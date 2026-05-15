"""
视频上传引擎

核心自动化逻辑：登录 → 上传视频 → 填写信息 → 发布
"""

import json
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from DrissionPage import ChromiumPage

from .browser import get_browser_for_account
from .config import WeixinConfig
from .dao import WeixinDAO
from .metadata import MetadataResolver, VideoMetadata
from .proxy import ProxyCheckError, log_proxy_check_for_upload
from .schemas import AccountStatus, TaskStatus
from .account_manager import get_account_lock
from src.core.logger import logger

# 全局上传并发闸门：避免多个 BackgroundTasks 同时跑 upload_video 导致多浏览器实例互相抢占。
_upload_slot = threading.BoundedSemaphore(WeixinConfig.MAX_CONCURRENT_UPLOADS)


class Uploader:
    """视频号上传引擎"""

    def __init__(self, dao: Optional[WeixinDAO] = None):
        self.dao = dao or WeixinDAO()

    def upload_video(
        self,
        task_id: int,
        account_id: int,
        video_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        metadata_source: str = "manual",
        scheduled_at: Optional[datetime] = None,
        drama_link: Optional[str] = None,
    ) -> dict:
        """
        上传单个视频。

        当前发表流程只会填写「视频描述」+「剧集链接」+「不显示位置」。标签功能已下线，
        所有标签写入逻辑均不再执行（保留过期的 `tags` 字段会被忽略）。

        位置默认强制为「不显示位置」（位置列表第一项），避免 IP 定位被自动写入。

        Returns:
            dict: {"status": "success"/"failed", "message": "..."}
        """
        account = self.dao.get_account(account_id)
        if not account:
            return self._fail_task(task_id, "账号不存在")

        if account["status"] != AccountStatus.ACTIVE.value:
            return self._fail_task(task_id, f"账号状态异常: {account['status']}")

        # 验证视频文件
        video_file = Path(video_path)
        if not video_file.exists():
            return self._fail_task(task_id, f"视频文件不存在: {video_path}")

        if video_file.suffix.lower() not in WeixinConfig.SUPPORTED_VIDEO_FORMATS:
            return self._fail_task(
                task_id,
                f"不支持的视频格式: {video_file.suffix}，支持: {WeixinConfig.SUPPORTED_VIDEO_FORMATS}",
            )

        file_size_mb = video_file.stat().st_size / (1024 * 1024)
        if file_size_mb > WeixinConfig.MAX_VIDEO_SIZE_MB:
            return self._fail_task(
                task_id, f"视频文件过大: {file_size_mb:.1f}MB，最大: {WeixinConfig.MAX_VIDEO_SIZE_MB}MB"
            )

        # 解析元数据；标签功能已下线，所以这里固定传空列表，避免任何后续 tag 处理。
        metadata = MetadataResolver.resolve(
            video_path=video_path,
            source=metadata_source,
            title=title,
            description=description,
            tags=None,
        )
        metadata.tags = []

        logger.info(f"开始上传任务 #{task_id}: {video_file.name} → 账号 {account['name']}")

        if WeixinConfig.PROXY_ENABLED:
            try:
                proxy_result = log_proxy_check_for_upload()
                if proxy_result and proxy_result.get("proxy"):
                    info = proxy_result["proxy"]
                    location = " ".join(
                        part
                        for part in (info.get("country"), info.get("region"), info.get("city"))
                        if part
                    )
                    logger.info(
                        f"Task #{task_id} proxy location: {info.get('ip') or '-'} {location or '-'}"
                    )
            except ProxyCheckError as e:
                return self._fail_task(task_id, str(e))
            except Exception as e:
                return self._fail_task(task_id, f"Proxy location check failed: {e}")

        _upload_slot.acquire()
        account_lock = get_account_lock(account_id)
        account_lock.acquire()
        page = None
        try:
            page = get_browser_for_account(account["cookie_path"])
            self._load_cookies(page, account["cookie_path"])

            self.dao.update_task_status(task_id, TaskStatus.UPLOADING)
            self._navigate_to_create(page)

            self._upload_file(page, str(video_file.absolute()))
            self.dao.update_task_status(task_id, TaskStatus.PROCESSING)
            self._wait_for_upload_complete(page)

            self.dao.update_task_status(task_id, TaskStatus.FILLING)
            self._fill_metadata(page, metadata, drama_link)

            # 强制将位置设为「不显示位置」（位置列表第一项），避免 IP 定位泄漏
            if WeixinConfig.LOCATION_MODE == "hidden":
                self._set_location_hidden(page)
            else:
                logger.info("Weixin location mode is proxy_ip; leaving location for platform IP detection")
            self._random_delay(0.5, 1)

            if scheduled_at:
                self._set_schedule_time(page, scheduled_at)

            self.dao.update_task_status(task_id, TaskStatus.PUBLISHING)
            self._click_publish(page)
            self._confirm_publish(page)

            self._save_cookies(page, account["cookie_path"])

            page.quit()
            page = None
            self.dao.update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"任务 #{task_id} 上传成功")
            return {"status": "success", "message": "上传成功"}

        except Exception as e:
            logger.error(f"任务 #{task_id} 上传失败: {e}")
            if page is not None:
                try:
                    page.quit()
                except Exception:
                    pass
            return self._fail_task(task_id, str(e))
        finally:
            account_lock.release()
            _upload_slot.release()

    def _navigate_to_create(self, page: ChromiumPage):
        """导航到视频发布页面。"""
        logger.info("正在打开发表页面...")
        page.get(WeixinConfig.POST_CREATE_URL)
        self._random_delay(3, 5)

        upload_area = page.ele("css:.ant-upload-drag, .upload-content, .post-upload-wrap", timeout=15)
        if not upload_area:
            logger.warning("未找到上传区域，页面可能未完全加载")
        else:
            logger.info("页面加载完成，找到上传区域")

    def _upload_file(self, page: ChromiumPage, file_path: str):
        """通过 file input 上传视频文件"""
        logger.info(f"正在上传文件: {file_path}")

        # 等待页面加载完成
        self._random_delay(1, 2)

        # 找到视频上传的 input[type=file]
        file_input = page.ele("css:input[type=file][accept*='video']", timeout=5)
        if not file_input:
            file_input = page.ele("css:input[type=file]", timeout=5)

        if not file_input:
            raise Exception("无法找到文件上传入口")

        # 使用 DrissionPage 的 input() 方法注入文件路径
        # 这个方法应该直接设置文件路径，不打开文件选择对话框
        try:
            file_input.input(file_path)
            logger.info("文件路径已注入到 input 元素")
            self._random_delay(2, 3)
            return
        except Exception as e:
            logger.warning(f"直接注入失败: {e}")

        # 如果直接注入失败，尝试先显示元素再注入
        try:
            page.run_js("""
                var fileInput = document.querySelector('input[type="file"][accept*="video"]');
                if (!fileInput) {
                    fileInput = document.querySelector('input[type="file"]');
                }
                if (fileInput) {
                    fileInput.style.display = 'block';
                    fileInput.style.visibility = 'visible';
                    fileInput.style.opacity = '1';
                    fileInput.style.position = 'relative';
                    fileInput.style.zIndex = '9999';
                }
            """)
            self._random_delay(0.5, 1)
            file_input = page.ele("css:input[type=file]", timeout=3)
            if file_input:
                file_input.input(file_path)
                logger.info("文件路径已注入（显示元素后）")
                self._random_delay(1, 2)
                return
        except Exception as e:
            logger.warning(f"显示元素后注入失败: {e}")

        raise Exception("无法注入文件路径")

    def _wait_for_upload_complete(self, page: ChromiumPage):
        """等待视频上传和处理完成"""
        logger.info("等待视频上传完成...")
        start_time = time.time()

        while time.time() - start_time < WeixinConfig.UPLOAD_TIMEOUT:
            # 检查是否出现描述输入框（表示上传完成，进入编辑状态）
            desc_editor = page.ele("css:.post-desc-box .input-editor, [contenteditable][data-placeholder='添加描述']", timeout=2)
            if desc_editor:
                logger.info("视频上传完成，已进入编辑状态")
                self._random_delay(1, 2)
                return

            # 检查上传进度
            try:
                progress = page.ele("css:.ant-progress-text, .upload-progress, .progress-text", timeout=1)
                if progress:
                    text = progress.text
                    percent_match = re.search(r"(\d+)%", text)
                    if percent_match:
                        percent = int(percent_match.group(1))
                        logger.info(f"上传进度: {percent}%")
            except Exception:
                pass

            # 检查是否有错误提示
            try:
                error = page.ele("css:.ant-message-error, .error-message, .upload-error", timeout=1)
                if error:
                    raise Exception(f"上传出错: {error.text}")
            except Exception:
                pass

            # 检查是否有视频预览
            try:
                video_preview = page.ele("css:video[src], .video-preview, .ant-upload-list-item", timeout=1)
                if video_preview:
                    logger.info("检测到视频预览，等待处理完成...")
            except Exception:
                pass

            time.sleep(2)

        raise Exception(f"视频上传超时（{WeixinConfig.UPLOAD_TIMEOUT}秒）")

    def _fill_metadata(self, page: ChromiumPage, metadata: VideoMetadata, drama_link: Optional[str] = None):
        """填写描述 + 剧集链接 + （可选）短标题。

        标签写入已下线：`metadata.tags` 即便有值也不会再拼进描述、也不会再点 #话题 添加。
        """
        logger.info("正在填写视频信息...")

        description = (metadata.description or "").strip()
        if description:
            self._fill_description(page, description)
            self._random_delay(0.5, 1)

        if drama_link:
            self._add_drama_link(page, drama_link)
            self._random_delay(0.5, 1)

        if metadata.title:
            self._fill_short_title(page, metadata.title)

        self._random_delay(0.5, 1)

    def _fill_description(self, page: ChromiumPage, description: str):
        """
        填写描述内容。

        视频号的描述编辑器实际 DOM 结构（来自抓到的页面源代码 tmp/视频号创建视频.html）：

            <div class="post-desc-box">
              <div contenteditable="" data-placeholder="添加描述" class="input-editor"></div>
              ...
            </div>

        历史踩坑：
            1) 旧实现 A：`innerHTML + Event('input')`
               → 页面看得到字，但发表后正文为空（Vue v-model 不认裸 Event）。
            2) 旧实现 B：`innerHTML + 自构 InputEvent('input', inputType:'insertFromPaste', data)`
               → 有时正常、有时被 Vue 当成「光标处再粘一遍」从而双写（任务日志里出现过
               「期望=5 / 实际=10」的镜像现象），最终发布出去描述为空或异常。

        现在改成 **完全走浏览器原生 `document.execCommand`**：
            - `execCommand('selectAll') + execCommand('delete')` 清空
            - `execCommand('insertText', false, line)` 逐行插入文本
            - `execCommand('insertLineBreak', false, null)` 在行间插换行
        execCommand 会派发真正的 `beforeinput` / `input` 事件，并由浏览器自己更新 DOM，
        Vue 的 v-model 100% 同步，不会出现「DOM 一份 + v-model 又拼一份」的双写问题。

        极端情况下（非常老旧的 Chromium 或 execCommand 整体失败）才回退到「Range
        手动塞 textNode + 自构 InputEvent」的兜底路径。
        """
        try:
            desc_editor = page.ele(
                "css:[contenteditable][data-placeholder='添加描述']", timeout=3
            )
            if not desc_editor:
                desc_editor = page.ele("css:.post-desc-box .input-editor", timeout=2)
            if not desc_editor:
                desc_editor = page.ele("css:.post-desc-box [contenteditable]", timeout=2)
            if not desc_editor:
                desc_editor = page.ele("css:[contenteditable='true']", timeout=2)
            if not desc_editor:
                desc_editor = page.ele("css:[contenteditable='']", timeout=2)

            if not desc_editor:
                logger.warning("未找到描述输入框")
                return

            desc_editor.click()
            self._random_delay(0.2, 0.4)

            # DrissionPage 会把脚本包成 function(){<user code>}，要用顶层 return 才能把
            # 结果带回 Python，否则 run_js 永远返回 None。
            js = r"""
            var el = arguments[0];
            var value = String(arguments[1] == null ? '' : arguments[1]);
            if (!el) return { ok: false, reason: 'no element' };

            function findEditable(root) {
                if (!root) return null;
                if (root.isContentEditable) return root;
                if (root.getAttribute && root.getAttribute('contenteditable') != null) return root;
                return root.querySelector(
                    '[contenteditable="true"],[contenteditable=""],[contenteditable]'
                );
            }

            var editor = findEditable(el);
            if (!editor) {
                return { ok: false, reason: 'no contenteditable',
                         tag: el.tagName, cls: el.className };
            }

            var doc = editor.ownerDocument || document;
            var win = doc.defaultView || window;

            editor.focus();

            // 1) 全选已有内容并通过 execCommand 删除 —— 让 Vue 收到真正的 input 事件，
            //    从而把内部 model 同步成空字符串。
            var clearOk = false;
            try {
                var range = doc.createRange();
                range.selectNodeContents(editor);
                var sel = win.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                clearOk = doc.execCommand('delete', false, null);
            } catch (e) {
                clearOk = false;
            }
            // execCommand 失败兜底：强制把 DOM 清干净
            if (!clearOk || editor.textContent.length > 0) {
                editor.innerHTML = '';
            }

            // 2) 逐行用 execCommand 插入文本
            var lines = value.split('\n');
            var usedExec = true;
            for (var i = 0; i < lines.length; i++) {
                if (i > 0) {
                    var brOk = false;
                    try {
                        brOk = doc.execCommand('insertLineBreak', false, null);
                    } catch (e) {
                        brOk = false;
                    }
                    if (!brOk) {
                        usedExec = false;
                        // Range 兜底：把 <br> 插到当前光标位置
                        var s = win.getSelection();
                        var br = doc.createElement('br');
                        if (s && s.rangeCount) {
                            var r = s.getRangeAt(0);
                            r.insertNode(br);
                            r.setStartAfter(br);
                            r.collapse(true);
                            s.removeAllRanges();
                            s.addRange(r);
                        } else {
                            editor.appendChild(br);
                        }
                        editor.dispatchEvent(new InputEvent('input', {
                            bubbles: true, cancelable: true,
                            inputType: 'insertLineBreak', data: null
                        }));
                    }
                }
                if (lines[i]) {
                    var inserted = false;
                    try {
                        inserted = doc.execCommand('insertText', false, lines[i]);
                    } catch (e) {
                        inserted = false;
                    }
                    if (!inserted) {
                        usedExec = false;
                        // Range 兜底：把 textNode 塞到光标位置
                        var s2 = win.getSelection();
                        var tn = doc.createTextNode(lines[i]);
                        if (s2 && s2.rangeCount) {
                            var r2 = s2.getRangeAt(0);
                            r2.insertNode(tn);
                            r2.setStartAfter(tn);
                            r2.collapse(true);
                            s2.removeAllRanges();
                            s2.addRange(r2);
                        } else {
                            editor.appendChild(tn);
                        }
                        editor.dispatchEvent(new InputEvent('input', {
                            bubbles: true, cancelable: true,
                            inputType: 'insertText', data: lines[i]
                        }));
                    }
                }
            }

            // 3) 兜底再来一发 change，覆盖少数版本只监听 change 的情况
            try {
                editor.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {}

            return {
                ok: true,
                used_exec_command: usedExec,
                text: editor.innerText,
                html: editor.innerHTML,
                expected_len: value.length
            };
            """
            result = page.run_js(js, desc_editor, description)
            preview = description[:30].replace("\n", "\\n")

            if isinstance(result, dict) and result.get("ok"):
                actual_text = result.get("text") or ""
                logger.info(
                    f"描述已写入：{preview}... "
                    f"(实际文本长度={len(actual_text)} / 期望={result.get('expected_len')}, "
                    f"execCommand={'是' if result.get('used_exec_command') else '回退Range'})"
                )
                return

            # 极端情况：连 DOM 都没塞进去，最后兜底用 DrissionPage 逐字符模拟
            logger.warning(f"描述写入异常（result={result}），回退到逐字符模拟输入")
            try:
                desc_editor.click()
                self._random_delay(0.1, 0.2)
                self._human_type(desc_editor, description)
                logger.info(f"描述已通过逐字符输入兜底写入：{preview}...")
            except Exception as e:
                logger.warning(f"逐字符兜底输入也失败：{e}")
        except Exception as e:
            logger.warning(f"描述填写失败: {e}")

    def _fill_short_title(self, page: ChromiumPage, title: str):
        """填写短标题"""
        try:
            short_title_selectors = [
                "css:.post-short-title-wrap input",
                "css:.short-title-wrap input",
                "css:input[placeholder*='概括视频主要内容']",
                "css:input[placeholder*='字数建议']",
            ]
            for selector in short_title_selectors:
                try:
                    title_input = page.ele(selector, timeout=2)
                    if title_input:
                        title_input.click()
                        self._random_delay(0.2, 0.3)
                        title_input.clear()
                        short_title = title[:16] if len(title) > 16 else title
                        self._human_type(title_input, short_title)
                        logger.info(f"短标题已填写: {short_title}")
                        return
                except Exception:
                    continue
            logger.warning("未找到短标题输入框")
        except Exception as e:
            logger.warning(f"短标题填写失败: {e}")

    def _set_location_hidden(self, page: ChromiumPage):
        """
        将「位置」固定为列表第一项「不显示位置」。

        自定义位置一直无法稳定生效（视频号会用 IP 反查覆盖坐标），所以这里直接选择「不显示位置」
        作为默认行为，避免任何位置信息出现在发表后的视频卡片上。
        """
        try:
            logger.info("将位置强制设为：不显示位置")

            position_display = page.ele("css:.post-position-wrap .position-display", timeout=3)
            if not position_display:
                position_display = page.ele("css:.position-display", timeout=2)
            if not position_display:
                logger.warning("未找到位置区域，跳过设置")
                return

            if not self._scroll_click_element(page, position_display):
                logger.warning("点击位置区域失败")
                return
            self._random_delay(0.5, 1)

            filter_wrap = page.ele("css:.location-filter-wrap", timeout=5)
            if not filter_wrap:
                logger.warning("未找到位置下拉框，跳过设置")
                return

            deadline = time.time() + 8.0
            while time.time() < deadline:
                items = page.eles("css:.location-filter-wrap .location-item", timeout=1) or []
                # 1) 优先按名字匹配「不显示位置」
                for item in items:
                    try:
                        name_el = item.ele("css:.name", timeout=0.5)
                        name_text = ((name_el.text if name_el else "") or "").strip()
                        if "不显示位置" in name_text or name_text == "不显示":
                            if self._scroll_click_element(page, item):
                                logger.info(f"已选择位置：{name_text or '不显示位置'}")
                                return
                    except Exception:
                        continue
                # 2) 兜底：点列表第一项（视频号的「不显示位置」就是 list[0]）
                if items:
                    try:
                        if self._scroll_click_element(page, items[0]):
                            logger.info("已选择位置列表第一项（按设计即「不显示位置」）")
                            return
                    except Exception:
                        pass
                self._random_delay(0.3, 0.6)

            logger.warning("位置列表未加载，无法选择「不显示位置」")

        except Exception as e:
            logger.warning(f"设置「不显示位置」失败: {e}")

    def _scroll_click_element(self, page: ChromiumPage, ele) -> bool:
        """滚动到视口内再点击；对文本节点会沿父链多点几次。"""
        if not ele:
            return False
        chain = [ele]
        cur = ele
        for _ in range(6):
            try:
                cur = cur.parent()
                if cur:
                    chain.append(cur)
            except Exception:
                break
        for target in chain:
            try:
                page.run_js(
                    "arguments[0].scrollIntoView({block:'center',inline:'nearest'});",
                    target,
                )
            except Exception:
                pass
            self._random_delay(0.08, 0.18)
            try:
                target.click()
                return True
            except Exception:
                pass
            try:
                page.run_js(
                    "arguments[0].dispatchEvent(new MouseEvent('click',"
                    "{bubbles:true,cancelable:true,view:window}));",
                    target,
                )
                return True
            except Exception:
                pass
            try:
                page.run_js("arguments[0].click&&arguments[0].click();", target)
                return True
            except Exception:
                pass
        return False

    def _try_js_click_link_option_video_series(self, page: ChromiumPage) -> bool:
        """用页面内脚本点击「视频号剧集」整行（避免点到无尺寸文本节点）。"""
        js = r"""
        (function () {
          var selectors = [
            '.link-list-options .link-option-item',
            '[class*="link-option"]',
            '[class*="LinkOption"]',
            '.weui-desktop-dropdown__list-box > *',
            '[role="menu"] [role="menuitem"]',
            '[role="listbox"] [role="option"]'
          ];
          var seen = new Set();
          var cand = [];
          selectors.forEach(function (sel) {
            try {
              document.querySelectorAll(sel).forEach(function (el) {
                if (!seen.has(el)) { seen.add(el); cand.push(el); }
              });
            } catch (e) {}
          });
          for (var i = 0; i < cand.length; i++) {
            var el = cand[i];
            var t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
            if (!t) continue;
            if (t.indexOf('小程序短剧') >= 0 && t.indexOf('视频号剧集') < 0) continue;
            if (t.indexOf('小程序') >= 0 && t.indexOf('短剧') >= 0 && t.indexOf('视频号剧集') < 0) continue;
            if (t.indexOf('视频号剧集') >= 0) {
              el.scrollIntoView({ block: 'center', inline: 'nearest' });
              el.click();
              return true;
            }
          }
          return false;
        }})();
        """
        try:
            return bool(page.run_js(js))
        except Exception:
            return False

    def _find_link_option_row_video_series(self, page: ChromiumPage):
        """定位链接类型列表里「视频号剧集」所在的可点击行。"""
        row_selectors = [
            "css:.link-list-options .link-option-item",
            "css:.link-option-item",
            "css:.link-list-options li",
            "css:[class*='link-option-item']",
            "xpath://*[contains(@class,'link-option-item')][contains(.,'视频号剧集')]",
            "xpath://*[contains(@class,'LinkOption')][contains(.,'视频号剧集')]",
            "xpath://li[contains(.,'视频号剧集')]",
        ]
        for sel in row_selectors:
            try:
                rows = page.eles(sel, timeout=2) or []
            except Exception:
                continue
            for row in rows:
                try:
                    t = (row.text or "").replace("\n", " ").strip()
                except Exception:
                    t = ""
                if not t:
                    continue
                if "小程序短剧" in t and "视频号剧集" not in t:
                    continue
                if "小程序" in t and "短剧" in t and "视频号剧集" not in t:
                    continue
                if "视频号剧集" in t:
                    return row
        return None

    def _try_js_click_picker_placeholder(self, page: ChromiumPage) -> bool:
        """点击「选择需要添加的视频号剧集」（源码: .post-component-choose-wrap span.placeholder）。"""
        js = r"""
        (function () {
          var wrap = document.querySelector('.post-component-choose-wrap');
          if (wrap) {
            var ph = wrap.querySelector('.placeholder') || wrap.querySelector('.content-wrap');
            if (ph) {
              var t = (ph.innerText || ph.textContent || '').trim();
              if (t.indexOf('选择需要添加') >= 0 || t.indexOf('选择需要关联') >= 0 || t.indexOf('视频号剧集') >= 0) {
                ph.scrollIntoView({ block: 'center' });
                ph.click();
                return true;
              }
              ph.scrollIntoView({ block: 'center' });
              ph.click();
              return true;
            }
            wrap.scrollIntoView({ block: 'center' });
            wrap.click();
            return true;
          }
          var nodes = document.querySelectorAll(
            'button, a, div[role="button"], span.placeholder, span, [class*="placeholder"]'
          );
          for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            var t = (el.innerText || el.textContent || '').trim();
            if ((t.indexOf('选择需要添加') >= 0 || t.indexOf('选择需要关联') >= 0) && t.indexOf('视频号剧集') >= 0) {
              el.scrollIntoView({ block: 'center' });
              el.click();
              return true;
            }
          }
          return false;
        }})();
        """
        try:
            return bool(page.run_js(js))
        except Exception:
            return False

    @staticmethod
    def _dialog_root_from_element(ele) -> Optional[object]:
        """向上查找包含 dialog-wrap 的容器。"""
        if not ele:
            return None
        cur = ele
        for _ in range(28):
            try:
                cls = cur.attr("class") or ""
                if isinstance(cls, str) and "dialog-wrap" in cls:
                    return cur
                cur = cur.parent()
            except Exception:
                return None
        return None

    @staticmethod
    def _row_inside_ant_table(row) -> bool:
        try:
            cur = row
            for _ in range(12):
                if not cur:
                    break
                cls = cur.attr("class") or ""
                if isinstance(cls, str) and "ant-table" in cls:
                    return True
                cur = cur.parent()
        except Exception:
            pass
        return False

    def _confirm_native_drama_dialog(self, page: ChromiumPage) -> None:
        """点击剧集弹层底部的「添加」按钮（通过 dialog 标题定位，不检查可见性）。"""
        btn_selectors = (
            "xpath://h3[contains(.,'视频号剧集')]"
            "/ancestor::div[contains(@class,'weui-desktop-dialog')]//button[contains(@class,'weui-desktop-btn_primary')]",
            "xpath://h3[contains(.,'选择需要关联')]"
            "/ancestor::div[contains(@class,'weui-desktop-dialog')]//button[contains(@class,'weui-desktop-btn_primary')]",
        )
        for sel in btn_selectors:
            try:
                btn = page.ele(sel, timeout=2)
                if not btn:
                    continue
                tx = (btn.text or "").strip()
                if tx not in ("确定", "确认", "添加"):
                    continue
                cls = btn.attr("class") or ""
                if isinstance(cls, str) and "disabled" in cls:
                    continue
                self._scroll_click_element(page, btn)
                logger.info(f"已点击剧集弹层按钮: {tx}")
                return
            except Exception:
                continue

    def _check_browser_alive(self, page: ChromiumPage) -> None:
        """检测浏览器是否已关闭，若已关闭则抛出异常。"""
        try:
            page.run_js("return 1")
        except Exception as e:
            raise Exception(f"浏览器已关闭: {e}")

    def _find_drama_dialog_search_input(self, page: ChromiumPage):
        """
        通过标题文本定位剧集弹层里的搜索框。
        微信页面会把弹层浮在发表页之上，根节点不一定正好是 .weui-desktop-dialog。
        """
        # 用 JS 从「选择需要关联的视频号剧集」标题反查浮层容器，再给搜索 input 打标。
        js = r"""
        (function () {
          document.querySelectorAll('input[data-vd-drama-search]').forEach(function (el) {
            el.removeAttribute('data-vd-drama-search');
          });

          function text(el) {
            return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, ' ').trim();
          }

          function isUsableInput(el, allowHidden) {
            if (!el || el.disabled || el.readOnly) return false;
            var ph = el.getAttribute('placeholder') || '';
            if (ph.indexOf('小游戏') >= 0 || ph.indexOf('小说') >= 0) return false;
            var rect = el.getBoundingClientRect();
            return allowHidden || (rect.width > 0 && rect.height > 0);
          }

          function hasDramaPickerContent(el) {
            return !!(el && el.querySelector(
              '.drama-table-wrap,tr.drama-row,tbody tr.ant-table-row,.drama-title,input[placeholder="搜索内容"]'
            ));
          }

          function isVisible(el) {
            if (!el) return false;
            var style = el.ownerDocument.defaultView.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            var rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }

          function markActiveDramaPaneInput(root) {
            var panes = root.querySelectorAll('.dialog-wrap');
            for (var p = panes.length - 1; p >= 0; p--) {
              var pane = panes[p];
              if (!isVisible(pane)) continue;
              if (!pane.querySelector('.drama-table-wrap,tr.drama-row,.drama-title')) continue;
              var input = pane.querySelector('input.weui-desktop-form__input[placeholder="搜索内容"],input[placeholder="搜索内容"]');
              if (isUsableInput(input, false)) {
                input.setAttribute('data-vd-drama-search', '1');
                return true;
              }
            }
            return false;
          }

          function findRoot(title) {
            var cur = title ? title.parentElement : null;
            for (var i = 0; i < 14 && cur; i++) {
              var cls = cur.className || '';
              if (typeof cls !== 'string') cls = '';
              if (
                cls.indexOf('weui-desktop-dialog') >= 0 ||
                cls.indexOf('dialog') >= 0 ||
                cls.indexOf('modal') >= 0 ||
                cur.getAttribute('role') === 'dialog'
              ) {
                if (hasDramaPickerContent(cur)) return cur;
              }
              cur = cur.parentElement;
            }
            return title.parentElement || document.body;
          }

          function markInput(root) {
            if (markActiveDramaPaneInput(root)) return true;
            var selectors = [
              'input.weui-desktop-form__input[placeholder="搜索内容"]',
              'input[placeholder="搜索内容"]',
              'input.weui-desktop-form__input[placeholder*="搜索"]',
              'input[placeholder*="搜索"]',
              'input[placeholder*="短剧"]'
            ];
            var hiddenExact = null;
            for (var s = 0; s < selectors.length; s++) {
              var inputs = root.querySelectorAll(selectors[s]);
              for (var i = 0; i < inputs.length; i++) {
                if (isUsableInput(inputs[i], false)) {
                  inputs[i].setAttribute('data-vd-drama-search', '1');
                  return true;
                }
                if (
                  !hiddenExact &&
                  inputs[i] &&
                  (inputs[i].getAttribute('placeholder') || '') === '搜索内容' &&
                  isUsableInput(inputs[i], true)
                ) {
                  hiddenExact = inputs[i];
                }
              }
            }
            // 微信页面源码里剧集弹层的 active pane 有时仍保留 display:none，
            // 这种情况下 rect 为 0，但精确 placeholder 仍是后续 Vue 搜索绑定的输入框。
            if (hiddenExact) {
              hiddenExact.setAttribute('data-vd-drama-search', '1');
              return true;
            }
            return false;
          }

          function markBestGlobalInput() {
            var exactInputs = document.querySelectorAll(
              'input.weui-desktop-form__input[placeholder="搜索内容"],input[placeholder="搜索内容"]'
            );
            var hiddenExact = null;
            for (var e = 0; e < exactInputs.length; e++) {
              if (isUsableInput(exactInputs[e], false)) {
                exactInputs[e].setAttribute('data-vd-drama-search', '1');
                return true;
              }
              if (!hiddenExact && isUsableInput(exactInputs[e], true)) {
                hiddenExact = exactInputs[e];
              }
            }
            if (hiddenExact) {
              hiddenExact.setAttribute('data-vd-drama-search', '1');
              return true;
            }
            return false;
          }

          if (markActiveDramaPaneInput(document)) return true;

          var titles = document.querySelectorAll(
            'h1,h2,h3,h4,.weui-desktop-dialog__title,[class*="dialog__title"],[class*="dialog-title"]'
          );
          for (var t = 0; t < titles.length; t++) {
            var titleText = text(titles[t]);
            if (titleText.indexOf('视频号剧集') < 0) continue;
            if (titleText.indexOf('选择需要关联') < 0 && titleText.indexOf('选择需要添加') < 0) continue;
            if (markInput(findRoot(titles[t]))) return true;
          }

          var dialogs = document.querySelectorAll(
            '.weui-desktop-dialog,[class*="weui-desktop-dialog"],[role="dialog"],[class*="dialog"],[class*="modal"]'
          );
          for (var d = 0; d < dialogs.length; d++) {
            if (text(dialogs[d]).indexOf('视频号剧集') < 0) continue;
            if (markInput(dialogs[d])) return true;
          }

          if (markBestGlobalInput()) return true;

          return false;
        })();
        """
        try:
            if not page.run_js(js):
                return None
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("disconnected", "target closed", "session", "connection refused")):
                raise
            return None

        try:
            el = page.ele("css:input[data-vd-drama-search='1']", timeout=2)
            return el
        except Exception:
            return None

    def _js_search_drama_dialog(self, page: ChromiumPage, drama_query: str) -> bool:
        """在剧集浮层内直接输入搜索词；覆盖主文档、同源 iframe 和 shadow DOM。"""
        safe_query = json.dumps((drama_query or "").strip(), ensure_ascii=False)
        js = f"""
        (function () {{
          var query = {safe_query};
          function text(el) {{
            return ((el && (el.innerText || el.textContent)) || '').replace(/\\s+/g, ' ').trim();
          }}
          function visible(el) {{
            if (!el) return false;
            var style = el.ownerDocument.defaultView.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            var rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }}
          function isDramaSearchInput(el) {{
            if (!el || el.tagName !== 'INPUT' || el.disabled || el.readOnly) return false;
            var ph = el.getAttribute('placeholder') || '';
            if (ph.indexOf('小游戏') >= 0 || ph.indexOf('小说') >= 0) return false;
            if (visible(el)) return ph === '搜索内容' || ph.indexOf('搜索') >= 0;
            return ph === '搜索内容';
          }}
          function setNativeValue(el, value) {{
            if (visible(el)) el.focus();
            var setter = Object.getOwnPropertyDescriptor(el.ownerDocument.defaultView.HTMLInputElement.prototype, 'value').set;
            if (setter) setter.call(el, '');
            else el.value = '';
            el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'deleteContentBackward', data: null }}));
            if (setter) setter.call(el, value);
            else el.value = value;
            el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: value }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: 'Enter', code: 'Enter', keyCode: 13, which: 13 }}));
            var iconRoot =
              (el.closest && (el.closest('.dialog-body') || el.closest('.filter-wrap') || el.closest('.search-wrap'))) ||
              el.parentElement;
            var icon = iconRoot && iconRoot.querySelector('.search-icon,svg[class*="search"]');
            if (icon) icon.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: el.ownerDocument.defaultView }}));
          }}
          function findRootFromTitle(doc) {{
            var titles = doc.querySelectorAll('h1,h2,h3,h4,.weui-desktop-dialog__title,[class*="dialog__title"],[class*="dialog-title"]');
            for (var i = titles.length - 1; i >= 0; i--) {{
              var titleText = text(titles[i]);
              if (titleText.indexOf('视频号剧集') < 0) continue;
              if (titleText.indexOf('选择需要关联') < 0 && titleText.indexOf('选择需要添加') < 0) continue;
              var cur = titles[i].parentElement;
              for (var depth = 0; depth < 20 && cur; depth++) {{
                if (cur.querySelector && cur.querySelector('input[placeholder="搜索内容"],input[placeholder*="搜索"],tr.drama-row,.drama-title')) return cur;
                cur = cur.parentElement;
              }}
            }}
            return null;
          }}
          function findInput(doc) {{
            var panes = doc.querySelectorAll('.dialog-wrap');
            for (var p = panes.length - 1; p >= 0; p--) {{
              var pane = panes[p];
              if (!visible(pane)) continue;
              if (!pane.querySelector('.drama-table-wrap,tr.drama-row,.drama-title')) continue;
              var paneInput = pane.querySelector('input.weui-desktop-form__input[placeholder="搜索内容"],input[placeholder="搜索内容"]');
              if (isDramaSearchInput(paneInput)) return paneInput;
            }}
            var roots = [];
            var root = findRootFromTitle(doc);
            if (root) roots.push(root);
            doc.querySelectorAll('.weui-desktop-dialog,[class*="weui-desktop-dialog"],[role="dialog"],[class*="dialog"],[class*="modal"],body').forEach(function (el) {{
              if (text(el).indexOf('视频号剧集') >= 0 || el === doc.body) roots.push(el);
            }});
            for (var r = 0; r < roots.length; r++) {{
              var inputs = roots[r].querySelectorAll('input.weui-desktop-form__input[placeholder="搜索内容"],input[placeholder="搜索内容"],input[placeholder*="搜索"]');
              for (var i = 0; i < inputs.length; i++) {{
                if (isDramaSearchInput(inputs[i])) return inputs[i];
              }}
            }}
            return null;
          }}
          function visitDoc(doc, seen) {{
            if (!doc || seen.indexOf(doc) >= 0) return false;
            seen.push(doc);
            var input = findInput(doc);
            if (input) {{
              if (visible(input)) input.scrollIntoView({{ block: 'center', inline: 'nearest' }});
              setNativeValue(input, query);
              return true;
            }}
            var all = doc.querySelectorAll('*');
            for (var s = 0; s < all.length; s++) {{
              if (all[s].shadowRoot && visitDoc(all[s].shadowRoot, seen)) return true;
            }}
            var frames = doc.querySelectorAll('iframe,frame');
            for (var f = 0; f < frames.length; f++) {{
              try {{
                if (frames[f].contentDocument && visitDoc(frames[f].contentDocument, seen)) return true;
              }} catch (e) {{}}
            }}
            return false;
          }}
          return visitDoc(document, []);
        }})();
        """
        try:
            return bool(page.run_js(js))
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("disconnected", "target closed", "session", "connection refused")):
                raise
            logger.warning(f"JS 搜索剧集输入失败: {e}")
            return False

    def _js_pick_first_drama_row(self, page: ChromiumPage, drama_query: str = "") -> bool:
        """在剧集表格中点击一行：有剧名关键词则优先匹配 `.drama-title`，否则首条。"""
        safe_query = json.dumps((drama_query or "").strip(), ensure_ascii=False)
        js = f"""
        (function () {{
          var preferred = {safe_query};
          function text(el) {{
            return ((el && (el.innerText || el.textContent)) || '').replace(/\\s+/g, ' ').trim();
          }}
          function normalized(value) {{
            return (value || '').replace(/[\\s|\\-|·・_《》<>「」【】\\[\\]()（）]/g, '');
          }}
          function visible(el) {{
            if (!el) return false;
            var style = el.ownerDocument.defaultView.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            var rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }}
          function hasDramaPickerContent(el) {{
            return !!(el && el.querySelector(
              'input[placeholder="搜索内容"],input[placeholder*="搜索"],tr.drama-row,tbody tr.ant-table-row,.drama-title'
            ));
          }}
          function findRoot(doc, title) {{
            var cur = title ? title.parentElement : null;
            for (var i = 0; i < 20 && cur; i++) {{
              var cls = cur.className || '';
              if (typeof cls !== 'string') cls = '';
              if (
                cls.indexOf('weui-desktop-dialog') >= 0 ||
                cls.indexOf('dialog') >= 0 ||
                cls.indexOf('modal') >= 0 ||
                cur.getAttribute('role') === 'dialog' ||
                hasDramaPickerContent(cur)
              ) {{
                if (hasDramaPickerContent(cur)) return cur;
              }}
              cur = cur.parentElement;
            }}
            return doc.body;
          }}
          function visitDoc(doc, seen) {{
            if (!doc || seen.indexOf(doc) >= 0) return false;
            seen.push(doc);
            if (pickInDoc(doc)) return true;
            var all = doc.querySelectorAll('*');
            for (var s = 0; s < all.length; s++) {{
              if (all[s].shadowRoot && visitDoc(all[s].shadowRoot, seen)) return true;
            }}
            var frames = doc.querySelectorAll('iframe,frame');
            for (var f = 0; f < frames.length; f++) {{
              try {{
                if (frames[f].contentDocument && visitDoc(frames[f].contentDocument, seen)) return true;
              }} catch (e) {{}}
            }}
            return false;
          }}
          function pickInDoc(doc) {{
            var titleNodes = doc.querySelectorAll(
              'h1,h2,h3,h4,.weui-desktop-dialog__title,[class*="dialog__title"],[class*="dialog-title"]'
            );
            var dlg = null;
            for (var t = titleNodes.length - 1; t >= 0; t--) {{
              var titleText = text(titleNodes[t]);
              if (titleText.indexOf('视频号剧集') >= 0) {{ dlg = findRoot(doc, titleNodes[t]); break; }}
            }}
            if (!dlg) {{
              var dialogs = doc.querySelectorAll(
                '.weui-desktop-dialog,[class*="weui-desktop-dialog"],[role="dialog"],[class*="dialog"],[class*="modal"]'
              );
              for (var d = dialogs.length - 1; d >= 0; d--) {{
                if (text(dialogs[d]).indexOf('视频号剧集') >= 0) {{ dlg = dialogs[d]; break; }}
              }}
            }}
            if (!dlg) dlg = doc.body;
            var rows = dlg.querySelectorAll('tr.drama-row, tr.ant-table-row.drama-row, tbody tr.ant-table-row');
            var normalizedPreferred = normalized(preferred);
            var list = [];
            for (var j = 0; j < rows.length; j++) {{
              var el = rows[j];
              if (!visible(el)) continue;
              var titleEl = el.querySelector('.drama-title');
              var rowTitle = titleEl ? titleEl.textContent.trim() : text(el);
              if (!rowTitle || rowTitle.indexOf('暂无') >= 0) continue;
              if (rowTitle.replace(/[\\s|\\-]/g, '') === '') continue;
              list.push({{ el: el, title: rowTitle, normalizedTitle: normalized(rowTitle) }});
            }}
            if (preferred) {{
              for (var k = 0; k < list.length; k++) {{
                if (
                  list[k].title.indexOf(preferred) >= 0 ||
                  (normalizedPreferred && list[k].normalizedTitle.indexOf(normalizedPreferred) >= 0)
                ) {{
                  list[k].el.scrollIntoView({{ block: 'center', inline: 'nearest' }});
                  list[k].el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: list[k].el.ownerDocument.defaultView }}));
                  list[k].el.click();
                  return true;
                }}
              }}
              return false;
            }}
            if (list.length > 0) {{
              list[0].el.scrollIntoView({{ block: 'center', inline: 'nearest' }});
              list[0].el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: list[0].el.ownerDocument.defaultView }}));
              list[0].el.click();
              return true;
            }}
            return false;
          }}
          return visitDoc(document, []);
        }})();
        """
        try:
            return bool(page.run_js(js))
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("disconnected", "target closed", "session", "connection refused")):
                raise
            return False

    def _search_and_select_native_drama(self, page: ChromiumPage, drama_name: Optional[str]) -> bool:
        """
        在剧集弹层搜索框输入关键词，再选第一条结果行。
        浏览器关闭时抛出异常而非静默超时。
        """
        query = (drama_name or "").strip()

        # 检测浏览器是否存活
        self._check_browser_alive(page)

        # 等待弹层出现并定位搜索框
        search_input = None
        for attempt in range(20):
            self._check_browser_alive(page)
            search_input = self._find_drama_dialog_search_input(page)
            if search_input:
                break
            time.sleep(0.3)

        logger.info(f"搜索剧集: {query}, 已定位搜索框: {bool(search_input)}")

        js_search_done = False
        if query:
            js_search_done = self._js_search_drama_dialog(page, query)
            logger.info(f"JS 搜索剧集: {query}, 已触发输入: {js_search_done}")
            if js_search_done:
                self._random_delay(1.2, 1.8)

        if search_input and not js_search_done:
            try:
                self._scroll_click_element(page, search_input)
                self._random_delay(0.2, 0.4)
                try:
                    search_input.clear()
                except Exception:
                    pass
                if query:
                    self._human_type(search_input, query)
                    try:
                        page.run_js(
                            """
                            var el = arguments[0];
                            var value = arguments[1];
                            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, value);
                            el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
                            """,
                            search_input,
                            query,
                        )
                    except Exception:
                        pass
                self._random_delay(1.2, 1.8)
            finally:
                try:
                    page.run_js(
                        "var n=document.querySelector('input[data-vd-drama-search]');"
                        "if(n)n.removeAttribute('data-vd-drama-search');"
                    )
                except Exception:
                    pass
        else:
            if not search_input and not js_search_done:
                logger.info("未通过脚本定位剧集搜索框，继续等待剧集列表结果")

        # 循环等待并点击第一条剧集
        deadline = time.time() + 18.0
        while time.time() < deadline:
            self._check_browser_alive(page)

            if self._js_pick_first_drama_row(page, query):
                disp = query or "（首条结果）"
                logger.info(f"已选择剧集: {disp}")
                self._random_delay(0.35, 0.6)
                self._confirm_native_drama_dialog(page)
                return True

            time.sleep(0.45)

        if not search_input and not js_search_done:
            logger.warning("未找到剧集搜索输入框，且未能通过当前列表选择剧集")
        logger.warning(f"剧集列表未出现可点击行: {query or '(关键词为空)'}")
        return False

    def _add_drama_link(self, page: ChromiumPage, drama_name: str):
        """添加视频号剧集链接：选「视频号剧集」→ 点「选择需要关联/添加的视频号剧集」→ 在「搜索内容」中搜索并选择。"""
        try:
            logger.info(f"正在添加剧集链接: {drama_name}")

            link_wrap = page.ele("css:.post-link-wrap .link-display-wrap", timeout=3)
            if not link_wrap:
                link_wrap = page.ele("css:.link-display-wrap", timeout=2)

            if not link_wrap:
                logger.warning("未找到链接区域")
                return

            if not self._scroll_click_element(page, link_wrap):
                logger.warning("点击链接区域失败")
                return

            self._random_delay(0.8, 1.3)

            clicked_series = self._try_js_click_link_option_video_series(page)
            if clicked_series:
                logger.info("已通过脚本选择「视频号剧集」")
            else:
                drama_option = self._find_link_option_row_video_series(page)
                if not drama_option:
                    try:
                        options_container = page.ele("css:.link-list-options", timeout=2)
                        if options_container:
                            page.run_js(
                                "arguments[0].scrollTop = arguments[0].scrollHeight",
                                options_container,
                            )
                            self._random_delay(0.3, 0.5)
                        drama_option = self._find_link_option_row_video_series(page)
                    except Exception:
                        pass

                if not drama_option:
                    try:
                        hint = page.ele("text:视频号剧集", timeout=2)
                        if hint:
                            drama_option = hint
                    except Exception:
                        drama_option = None

                if not drama_option:
                    logger.warning("未找到「视频号剧集」选项（已跳过小程序短剧）")
                    return

                if not self._scroll_click_element(page, drama_option):
                    logger.warning("选择「视频号剧集」失败")
                    return

            self._random_delay(0.6, 1)

            # 选类型后出现「选择需要添加的视频号剧集」（.post-component-choose-wrap .placeholder）
            picker_clicked = False
            try:
                if self._try_js_click_picker_placeholder(page):
                    picker_clicked = True
                    logger.info("已通过脚本点击剧集选择入口 (.post-component-choose-wrap)")
                    self._random_delay(0.6, 1)
            except Exception:
                pass

            if not picker_clicked:
                picker_labels = (
                    "css:.post-component-choose-wrap .placeholder",
                    "css:.post-component-choose-wrap .content-wrap",
                    "css:.link-input-wrap .post-component-choose-wrap .content-wrap",
                    "text:选择需要关联的视频号剧集",
                    "text:选择需要添加的视频号剧集",
                    "text:选择需要关联",
                    "text:选择需要添加",
                    "xpath://*[contains(text(),'选择需要关联的视频号剧集')]",
                    "xpath://*[contains(text(),'选择需要添加的视频号剧集')]",
                    "xpath://*[contains(text(),'选择需要关联')]",
                    "xpath://*[contains(text(),'选择需要添加')]",
                )
                for picker_sel in picker_labels:
                    try:
                        picker = page.ele(picker_sel, timeout=5)
                        if picker and self._scroll_click_element(page, picker):
                            picker_clicked = True
                            logger.info("已点击剧集选择入口（关联/添加视频号剧集）")
                            self._random_delay(0.6, 1)
                            break
                    except Exception:
                        continue

            if not picker_clicked:
                logger.info("未找到「选择需要添加的视频号剧集」，尝试在当前层搜索")

            if not self._search_and_select_native_drama(page, drama_name):
                return

            logger.info(f"剧集链接流程已完成: {drama_name or '(首条结果)'}")

        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("disconnected", "target closed", "浏览器已关闭", "session", "connection refused")):
                raise
            logger.warning(f"添加剧集链接失败: {e}")

    def _set_schedule_time(self, page: ChromiumPage, scheduled_at: datetime):
        """设置定时发布时间"""
        logger.info(f"设置定时发表: {scheduled_at}")

        # 点击定时发表选项
        schedule_option = page.ele("text:定时发表", timeout=5)
        if schedule_option:
            schedule_option.click()
            self._random_delay(0.5, 1)

            # 设置日期和时间
            date_input = page.ele("css:.date-picker input, input[placeholder*=日期]", timeout=5)
            if date_input:
                date_str = scheduled_at.strftime("%Y-%m-%d")
                date_input.clear()
                self._human_type(date_input, date_str)

            time_input = page.ele("css:.time-picker input, input[placeholder*=时间]", timeout=5)
            if time_input:
                time_str = scheduled_at.strftime("%H:%M")
                time_input.clear()
                self._human_type(time_input, time_str)

            self._random_delay(0.5, 1)

    def _click_publish(self, page: ChromiumPage):
        """点击发表按钮"""
        logger.info("正在发表...")
        # 等待按钮可用（服务端转码/处理完成后才可点击），时长上限与 UPLOAD_TIMEOUT 一致
        start = time.time()
        deadline = start + WeixinConfig.UPLOAD_TIMEOUT
        last_log = start
        logged_disabled_hint = False
        while time.time() < deadline:
            # 检查浏览器是否已关闭
            try:
                page.run_js("return 1")
            except Exception:
                raise Exception("浏览器已关闭，无法继续等待发表按钮")
            try:
                buttons = page.eles("css:.weui-desktop-btn_primary", timeout=2)
                for btn in buttons:
                    if btn.text.strip() == "发表":
                        btn_class = btn.attr("class") or ""
                        if "disabled" not in btn_class:
                            btn.click()
                            logger.info("已点击发表按钮")
                            self._random_delay(1, 2)
                            return
                        now = time.time()
                        if not logged_disabled_hint:
                            logger.info(
                                f"发表按钮暂不可用，等待中...（与上传环节共用超时上限 {WeixinConfig.UPLOAD_TIMEOUT} 秒）"
                            )
                            logged_disabled_hint = True
                            last_log = now
                        elif now - last_log >= 30:
                            logger.info(
                                f"发表按钮仍不可用...（已等待 {now - start:.0f} / {WeixinConfig.UPLOAD_TIMEOUT} 秒）"
                            )
                            last_log = now
                        break
            except Exception:
                pass
            self._random_delay(1, 2)
        raise Exception(
            f"未找到可用的发表按钮（等待超时 {WeixinConfig.UPLOAD_TIMEOUT} 秒，与视频上传超时一致）"
        )

    def _is_post_list_url(self, url: str) -> bool:
        """发表成功后站点会跳转到作品列表页。"""
        if not url:
            return False
        return (
            "channels.weixin.qq.com" in url
            and "/platform/post/list" in url
        )

    def _confirm_publish(self, page: ChromiumPage):
        """确认发表（处理可能的确认弹窗），成功以跳转到作品列表页为准。"""
        self._random_delay(1, 2)

        confirm_selectors = [
            "css:.weui-desktop-btn_primary:contains('确定')",
            "css:.weui-desktop-btn_primary:contains('确认')",
            "css:.weui-desktop-btn_primary:contains('继续')",
            "text:确定",
            "text:确认发表",
            "text:继续发表",
        ]

        # 发表后应自动跳转到 https://channels.weixin.qq.com/platform/post/list
        deadline = time.time() + 120
        while time.time() < deadline:
            if self._is_post_list_url(page.url):
                logger.info(f"已跳转至作品列表，发表成功: {page.url}")
                return

            for selector in confirm_selectors:
                try:
                    confirm_btn = page.ele(selector, timeout=1)
                    if confirm_btn:
                        confirm_btn.click()
                        logger.info("已确认发表弹窗")
                        self._random_delay(1, 2)
                        break
                except Exception:
                    continue

            self._random_delay(0.5, 1.0)

        raise Exception(
            "发表后未跳转到作品列表页面 "
            f"({WeixinConfig.POST_LIST_URL})，当前 URL: {page.url!r}"
        )

    def _load_cookies(self, page: ChromiumPage, cookie_path: str):
        """加载 Cookie"""
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        page.get(WeixinConfig.CHANNELS_URL)
        for cookie in cookies:
            page.set.cookies(cookie)

    def _save_cookies(self, page: ChromiumPage, cookie_path: str):
        """保存 Cookie"""
        cookies = page.cookies()
        Path(cookie_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    def _human_type(self, element, text: str):
        """模拟人类打字速度输入"""
        for char in text:
            element.input(char)
            time.sleep(random.uniform(0.02, 0.08))

    def _random_delay(self, min_sec: float = None, max_sec: float = None):
        """随机延迟"""
        min_sec = min_sec or WeixinConfig.OPERATION_DELAY_MIN
        max_sec = max_sec or WeixinConfig.OPERATION_DELAY_MAX
        time.sleep(random.uniform(min_sec, max_sec))

    def _fail_task(self, task_id: int, message: str) -> dict:
        """标记任务失败"""
        self.dao.update_task_status(task_id, TaskStatus.FAILED, error_msg=message)
        return {"status": "failed", "message": message}
