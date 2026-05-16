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


def apply_weixin_proxy(
    options: ChromiumOptions,
    proxy_url: Optional[str] = None,
    bypass_hosts: Optional[list[str]] = None,
) -> ChromiumOptions:
    """
    给 Chromium 启动参数注入代理 + 可选的 bypass 列表。

    bypass_hosts: 这些域名/通配符不走代理（直连）。常用于让"视频上传 CDN"绕开代理 ——
    上传文件量大、代理通常是按流量/速度计费的瓶颈，所以走直连显著提升上传速度。
    Chromium 启动参数 `--proxy-bypass-list` 支持 `*.example.com` 这种通配符语法。
    """
    proxy = proxy_url if proxy_url is not None else WeixinConfig.proxy_url()
    if proxy:
        options.set_proxy(proxy)
        if bypass_hosts:
            bypass_str = ";".join(bypass_hosts)
            options.set_argument(f"--proxy-bypass-list={bypass_str}")
            logger.info(f"Weixin browser proxy enabled: {proxy} (bypass: {bypass_str})")
        else:
            logger.info(f"Weixin browser proxy enabled: {proxy}")
    return options


class BrowserPool:
    """浏览器实例池"""

    def __init__(self, max_instances: int = None):
        self.max_instances = max_instances or WeixinConfig.MAX_BROWSER_INSTANCES
        self._pool: Queue = Queue(maxsize=self.max_instances)
        self._active_count = 0
        self._lock = threading.Lock()
        self._created_pages: list[ChromiumPage] = []

    def _create_browser(self, user_data_dir: Optional[str] = None, proxy_url: Optional[str] = None) -> ChromiumPage:
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
        apply_weixin_proxy(options, proxy_url=proxy_url)
        if user_data_dir:
            options.set_user_data_path(user_data_dir)
        # 与 _chromium_options_with_profile 对齐：多实例并发场景下，共用默认 9222
        # 调试端口会让后启动的 Chromium 顶替前一个；auto_port 让每个实例自己挑端口。
        options.auto_port(True)
        page = ChromiumPage(options)
        self._created_pages.append(page)
        return page

    @contextmanager
    def acquire(self, user_data_dir: Optional[str] = None, proxy_url: Optional[str] = None):
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
                        page = self._create_browser(user_data_dir, proxy_url=proxy_url)
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


def _chromium_options_with_profile(
    user_data_dir: str,
    proxy_url: Optional[str] = None,
    bypass_hosts: Optional[list[str]] = None,
) -> ChromiumOptions:
    options = ChromiumOptions()
    if WeixinConfig.BROWSER_PATH:
        options.set_browser_path(WeixinConfig.BROWSER_PATH)
    if WeixinConfig.BROWSER_HEADLESS:
        options.headless()
    options.set_timeouts(page_load=WeixinConfig.PAGE_LOAD_TIMEOUT)
    options.set_argument("--disable-blink-features=AutomationControlled")
    options.set_argument("--disable-infobars")
    options.set_argument("--no-sandbox")
    # Edge：自动化使用的独立 user-data-dir 常被当成「新配置」，易弹出「在所有设备上同步浏览数据」等引导。
    # 以下为 Chromium 通用开关，可减轻（未必完全消除）；仍出现时请在 Edge「设置 → 个人资料」对该配置文件退出登录。
    options.set_argument("--no-first-run")
    options.set_argument("--disable-sync")
    options.set_argument("--disable-default-apps")
    apply_weixin_proxy(options, proxy_url=proxy_url, bypass_hosts=bypass_hosts)
    options.set_user_data_path(user_data_dir)
    # 默认未开启时多个 ChromiumPage 可能争用同一调试端口，后起的会顶替前一个窗口。
    options.auto_port(True)
    return options


def get_browser_for_account(
    account_cookie_path: str,
    proxy_url: Optional[str] = None,
    bypass_hosts: Optional[list[str]] = None,
) -> ChromiumPage:
    """
    为指定账号创建独立的浏览器实例（不使用池）

    用于首次扫码登录等需要独立浏览器的场景。
    bypass_hosts: 走代理时跳过的域名通配符（典型用法：让视频上传 CDN 走直连）。
    """
    # 使用独立的用户数据目录实现会话隔离（上传 / 扫码）
    user_data_dir = str(
        WeixinConfig.COOKIES_DIR / f"profile_{hash(account_cookie_path)}"
    )
    page = ChromiumPage(
        _chromium_options_with_profile(user_data_dir, proxy_url=proxy_url, bypass_hosts=bypass_hosts)
    )
    return page


def get_browser_for_channels_viewer(account_id: int) -> ChromiumPage:
    """
    「视频管理页」等前台浏览：每个账号固定一个 viewer 目录（不随点击无限增长）。

    使用独立 user-data-dir（viewer/account_*）且与上传用的 profile_* 分离；配合 auto_port，
    一般可与同一账号的上传任务并行（上传一个 Edge、viewer 再开一个 Edge）。
    登录态通过 Cookie 文件注入（调用方负责 load_cookies）。
    若在未关闭 viewer 的情况下再次点击「视频管理页」，同一 viewer 目录可能被占用导致启动失败，需先关掉已有 viewer 窗口。
    """
    WeixinConfig.ensure_dirs()
    viewer_dir = WeixinConfig.COOKIES_DIR / "viewer" / f"account_{account_id}"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    return ChromiumPage(_chromium_options_with_profile(str(viewer_dir)))
