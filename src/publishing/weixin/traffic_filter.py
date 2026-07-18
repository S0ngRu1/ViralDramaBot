"""
视频流量筛选：低播放 OR 作品优化建议 → 候选列表 / 人工删稿
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .account_manager import AccountManager, get_account_lock
from .channel_post import ChannelPost, TrafficCandidate
from .config import WeixinConfig
from .dao import WeixinDAO
from .notification import OptimizeTipNotice, fetch_optimize_tip_notices
from .post_delete import delete_post
from .post_list import fetch_posts
from .schemas import AccountStatus
from src.core.logger import logger

REASON_LOW_VIEWS = "low_views"
REASON_OPTIMIZE_TIP = "optimize_tip"


def merge_traffic_candidates(
    posts: List[ChannelPost],
    tips: List[OptimizeTipNotice],
    grace_period_hours: int,
    min_views: int,
    now: Optional[datetime] = None,
) -> List[TrafficCandidate]:
    """
    OR 合并：
    - 发表超过观察期且播放量 < 阈值
    - 或消息中心有「作品优化建议」
    """
    now = now or datetime.now()
    cutoff = now - timedelta(hours=max(0, int(grace_period_hours)))
    min_views = int(min_views)

    by_id: Dict[str, TrafficCandidate] = {}

    post_map = {p.post_id: p for p in posts}

    for post in posts:
        if post.published_at > cutoff:
            continue
        if post.view_count >= min_views:
            continue
        cand = by_id.get(post.post_id)
        if not cand:
            cand = TrafficCandidate(
                post_id=post.post_id,
                title=post.title,
                published_at=post.published_at,
                view_count=post.view_count,
                reasons=[],
            )
            by_id[post.post_id] = cand
        if REASON_LOW_VIEWS not in cand.reasons:
            cand.reasons.append(REASON_LOW_VIEWS)

    for tip in tips:
        post = post_map.get(tip.post_id)
        cand = by_id.get(tip.post_id)
        if not cand:
            cand = TrafficCandidate(
                post_id=tip.post_id,
                title=(post.title if post else None) or tip.title or tip.post_id,
                published_at=(post.published_at if post else None) or tip.published_at,
                view_count=post.view_count if post else None,
                reasons=[],
            )
            by_id[tip.post_id] = cand
        else:
            if (not cand.title or cand.title == cand.post_id) and tip.title:
                cand.title = tip.title
            if cand.published_at is None and tip.published_at is not None:
                cand.published_at = tip.published_at
            if cand.view_count is None and post is not None:
                cand.view_count = post.view_count
        if REASON_OPTIMIZE_TIP not in cand.reasons:
            cand.reasons.append(REASON_OPTIMIZE_TIP)

    results = list(by_id.values())
    results.sort(
        key=lambda c: (c.published_at or datetime.min, c.post_id),
        reverse=True,
    )
    return results


def candidate_to_dict(c: TrafficCandidate) -> dict:
    return {
        "post_id": c.post_id,
        "title": c.title,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "view_count": c.view_count,
        "reasons": list(c.reasons),
    }


class TrafficFilterService:
    """单账号流量筛选与删稿"""

    def __init__(
        self,
        dao: Optional[WeixinDAO] = None,
        account_manager: Optional[AccountManager] = None,
    ):
        self.dao = dao or WeixinDAO()
        self.account_manager = account_manager or AccountManager(self.dao)

    def _precheck(self, account_id: int) -> Optional[str]:
        if self.dao.has_active_task(account_id):
            return "账号有进行中的上传任务"
        account = self.dao.get_account(account_id)
        if not account:
            return "账号不存在"
        if account["status"] != AccountStatus.ACTIVE.value:
            return f"账号状态非 active: {account['status']}"
        if not Path(account.get("cookie_path") or "").exists():
            return "Cookie 文件不存在"
        return None

    def scan(
        self,
        account_id: int,
        grace_period_hours: int = 72,
        min_views: int = 100,
    ) -> dict:
        skip = self._precheck(account_id)
        if skip:
            return {
                "status": "error",
                "message": skip,
                "scanned": 0,
                "optimize_tips": 0,
                "candidates": [],
            }

        lock = get_account_lock(account_id)
        if not lock.acquire(blocking=False):
            return {
                "status": "error",
                "message": "账号锁被占用（可能正在上传或登录）",
                "scanned": 0,
                "optimize_tips": 0,
                "candidates": [],
            }

        page = None
        try:
            account = self.dao.get_account(account_id)
            cookie_path = account["cookie_path"]
            page = AccountManager._create_headless_browser(cookie_path, proxy_url=None)
            self.account_manager._load_cookies(page, cookie_path)
            page.get(WeixinConfig.POST_LIST_URL)
            login = self.account_manager._check_login_status(page)
            if not login.get("success"):
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                return {
                    "status": "error",
                    "message": login.get("error") or "Cookie 已失效，请重新登录",
                    "scanned": 0,
                    "optimize_tips": 0,
                    "candidates": [],
                }
            self.dao.update_account_status(account_id, AccountStatus.ACTIVE)

            posts = fetch_posts(page)
            tips = fetch_optimize_tip_notices(page)
            candidates = merge_traffic_candidates(
                posts,
                tips,
                grace_period_hours=grace_period_hours,
                min_views=min_views,
            )
            return {
                "status": "success",
                "message": "ok",
                "scanned": len(posts),
                "optimize_tips": len(tips),
                "candidates": [candidate_to_dict(c) for c in candidates],
            }
        except Exception as e:
            logger.exception(f"流量筛选扫描失败 account={account_id}")
            return {
                "status": "error",
                "message": str(e),
                "scanned": 0,
                "optimize_tips": 0,
                "candidates": [],
            }
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            lock.release()

    def delete_posts(self, account_id: int, post_ids: List[str]) -> dict:
        skip = self._precheck(account_id)
        if skip:
            return {"status": "error", "message": skip, "deleted": [], "failed": []}

        ids = [str(x).strip() for x in (post_ids or []) if str(x).strip()]
        if not ids:
            return {"status": "error", "message": "未选择要删除的视频", "deleted": [], "failed": []}

        lock = get_account_lock(account_id)
        if not lock.acquire(blocking=False):
            return {
                "status": "error",
                "message": "账号锁被占用（可能正在上传或登录）",
                "deleted": [],
                "failed": [],
            }

        page = None
        deleted: List[str] = []
        failed: List[dict] = []
        try:
            account = self.dao.get_account(account_id)
            cookie_path = account["cookie_path"]
            page = AccountManager._create_headless_browser(cookie_path, proxy_url=None)
            self.account_manager._load_cookies(page, cookie_path)
            page.get(WeixinConfig.POST_LIST_URL)
            login = self.account_manager._check_login_status(page)
            if not login.get("success"):
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                return {
                    "status": "error",
                    "message": login.get("error") or "Cookie 已失效，请重新登录",
                    "deleted": [],
                    "failed": [{"post_id": pid, "error": "cookie_expired"} for pid in ids],
                }
            self.dao.update_account_status(account_id, AccountStatus.ACTIVE)

            for pid in ids:
                try:
                    ok = delete_post(page, pid)
                    if ok:
                        deleted.append(pid)
                    else:
                        failed.append({"post_id": pid, "error": "delete_failed"})
                except Exception as e:
                    failed.append({"post_id": pid, "error": str(e)})

            return {
                "status": "success" if deleted and not failed else ("partial" if deleted else "error"),
                "message": f"删除成功 {len(deleted)}，失败 {len(failed)}",
                "deleted": deleted,
                "failed": failed,
            }
        except Exception as e:
            logger.exception(f"流量筛选删稿失败 account={account_id}")
            return {
                "status": "error",
                "message": str(e),
                "deleted": deleted,
                "failed": failed or [{"post_id": pid, "error": str(e)} for pid in ids],
            }
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            lock.release()
