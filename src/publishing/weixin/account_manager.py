"""
账号管理模块

处理视频号账号的登录、Cookie 持久化、自动登录
"""

import json
import time
from pathlib import Path
from typing import Optional

from DrissionPage import ChromiumPage

from .browser import get_browser_for_account
from .config import WeixinConfig
from .dao import WeixinDAO
from .schemas import AccountStatus
from src.core.logger import logger


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
                page.quit()
                return {"status": "success", "message": "登录成功"}
            else:
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                page.quit()
                return {"status": "failed", "message": login_result["message"]}

        except Exception as e:
            logger.error(f"登录失败: {e}")
            self.dao.update_account_status(account_id, AccountStatus.ERROR)
            return {"status": "error", "message": str(e)}

    def auto_login(self, account_id: int) -> bool:
        """
        自动登录（使用已保存的 Cookie）

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

        try:
            page = get_browser_for_account(cookie_path)
            self._load_cookies(page, cookie_path)
            page.get(WeixinConfig.CHANNELS_URL)
            time.sleep(3)

            result = self._check_login_status(page)
            if result["success"]:
                self.dao.update_account_status(account_id, AccountStatus.ACTIVE)
                logger.info(f"自动登录成功: {account['name']}")
                page.quit()
                return True
            else:
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                logger.warn(f"Cookie 已过期: {account['name']}")
                page.quit()
                return False

        except Exception as e:
            logger.error(f"自动登录失败: {e}")
            self.dao.update_account_status(account_id, AccountStatus.ERROR)
            return False

    def refresh_login(self, account_id: int) -> dict:
        """刷新登录状态"""
        account = self.dao.get_account(account_id)
        if not account:
            raise ValueError(f"账号不存在: {account_id}")

        # 先尝试自动登录
        if self.auto_login(account_id):
            return {"status": "success", "message": "自动登录成功"}
        else:
            # 自动登录失败，触发扫码登录
            return self.login_with_qrcode(account_id)

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
                return {"success": False, "message": result["error"]}

            # 每次检查后打印状态（每 5 次检查打印一次）
            if check_count % 5 == 0:
                elapsed = int(time.time() - start_time)
                logger.info(f"等待扫码中... 已等待 {elapsed} 秒")

            time.sleep(2)

        return {"success": False, "message": "扫码超时，请重试"}

    def _check_login_status(self, page: ChromiumPage) -> dict:
        """
        检查登录状态

        Returns:
            dict: {"success": bool, "error": str|None}
        """
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

        except Exception:
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
