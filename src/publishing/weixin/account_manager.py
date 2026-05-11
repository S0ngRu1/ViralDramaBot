"""
账号管理模块

处理视频号账号的登录、Cookie 持久化、自动登录
"""

import json
import time
import threading
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from DrissionPage import ChromiumPage

from .browser import get_browser_for_account, get_browser_for_channels_viewer
from .config import WeixinConfig
from DrissionPage import ChromiumOptions
from .dao import WeixinDAO
from .schemas import AccountStatus
from src.core.logger import logger

# Cookie 轮询间隔（秒）
COOKIE_CHECK_INTERVAL_SECONDS = 3600  # 每小时检查一次

# Per-account 锁：防止 Cookie 检查与上传任务同时操作同一账号的浏览器 user_data_dir
_account_locks: dict[int, threading.Lock] = {}
_account_locks_guard = threading.Lock()


def get_account_lock(account_id: int) -> threading.Lock:
    """获取指定账号的锁（线程安全的懒创建）"""
    lock = _account_locks.get(account_id)
    if lock is None:
        with _account_locks_guard:
            lock = _account_locks.get(account_id)
            if lock is None:
                lock = threading.Lock()
                _account_locks[account_id] = lock
    return lock


class AccountManager:
    """视频号账号管理器"""

    def __init__(self, dao: Optional[WeixinDAO] = None):
        self.dao = dao or WeixinDAO()

    def create_account(self, name: str) -> dict:
        """创建新账号（触发扫码登录流程）"""
        if self.dao.get_account_count() >= WeixinConfig.MAX_ACCOUNTS:
            raise ValueError(f"已达到最大账号数限制 ({WeixinConfig.MAX_ACCOUNTS})")

        account_id = self.dao.create_account(name)
        account = self.dao.get_account(account_id)
        logger.info(f"账号已创建: {name} (ID: {account_id})")
        return account

    def login_with_qrcode(self, account_id: int) -> dict:
        """
        扫码登录流程

        1. 启动浏览器
        2. 打开视频号登录页
        3. 等待用户扫码
        4. 保存 Cookie
        """
        account = self.dao.get_account(account_id)
        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        self.dao.update_account_status(account_id, AccountStatus.LOGGING_IN)
        cookie_path = account["cookie_path"]

        page = None
        try:
            page = get_browser_for_account(cookie_path)
            logger.info(f"正在打开视频号登录页面...")
            page.get(WeixinConfig.LOGIN_URL)
            time.sleep(2)

            # 等待用户扫码（检测登录状态变化）
            logger.info("请使用微信扫描二维码登录...")
            login_result = self._wait_for_login(page, timeout=120)

            if login_result["success"]:
                self._save_cookies(page, cookie_path)
                # 尝试获取微信昵称
                wechat_id = self._extract_wechat_id(page)
                self.dao.update_account_status(
                    account_id, AccountStatus.ACTIVE, wechat_id
                )
                logger.info(f"账号登录成功: {account['name']}")
                return {"status": "success", "message": "登录成功"}
            else:
                msg = login_result["message"]
                if "浏览器已关闭" in msg:
                    self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                    logger.info(f"用户关闭了浏览器，取消登录: {account['name']}")
                else:
                    self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                return {"status": "failed", "message": msg}

        except Exception as e:
            logger.error(f"登录失败: {e}")
            self.dao.update_account_status(account_id, AccountStatus.ERROR)
            return {"status": "error", "message": str(e)}
        finally:
            # 确保浏览器实例被清理（用户关闭页面时 page.quit() 可能抛异常）
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

    def auto_login(self, account_id: int) -> bool:
        """
        自动登录（使用已保存的 Cookie，后台静默验证，不弹出浏览器）
        会获取 per-account 锁，防止与上传任务并发操作同一 user_data_dir。

        Returns:
            bool: 登录是否成功
        """
        lock = get_account_lock(account_id)
        with lock:
            return self._auto_login_internal(account_id)

    def _auto_login_internal(self, account_id: int) -> bool:
        """
        自动登录内部实现（不获取锁，调用方需自行持锁）

        Returns:
            bool: 登录是否成功
        """
        account = self.dao.get_account(account_id)
        if not account:
            return False

        cookie_path = account["cookie_path"]
        if not Path(cookie_path).exists():
            logger.warn(f"Cookie 文件不存在: {cookie_path}")
            self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
            return False

        page = None
        try:
            page = self._create_headless_browser(cookie_path)
            self._load_cookies(page, cookie_path)
            page.get(WeixinConfig.CHANNELS_URL)
            time.sleep(3)

            result = self._check_login_status(page)
            if result["success"]:
                self.dao.update_account_status(account_id, AccountStatus.ACTIVE)
                logger.info(f"自动登录成功: {account['name']}")
                return True
            else:
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                logger.warn(f"Cookie 已过期: {account['name']}")
                return False

        except Exception as e:
            logger.error(f"自动登录失败: {e}")
            self.dao.update_account_status(account_id, AccountStatus.ERROR)
            return False
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

    def refresh_login(self, account_id: int) -> dict:
        """刷新登录状态（仅无头检测，不弹浏览器）"""
        account = self.dao.get_account(account_id)
        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        if self.auto_login(account_id):
            return {"status": "success", "message": "登录状态正常", "need_relogin": False}
        else:
            return {"status": "expired", "message": "Cookie 已过期，需重新登录", "need_relogin": True}

    def open_channels_post_list(self, account_id: int) -> dict:
        """
        打开「视频」列表页：使用临时用户数据目录 + 注入已保存 Cookie。
        不与上传/扫码共用 profile，避免新开浏览器顶掉当前正在使用的窗口。
        """
        account = self.dao.get_account(account_id)
        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        cookie_path = account["cookie_path"]
        if not Path(cookie_path).exists():
            return {"status": "failed", "message": "Cookie 文件不存在，请先扫码登录"}

        page = None
        try:
            page = get_browser_for_channels_viewer(account_id)
            self._load_cookies(page, cookie_path)
            page.get(WeixinConfig.POST_LIST_URL)
            logger.info(f"已打开视频管理页（独立 viewer 会话）: {account['name']}")
            return {"status": "success", "message": "已打开浏览器"}
        except Exception as e:
            logger.error(f"打开视频管理页失败: {e}")
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            return {"status": "error", "message": str(e)}

    def get_account(self, account_id: int) -> Optional[dict]:
        """获取账号信息"""
        return self.dao.get_account(account_id)

    def get_all_accounts(self) -> list[dict]:
        """获取所有账号"""
        return self.dao.get_all_accounts()

    def delete_account(self, account_id: int) -> bool:
        """删除账号"""
        return self.dao.delete_account(account_id)

    def _wait_for_login(self, page: ChromiumPage, timeout: int = 120) -> dict:
        """
        等待用户扫码登录

        Returns:
            dict: {"success": bool, "message": str}
        """
        start_time = time.time()
        check_count = 0

        while time.time() - start_time < timeout:
            check_count += 1
            result = self._check_login_status(page)

            if result["success"]:
                return {"success": True, "message": "登录成功"}

            if result["error"]:
                if "浏览器已关闭" in result["error"]:
                    logger.info("检测到浏览器已关闭，停止等待扫码")
                return {"success": False, "message": result["error"]}

            # 每次检查后打印状态（每 5 次检查打印一次）
            if check_count % 5 == 0:
                elapsed = int(time.time() - start_time)
                logger.info(f"等待扫码中... 已等待 {elapsed} 秒")

            time.sleep(2)

        return {"success": False, "message": "扫码超时，请重试"}

    @staticmethod
    def _is_browser_alive(page: ChromiumPage) -> bool:
        """检查浏览器进程是否还在运行"""
        try:
            # 通过 WebSocket 连接状态判断：执行简单 JS，浏览器已断开时会抛异常
            page.run_js("1+1")
            return True
        except Exception:
            return False

    def _check_login_status(self, page: ChromiumPage) -> dict:
        """
        检查登录状态

        Returns:
            dict: {"success": bool, "error": str|None}
        """
        # 先检测浏览器是否还活着
        if not self._is_browser_alive(page):
            return {"success": False, "error": "浏览器已关闭"}

        try:
            url = page.url

            # 检查是否已离开登录页面（登录成功）
            if "channels.weixin.qq.com" in url and "/login" not in url:
                # 检查是否有用户信息元素
                user_elem = page.ele("css:.user-info, .avatar, .nickname", timeout=2)
                if user_elem:
                    return {"success": True, "error": None}
                # 备用检测：检查 cookie 中是否有关键 token
                cookies = page.cookies()
                for cookie in cookies:
                    if cookie.get("name") in ("slave_sid", "bizuin"):
                        return {"success": True, "error": None}

            # 检查页面上的错误提示
            error_text = self._detect_login_error(page)
            if error_text:
                return {"success": False, "error": error_text}

            return {"success": False, "error": None}

        except (ConnectionError, ConnectionRefusedError, ConnectionResetError,
                OSError, BrokenPipeError):
            return {"success": False, "error": "浏览器已关闭"}

        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in ("disconnected", "closed", "not reachable",
                                              "connection refused", "connection reset",
                                              "目标计算机积极拒绝", "远程主机强迫关闭")):
                return {"success": False, "error": "浏览器已关闭"}
            # 其他未知异常也可能是浏览器断开导致的，再次检测
            if not self._is_browser_alive(page):
                return {"success": False, "error": "浏览器已关闭"}
            return {"success": False, "error": None}

    def _detect_login_error(self, page: ChromiumPage) -> Optional[str]:
        """
        检测登录页面上的错误提示

        Returns:
            str: 错误信息，无错误返回 None
        """
        try:
            # 常见的错误提示关键词
            error_keywords = [
                "没有授权", "未授权", "授权失败", "登录失败",
                "二维码已过期", "已过期", "已失效",
                "异常", "错误", "失败", "无法登录",
                "账号异常", "被封禁", "被限制"
            ]

            # 尝试查找错误提示元素
            # 常见的错误提示选择器
            error_selectors = [
                "css:.error-tip", "css:.error-msg", "css:.login-error",
                "css:.qrcode-expired", "css:.tip-text", "css:.warning",
                "css:[class*='error']", "css:[class*='tip']"
            ]

            for selector in error_selectors:
                try:
                    elem = page.ele(selector, timeout=0.5)
                    if elem:
                        text = elem.text.strip()
                        if text and any(keyword in text for keyword in error_keywords):
                            return text
                except Exception:
                    continue

            # 检查页面上的所有文本节点（性能较差，作为后备方案）
            body_text = page.ele("tag:body", timeout=1)
            if body_text:
                text = body_text.text
                for keyword in error_keywords:
                    if keyword in text:
                        # 提取包含关键词的句子
                        for line in text.split('\n'):
                            if keyword in line:
                                return line.strip()[:100]  # 限制长度

            return None

        except Exception:
            return None

    @staticmethod
    def _create_headless_browser(cookie_path: str) -> ChromiumPage:
        """创建无头浏览器（用于后台 Cookie 验证，不弹窗）"""
        options = ChromiumOptions()
        if WeixinConfig.BROWSER_PATH:
            options.set_browser_path(WeixinConfig.BROWSER_PATH)
        options.headless()
        options.set_timeouts(page_load=WeixinConfig.PAGE_LOAD_TIMEOUT)
        options.set_argument("--disable-blink-features=AutomationControlled")
        options.set_argument("--no-sandbox")
        user_data_dir = str(
            WeixinConfig.COOKIES_DIR / f"profile_{hash(cookie_path)}"
        )
        options.set_user_data_path(user_data_dir)
        return ChromiumPage(options)

    def _save_cookies(self, page: ChromiumPage, cookie_path: str):
        """保存 Cookie 到文件"""
        cookies = page.cookies()
        Path(cookie_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookie 已保存: {cookie_path}")

    def _load_cookies(self, page: ChromiumPage, cookie_path: str):
        """从文件加载 Cookie"""
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        page.get(WeixinConfig.CHANNELS_URL)
        for cookie in cookies:
            page.set.cookies(cookie)
        logger.info(f"Cookie 已加载: {cookie_path}")

    def _extract_wechat_id(self, page: ChromiumPage) -> Optional[str]:
        """尝试从页面提取微信ID"""
        try:
            elem = page.ele("css:.nickname, .user-name", timeout=5)
            return elem.text if elem else None
        except Exception:
            return None

    def check_all_accounts_cookies(self) -> dict:
        """
        批量检查所有活跃账号的 Cookie 有效性
        跳过当前有上传任务正在执行的账号，避免浏览器 user_data_dir 冲突。

        Returns:
            dict: {"checked": int, "valid": int, "expired": int, "errors": int, "skipped": int}
        """
        accounts = self.dao.get_all_accounts()
        stats = {"checked": 0, "valid": 0, "expired": 0, "errors": 0, "skipped": 0}

        for account in accounts:
            # 只检查状态为 ACTIVE 的账号
            if account["status"] != AccountStatus.ACTIVE.value:
                continue

            account_id = account["id"]
            account_name = account["name"]

            # 跳过有活跃上传任务的账号，避免浏览器 user_data_dir 冲突
            if self.dao.has_active_task(account_id):
                stats["skipped"] += 1
                logger.info(f"[Cookie轮询] 账号 {account_name} 有上传任务进行中，跳过检查")
                continue

            stats["checked"] += 1

            try:
                # 使用 _auto_login_internal + per-account 锁，避免死锁
                lock = get_account_lock(account_id)
                with lock:
                    if self._auto_login_internal(account_id):
                        stats["valid"] += 1
                        logger.info(f"[Cookie轮询] 账号 {account_name} Cookie有效")
                    else:
                        stats["expired"] += 1
                        logger.warn(f"[Cookie轮询] 账号 {account_name} Cookie已过期")
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[Cookie轮询] 账号 {account_name} 检查异常: {e}")

        if stats["checked"] > 0 or stats["skipped"] > 0:
            logger.info(
                f"[Cookie轮询] 完成 — 检查 {stats['checked']} 个账号, "
                f"有效 {stats['valid']}, 过期 {stats['expired']}, 异常 {stats['errors']}, "
                f"跳过 {stats['skipped']}"
            )
        return stats


class CookieChecker:
    """后台 Cookie 轮询检查器"""

    def __init__(self, account_manager: AccountManager):
        self.account_manager = account_manager
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._lock = threading.Lock()

    def start(self, interval_seconds: int = COOKIE_CHECK_INTERVAL_SECONDS):
        """启动后台轮询"""
        with self._lock:
            if self.scheduler.running:
                return
            self.scheduler.add_job(
                self._check,
                "interval",
                seconds=interval_seconds,
                id="cookie_checker",
                replace_existing=True,
                next_run_time=None,  # 不立即执行，等间隔后再检查
            )
            self.scheduler.start()
            logger.info(f"[Cookie轮询] 已启动，间隔 {interval_seconds} 秒")

    def stop(self):
        """停止轮询"""
        with self._lock:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[Cookie轮询] 已停止")

    def _check(self):
        """执行一次检查"""
        try:
            self.account_manager.check_all_accounts_cookies()
        except Exception as e:
            logger.error(f"[Cookie轮询] 执行异常: {e}")
