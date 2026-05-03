"""
浏览器池管理

管理 DrissionPage 浏览器实例，避免同时打开过多浏览器
"""

import threading
import time
from contextlib import contextmanager
from queue import Queue, Empty
from typing import Optional

from DrissionPage import ChromiumOptions, ChromiumPage

from .config import WeixinConfig
from src.core.logger import logger


class BrowserPool:
    """浏览器实例池"""

    def __init__(self, max_instances: int = None):
        self.max_instances = max_instances or WeixinConfig.MAX_BROWSER_INSTANCES
        self._pool: Queue = Queue(maxsize=self.max_instances)
        self._active_count = 0
        self._lock = threading.Lock()
        self._created_pages: list[ChromiumPage] = []

    def _create_browser(self, user_data_dir: Optional[str] = None) -> ChromiumPage:
        """创建新的浏览器实例"""
        options = ChromiumOptions()
        if WeixinConfig.BROWSER_PATH:
            options.set_browser_path(WeixinConfig.BROWSER_PATH)
        if WeixinConfig.BROWSER_HEADLESS:
            options.headless()
        options.set_timeouts(page_load=WeixinConfig.PAGE_LOAD_TIMEOUT)
        # 反检测设置
        options.set_argument("--disable-blink-features=AutomationControlled")
        options.set_argument("--disable-infobars")
        options.set_argument("--no-sandbox")
        if user_data_dir:
            options.set_user_data_path(user_data_dir)
        page = ChromiumPage(options)
        self._created_pages.append(page)
        return page

    @contextmanager
    def acquire(self, user_data_dir: Optional[str] = None):
        """
        获取浏览器实例（上下文管理器）

        用法:
            with browser_pool.acquire() as page:
                page.get("https://example.com")
        """
        page = None
        acquired = False
        try:
            # 尝试从池中获取
            try:
                page = self._pool.get_nowait()
                acquired = True
            except Empty:
                pass

            if page is None:
                with self._lock:
                    if self._active_count < self.max_instances:
                        page = self._create_browser(user_data_dir)
                        self._active_count += 1
                        acquired = True

            if page is None:
                # 池已满，等待释放
                logger.info("浏览器池已满，等待可用实例...")
                page = self._pool.get(timeout=120)
                acquired = True

            yield page

        finally:
            if acquired and page is not None:
                try:
                    self._pool.put_nowait(page)
                except Exception:
                    # 队列满，关闭浏览器
                    self._close_page(page)

    def _close_page(self, page: ChromiumPage):
        """关闭浏览器页面"""
        try:
            page.quit()
            if page in self._created_pages:
                self._created_pages.remove(page)
            with self._lock:
                self._active_count = max(0, self._active_count - 1)
        except Exception as e:
            logger.warning(f"关闭浏览器失败: {e}")

    def close_all(self):
        """关闭所有浏览器实例"""
        while not self._pool.empty():
            try:
                page = self._pool.get_nowait()
                self._close_page(page)
            except Empty:
                break
        # 关闭可能遗漏的
        for page in self._created_pages[:]:
            self._close_page(page)
        logger.info("所有浏览器实例已关闭")


# 全局浏览器池实例
browser_pool = BrowserPool()


def get_browser_for_account(account_cookie_path: str) -> ChromiumPage:
    """
    为指定账号创建独立的浏览器实例（不使用池）

    用于首次扫码登录等需要独立浏览器的场景
    """
    options = ChromiumOptions()
    if WeixinConfig.BROWSER_PATH:
        options.set_browser_path(WeixinConfig.BROWSER_PATH)
    if WeixinConfig.BROWSER_HEADLESS:
        options.headless()
    options.set_timeouts(page_load=WeixinConfig.PAGE_LOAD_TIMEOUT)
    options.set_argument("--disable-blink-features=AutomationControlled")
    options.set_argument("--disable-infobars")
    options.set_argument("--no-sandbox")
    # 使用独立的用户数据目录实现会话隔离
    user_data_dir = str(
        WeixinConfig.COOKIES_DIR / f"profile_{hash(account_cookie_path)}"
    )
    options.set_user_data_path(user_data_dir)
    page = ChromiumPage(options)
    return page
