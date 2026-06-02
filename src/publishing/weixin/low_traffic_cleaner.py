"""
低流量视频自动检测与删稿
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from DrissionPage import ChromiumPage

from .account_manager import AccountManager, get_account_lock
from .batch_queue import batch_upload_queue
from .config import WeixinConfig
from .dao import WeixinDAO
from .post_delete import delete_post
from .post_list import fetch_posts
from .schemas import AccountStatus
from src.core.logger import logger


class LowTrafficCleaner:
    """按规则扫描已发视频并删除低播放条目"""

    def __init__(
        self,
        dao: Optional[WeixinDAO] = None,
        account_manager: Optional[AccountManager] = None,
    ):
        self.dao = dao or WeixinDAO()
        self.account_manager = account_manager or AccountManager(self.dao)

    def should_skip_account(self, account_id: int) -> Optional[str]:
        if self.dao.has_active_task(account_id):
            return "账号有进行中的上传任务"
        if batch_upload_queue.is_account_busy(account_id):
            return "账号有进行中的批量上传"
        account = self.dao.get_account(account_id)
        if not account:
            return "账号不存在"
        if account["status"] != AccountStatus.ACTIVE.value:
            return f"账号状态非 active: {account['status']}"
        if not Path(account.get("cookie_path") or "").exists():
            return "Cookie 文件不存在"
        return None

    def run_for_account(self, account_id: int) -> dict:
        """
        对单个账号执行一轮低流量检测与删稿。

        Returns:
            dict: scanned, candidates, deleted, failed, skipped_reason
        """
        rule = self.dao.get_low_traffic_rule(account_id)
        stats = {
            "account_id": account_id,
            "scanned": 0,
            "candidates": 0,
            "deleted": 0,
            "failed": 0,
            "skipped_reason": None,
        }

        if not rule.get("enabled"):
            stats["skipped_reason"] = "规则未启用"
            return stats

        skip = self.should_skip_account(account_id)
        if skip:
            stats["skipped_reason"] = skip
            logger.info(f"[低流量清理] 账号 {account_id} 跳过: {skip}")
            return stats

        lock = get_account_lock(account_id)
        if not lock.acquire(blocking=False):
            stats["skipped_reason"] = "账号锁被占用"
            return stats
        try:
            return self._run_locked(account_id, rule, stats)
        finally:
            lock.release()

    def _run_locked(self, account_id: int, rule: dict, stats: dict) -> dict:
        account = self.dao.get_account(account_id)
        cookie_path = account["cookie_path"]
        page = None
        try:
            page = AccountManager._create_headless_browser(cookie_path, proxy_url=None)
            self.account_manager._load_cookies(page, cookie_path)
            page.get(WeixinConfig.POST_LIST_URL)
            login = self.account_manager._check_login_status(page)
            if not login.get("success"):
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                stats["skipped_reason"] = login.get("error") or "Cookie 已失效"
                return stats
            self.dao.update_account_status(account_id, AccountStatus.ACTIVE)

            posts = fetch_posts(page)
            stats["scanned"] = len(posts)

            grace_hours = int(rule["grace_period_hours"])
            min_views = int(rule["min_views"])
            cutoff = datetime.now() - timedelta(hours=grace_hours)

            for post in posts:
                if self.dao.is_post_already_deleted(account_id, post.post_id):
                    continue
                if post.published_at > cutoff:
                    continue
                if post.view_count >= min_views:
                    continue

                stats["candidates"] += 1
                pub_iso = post.published_at.isoformat()
                ok = delete_post(page, post.post_id, post.title)
                if ok:
                    stats["deleted"] += 1
                    self.dao.add_cleanup_log(
                        account_id=account_id,
                        post_id=post.post_id,
                        title=post.title,
                        published_at=pub_iso,
                        view_count=post.view_count,
                        grace_period_hours=grace_hours,
                        min_views=min_views,
                        action="deleted",
                    )
                    logger.info(
                        f"[低流量清理] 已删除 account={account_id} "
                        f"post={post.post_id} views={post.view_count} title={post.title[:30]!r}"
                    )
                    time.sleep(1.0)
                else:
                    stats["failed"] += 1
                    self.dao.add_cleanup_log(
                        account_id=account_id,
                        post_id=post.post_id,
                        title=post.title,
                        published_at=pub_iso,
                        view_count=post.view_count,
                        grace_period_hours=grace_hours,
                        min_views=min_views,
                        action="failed",
                        error_msg="平台删稿失败",
                    )

            return stats
        except Exception as e:
            logger.error(f"[低流量清理] 账号 {account_id} 异常: {e}")
            stats["skipped_reason"] = str(e)
            return stats
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

    def run_all_enabled(self) -> list[dict]:
        """遍历所有启用规则的账号"""
        results = []
        for rule in self.dao.list_enabled_low_traffic_rules():
            account_id = rule["account_id"]
            logger.info(f"[低流量清理] 开始账号 {account_id}")
            results.append(self.run_for_account(account_id))
        return results
