"""
视频上传引擎

核心自动化逻辑：登录 → 上传视频 → 填写信息 → 发布
"""

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from DrissionPage import ChromiumPage

from .browser import get_browser_for_account
from .config import WeixinConfig
from .dao import WeixinDAO
from .metadata import MetadataResolver, VideoMetadata
from .schemas import AccountStatus, TaskStatus
from src.core.logger import logger


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
        tags: Optional[list[str]] = None,
        metadata_source: str = "manual",
        scheduled_at: Optional[datetime] = None,
        drama_link: Optional[str] = None,
    ) -> dict:
        """
        上传单个视频

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

        # 解析元数据
        metadata = MetadataResolver.resolve(
            video_path=video_path,
            source=metadata_source,
            title=title,
            description=description,
            tags=tags,
        )

        logger.info(f"开始上传任务 #{task_id}: {video_file.name} → 账号 {account['name']}")

        try:
            page = get_browser_for_account(account["cookie_path"])
            self._load_cookies(page, account["cookie_path"])

            # 1. 导航到发布页面
            self.dao.update_task_status(task_id, TaskStatus.UPLOADING)
            self._navigate_to_create(page)

            # 2. 上传视频文件
            self._upload_file(page, str(video_file.absolute()))
            self.dao.update_task_status(task_id, TaskStatus.PROCESSING)
            self._wait_for_upload_complete(page)

            # 3. 填写标题、描述、标签、剧集链接
            self.dao.update_task_status(task_id, TaskStatus.FILLING)
            self._fill_metadata(page, metadata, drama_link)

            # 4. 设置定时发布
            if scheduled_at:
                self._set_schedule_time(page, scheduled_at)

            # 5. 发布
            self.dao.update_task_status(task_id, TaskStatus.PUBLISHING)
            self._click_publish(page)
            self._confirm_publish(page)

            # 6. 保存更新后的 Cookie
            self._save_cookies(page, account["cookie_path"])

            page.quit()
            self.dao.update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"任务 #{task_id} 上传成功")
            return {"status": "success", "message": "上传成功"}

        except Exception as e:
            logger.error(f"任务 #{task_id} 上传失败: {e}")
            return self._fail_task(task_id, str(e))

    def _navigate_to_create(self, page: ChromiumPage):
        """导航到视频发布页面"""
        logger.info("正在打开发表页面...")
        page.get(WeixinConfig.POST_CREATE_URL)
        self._random_delay(3, 5)

        # 等待页面加载完成，检查上传区域
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
        """填写描述、标签、短标题、剧集链接"""
        logger.info("正在填写视频信息...")

        # 将标签追加到描述末尾（格式：#标签1 #标签2）
        description = metadata.description or ""
        if metadata.tags:
            tag_str = " ".join(f"#{tag}" for tag in metadata.tags[:5])
            description = f"{description}\n{tag_str}" if description else tag_str

        if description:
            self._fill_description(page, description)
            self._random_delay(0.5, 1)

        # 添加剧集链接
        if drama_link:
            self._add_drama_link(page, drama_link)
            self._random_delay(0.5, 1)

        # 填写短标题
        if metadata.title:
            self._fill_short_title(page, metadata.title)

        self._random_delay(0.5, 1)

    def _fill_description(self, page: ChromiumPage, description: str):
        """填写描述内容"""
        try:
            # 找到描述框
            desc_editor = page.ele("css:.post-desc-box .input-editor, [contenteditable][data-placeholder='添加描述']", timeout=3)
            if not desc_editor:
                desc_editor = page.ele("css:[contenteditable='']", timeout=2)

            if desc_editor:
                # 点击聚焦
                desc_editor.click()
                self._random_delay(0.2, 0.3)

                # 使用 JavaScript 设置内容并触发事件
                # 需要模拟用户输入来触发 Vue 的响应式更新
                page.run_js(f"""
                    var el = arguments[0];
                    el.focus();

                    // 清空内容
                    el.innerHTML = '';

                    // 设置新内容
                    var lines = `{description.replace('`', '\\`').replace('\\', '\\\\')}`.split('\\n');
                    for (var i = 0; i < lines.length; i++) {{
                        if (i > 0) {{
                            el.appendChild(document.createElement('br'));
                        }}
                        el.appendChild(document.createTextNode(lines[i]));
                    }}

                    // 触发各种事件让 Vue 检测到变化
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
                    el.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true }}));

                    // 尝试触发 Vue 的 v-model 更新
                    var event = new Event('input', {{ bubbles: true }});
                    Object.defineProperty(event, 'target', {{ value: el, enumerable: true }});
                    el.dispatchEvent(event);
                """, desc_editor)
                logger.info(f"描述已填写: {description[:50]}...")
                return

            logger.warning("未找到描述输入框")
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

    def _add_tag(self, page: ChromiumPage, tag_name: str):
        """通过点击 #话题 按钮添加真实标签"""
        try:
            logger.info(f"正在添加标签: {tag_name}")

            # 找到 #话题 按钮（.finder-tag-wrap.btn 中包含 #话题 文本的元素）
            tag_btn = None
            tag_buttons = page.eles("css:.finder-tag-wrap.btn", timeout=3)
            for btn in tag_buttons:
                if "#话题" in btn.text or "#" in btn.text:
                    tag_btn = btn
                    break

            if not tag_btn:
                logger.warning("未找到 #话题 按钮")
                return

            # 点击按钮打开标签输入弹窗
            tag_btn.click()
            self._random_delay(0.5, 1)

            # 等待标签输入弹窗出现
            # 弹窗中通常有搜索输入框
            tag_input = None
            input_selectors = [
                "css:.finder-tag-dialog input",
                "css:.tag-dialog input",
                "css:.common-dialog input[type='text']",
                "css:.modal input[type='text']",
                "css:.ant-modal input",
                "css:input[placeholder*='搜索']",
                "css:input[placeholder*='话题']",
                "css:input[placeholder*='标签']",
            ]
            for selector in input_selectors:
                try:
                    tag_input = page.ele(selector, timeout=2)
                    if tag_input:
                        logger.info(f"找到标签输入框: {selector}")
                        break
                except Exception:
                    continue

            if not tag_input:
                # 尝试通过 contenteditable 元素查找
                tag_input = page.ele("css:.finder-tag-dialog [contenteditable], .tag-dialog [contenteditable]", timeout=2)

            if tag_input:
                # 输入标签名称
                tag_input.click()
                self._random_delay(0.2, 0.3)
                tag_input.clear()
                self._human_type(tag_input, tag_name)
                self._random_delay(0.5, 1)

                # 尝试选择第一个搜索结果或按回车确认
                # 先尝试点击第一个搜索结果
                result_selectors = [
                    "css:.finder-tag-dialog .tag-item:first-child",
                    "css:.tag-dialog .tag-item:first-child",
                    "css:.common-option-list-wrap .option-item:first-child",
                    "css:.ant-select-item:first-child",
                ]
                for selector in result_selectors:
                    try:
                        result = page.ele(selector, timeout=1)
                        if result:
                            result.click()
                            logger.info(f"已选择标签: {tag_name}")
                            self._random_delay(0.3, 0.5)
                            return
                    except Exception:
                        continue

                # 如果没有搜索结果可点击，尝试按回车确认创建
                tag_input.input("\n")
                self._random_delay(0.3, 0.5)

                # 检查是否有确认按钮
                confirm_selectors = [
                    "css:.finder-tag-dialog .btn-primary",
                    "css:.tag-dialog .btn-primary",
                    "css:.modal .btn-primary:contains('确定')",
                    "css:.modal .btn-primary:contains('确认')",
                ]
                for selector in confirm_selectors:
                    try:
                        confirm_btn = page.ele(selector, timeout=1)
                        if confirm_btn:
                            confirm_btn.click()
                            logger.info(f"已确认标签: {tag_name}")
                            self._random_delay(0.3, 0.5)
                            return
                    except Exception:
                        continue

                logger.info(f"标签 '{tag_name}' 已输入")
            else:
                logger.warning("未找到标签输入弹窗")

        except Exception as e:
            logger.warning(f"添加标签失败: {e}")

    def _add_drama_link(self, page: ChromiumPage, drama_name: str):
        """添加视频号剧集链接"""
        try:
            logger.info(f"正在添加剧集链接: {drama_name}")

            # 找到链接区域并点击
            link_wrap = page.ele("css:.post-link-wrap .link-display-wrap", timeout=3)
            if not link_wrap:
                link_wrap = page.ele("css:.link-display-wrap", timeout=2)

            if not link_wrap:
                logger.warning("未找到链接区域")
                return

            link_wrap.click()
            self._random_delay(0.5, 1)

            # 等待链接选项列表出现，查找"视频号剧集"选项
            drama_option = None
            option_selectors = [
                "css:.link-option-item:contains('剧集')",
                "css:.link-list-options .link-option-item",
                "css:.link-option-item",
            ]

            # 先尝试直接找包含"剧集"文字的选项
            try:
                drama_option = page.ele("text:视频号剧集", timeout=2)
            except Exception:
                pass

            if not drama_option:
                # 遍历所有选项找剧集
                options = page.eles("css:.link-option-item", timeout=2)
                for opt in options:
                    if "剧集" in opt.text:
                        drama_option = opt
                        break

            if not drama_option:
                # 可能需要滚动查看更多选项
                try:
                    options_container = page.ele("css:.link-list-options", timeout=2)
                    if options_container:
                        page.run_js("arguments[0].scrollTop = arguments[0].scrollHeight", options_container)
                        self._random_delay(0.3, 0.5)
                        drama_option = page.ele("text:视频号剧集", timeout=2)
                except Exception:
                    pass

            if drama_option:
                drama_option.click()
                self._random_delay(0.5, 1)

                # 等待剧集选择弹窗出现
                # 弹窗中通常有搜索框和剧集列表
                search_input = None
                search_selectors = [
                    "css:.drama-dialog input",
                    "css:.common-dialog input[type='text']",
                    "css:.modal input[type='text']",
                    "css:input[placeholder*='剧集']",
                    "css:input[placeholder*='搜索']",
                ]
                for selector in search_selectors:
                    try:
                        search_input = page.ele(selector, timeout=2)
                        if search_input:
                            break
                    except Exception:
                        continue

                if search_input:
                    # 输入剧集名称搜索
                    search_input.click()
                    self._random_delay(0.2, 0.3)
                    search_input.clear()
                    self._human_type(search_input, drama_name)
                    self._random_delay(0.5, 1)

                    # 选择第一个匹配的剧集
                    result_selectors = [
                        "css:.drama-item:first-child",
                        "css:.common-option-list-wrap .option-item:first-child",
                        "css:.ant-select-item:first-child",
                        "css:.modal .list-item:first-child",
                    ]
                    for selector in result_selectors:
                        try:
                            result = page.ele(selector, timeout=2)
                            if result:
                                result.click()
                                logger.info(f"已选择剧集: {drama_name}")
                                self._random_delay(0.3, 0.5)

                                # 点击确认按钮
                                confirm_selectors = [
                                    "css:.modal .btn-primary:contains('确定')",
                                    "css:.modal .btn-primary:contains('确认')",
                                    "css:.dialog .btn-primary",
                                    "css:.ant-modal .ant-btn-primary",
                                ]
                                for confirm_sel in confirm_selectors:
                                    try:
                                        confirm_btn = page.ele(confirm_sel, timeout=1)
                                        if confirm_btn:
                                            confirm_btn.click()
                                            logger.info(f"已确认剧集链接: {drama_name}")
                                            return
                                    except Exception:
                                        continue
                                return
                        except Exception:
                            continue

                    logger.warning(f"未找到匹配的剧集: {drama_name}")
                else:
                    logger.warning("未找到剧集搜索输入框")
            else:
                logger.warning("未找到'视频号剧集'选项")

        except Exception as e:
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
        # 等待按钮可用（视频处理完成后才可点击），最多等 60 秒
        for attempt in range(30):
            try:
                # 遍历所有 primary 按钮，找到文本为"发表"且未禁用的
                buttons = page.eles("css:.weui-desktop-btn_primary", timeout=2)
                for btn in buttons:
                    if btn.text.strip() == "发表":
                        btn_class = btn.attr("class") or ""
                        if "disabled" not in btn_class:
                            btn.click()
                            logger.info("已点击发表按钮")
                            self._random_delay(1, 2)
                            return
                        else:
                            if attempt % 5 == 0:
                                logger.info(f"发表按钮暂不可用，等待中... ({attempt + 1}/30)")
                            break
            except Exception:
                pass
            self._random_delay(1, 2)
        raise Exception("未找到可用的发表按钮（等待超时）")

    def _confirm_publish(self, page: ChromiumPage):
        """确认发表（处理可能的确认弹窗）"""
        self._random_delay(1, 2)

        # 检查是否有确认弹窗
        confirm_selectors = [
            "css:.weui-desktop-btn_primary:contains('确定')",
            "css:.weui-desktop-btn_primary:contains('确认')",
            "css:.weui-desktop-btn_primary:contains('继续')",
            "text:确定",
            "text:确认发表",
            "text:继续发表",
        ]
        for selector in confirm_selectors:
            try:
                confirm_btn = page.ele(selector, timeout=2)
                if confirm_btn:
                    confirm_btn.click()
                    logger.info("已确认发表")
                    self._random_delay(1, 2)
                    break
            except Exception:
                continue

        # 等待发表成功
        success_indicators = [
            "text:发表成功",
            "text:已发表",
            "css:.weui-desktop-toast:contains('成功')",
        ]
        for selector in success_indicators:
            try:
                success = page.ele(selector, timeout=5)
                if success:
                    logger.info("发表成功")
                    return
            except Exception:
                continue

        # 检查是否已跳转到作品管理页面
        if "post/list" in page.url or "content" in page.url:
            logger.info("已跳转到作品管理页面，发表可能成功")
        else:
            logger.warning("未检测到明确的发表成功状态")

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
