"""
视频上传引擎

核心自动化逻辑：登录 → 上传视频 → 填写信息 → 发布
"""

import json
import random
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

            # 3. 填写标题、描述、标签
            self.dao.update_task_status(task_id, TaskStatus.FILLING)
            self._fill_metadata(page, metadata)

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
        logger.info("正在打开发布页面...")
        page.get(WeixinConfig.POST_CREATE_URL)
        self._random_delay(2, 4)

        # 确认页面加载完成
        create_btn = page.ele("css:input[type='file'], .upload-btn, .post-create", timeout=10)
        if not create_btn:
            # 尝试点击"发布"按钮进入发布页面
            post_btn = page.ele("text:发布视频", timeout=5)
            if post_btn:
                post_btn.click()
                self._random_delay(2, 3)

    def _upload_file(self, page: ChromiumPage, file_path: str):
        """通过 file input 上传视频文件"""
        logger.info(f"正在上传文件: {file_path}")

        # 方法1: 找到 input[type=file] 并注入文件路径
        file_input = page.ele("css:input[type=file]", timeout=10)
        if file_input:
            file_input.input(file_path)
            logger.info("文件路径已注入到 input 元素")
            return

        # 方法2: 点击上传按钮触发文件选择，然后注入
        upload_area = page.ele("css:.upload-area, .upload-btn, .upload-wrapper", timeout=5)
        if upload_area:
            upload_area.click()
            self._random_delay(1, 2)
            file_input = page.ele("css:input[type=file]", timeout=5)
            if file_input:
                file_input.input(file_path)
                return

        raise Exception("无法找到文件上传入口")

    def _wait_for_upload_complete(self, page: ChromiumPage):
        """等待视频上传和处理完成"""
        logger.info("等待视频上传完成...")
        start_time = time.time()

        while time.time() - start_time < WeixinConfig.UPLOAD_TIMEOUT:
            # 检查上传进度
            progress = page.ele("css:.progress, .upload-progress, .el-progress", timeout=2)
            if progress:
                text = progress.text
                # 尝试提取百分比
                percent_match = text.match(r"(\d+)%")
                if percent_match:
                    percent = int(percent_match.group(1))
                    logger.debug(f"上传进度: {percent}%")
                    if percent >= 100:
                        break

            # 检查是否出现"上传成功"或编辑区域
            success_indicator = page.ele(
                "text:上传成功, css:.upload-success, css:.video-preview, css:.editor-area",
                timeout=3,
            )
            if success_indicator:
                logger.info("视频上传完成")
                self._random_delay(1, 2)
                return

            # 检查是否有错误提示
            error = page.ele("css:.error-message, .upload-error", timeout=1)
            if error:
                raise Exception(f"上传出错: {error.text}")

            time.sleep(3)

        raise Exception(f"视频上传超时（{WeixinConfig.UPLOAD_TIMEOUT}秒）")

    def _fill_metadata(self, page: ChromiumPage, metadata: VideoMetadata):
        """填写标题、描述、标签"""
        logger.info("正在填写视频信息...")

        # 填写标题
        if metadata.title:
            title_input = page.ele(
                "css:input[placeholder*=标题], textarea[placeholder*=标题], .title-input",
                timeout=5,
            )
            if title_input:
                title_input.clear()
                self._human_type(title_input, metadata.title)
                logger.info(f"标题已填写: {metadata.title}")

        # 填写描述/正文
        if metadata.description:
            desc_input = page.ele(
                "css:textarea[placeholder*=描述], textarea[placeholder*=正文], .desc-input, .content-editor",
                timeout=5,
            )
            if desc_input:
                desc_input.clear()
                self._human_type(desc_input, metadata.description)
                logger.info("描述已填写")

        # 添加标签
        if metadata.tags:
            for tag in metadata.tags[:5]:  # 视频号最多5个标签
                self._add_tag(page, tag)

        self._random_delay(1, 2)

    def _add_tag(self, page: ChromiumPage, tag: str):
        """添加单个标签"""
        # 尝试找到标签输入框
        tag_input = page.ele(
            "css:input[placeholder*=标签], input[placeholder*=话题], .tag-input",
            timeout=3,
        )
        if tag_input:
            tag_input.clear()
            self._human_type(tag_input, tag)
            self._random_delay(0.5, 1)
            # 按回车确认标签
            tag_input.input("\n")
            self._random_delay(0.3, 0.8)
            logger.info(f"标签已添加: #{tag}")
        else:
            # 尝试在描述中添加 # 标签
            logger.warning(f"未找到标签输入框，跳过标签: {tag}")

    def _set_schedule_time(self, page: ChromiumPage, scheduled_at: datetime):
        """设置定时发布时间"""
        logger.info(f"设置定时发布: {scheduled_at}")

        # 点击定时发布选项
        schedule_option = page.ele("text:定时发布", timeout=5)
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
        """点击发布按钮"""
        logger.info("正在发布...")
        publish_btn = page.ele("text:发布", timeout=5)
        if publish_btn:
            publish_btn.click()
            self._random_delay(1, 2)
        else:
            raise Exception("未找到发布按钮")

    def _confirm_publish(self, page: ChromiumPage):
        """确认发布（处理可能的确认弹窗）"""
        # 检查是否有确认弹窗
        confirm_btn = page.ele("text:确定, text:确认发布, text:继续发布", timeout=5)
        if confirm_btn:
            confirm_btn.click()
            self._random_delay(1, 2)

        # 等待发布成功
        success = page.ele("text:发布成功, text:已发布", timeout=15)
        if success:
            logger.info("发布成功")
        else:
            # 检查是否已跳转到作品管理页面
            if "post/list" in page.url or "content" in page.url:
                logger.info("已跳转到作品管理页面，发布可能成功")
            else:
                logger.warning("未检测到明确的发布成功状态")

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
