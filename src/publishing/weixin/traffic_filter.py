"""
视频流量筛选：按观察期 + 低播放筛选候选，支持人工删稿。
扫描在后台线程执行，前端轮询结果。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .account_manager import AccountManager, get_account_lock
from .channel_post import ChannelPost, TrafficCandidate
from .config import WeixinConfig
from .dao import WeixinDAO
from .post_delete import delete_post
from .post_list import fetch_posts
from .schemas import AccountStatus
from src.core.logger import logger

REASON_LOW_VIEWS = "low_views"

DEFAULT_GRACE_PERIOD_HOURS = 48
DEFAULT_MIN_VIEWS = 1000


def merge_traffic_candidates(
    posts: List[ChannelPost],
    grace_period_hours: int,
    min_views: int,
    now: Optional[datetime] = None,
) -> List[TrafficCandidate]:
    """筛选：发表超过观察期且播放量 < 阈值。"""
    now = now or datetime.now()
    cutoff = now - timedelta(hours=max(0, int(grace_period_hours)))
    min_views = int(min_views)

    results: List[TrafficCandidate] = []
    for post in posts:
        if post.published_at > cutoff:
            continue
        if post.view_count >= min_views:
            continue
        results.append(
            TrafficCandidate(
                post_id=post.post_id,
                title=post.title,
                published_at=post.published_at,
                view_count=post.view_count,
                reasons=[REASON_LOW_VIEWS],
            )
        )

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
    """单账号流量筛选与删稿（扫描后台执行）。"""

    def __init__(
        self,
        dao: Optional[WeixinDAO] = None,
        account_manager: Optional[AccountManager] = None,
    ):
        self.dao = dao or WeixinDAO()
        self.account_manager = account_manager or AccountManager(self.dao)
        self._jobs_lock = threading.Lock()
        # account_id -> job state
        self._scan_jobs: Dict[int, dict] = {}

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

    def get_scan_status(self, account_id: int) -> dict:
        with self._jobs_lock:
            job = self._scan_jobs.get(int(account_id))
            if not job:
                return {
                    "status": "idle",
                    "is_scanning": False,
                    "message": "暂无扫描任务",
                    "scanned": 0,
                    "candidates": [],
                }
            return dict(job)

    def _set_job(self, account_id: int, **fields) -> dict:
        with self._jobs_lock:
            job = self._scan_jobs.setdefault(int(account_id), {})
            job.update(fields)
            return dict(job)

    def start_scan(
        self,
        account_id: int,
        grace_period_hours: int = DEFAULT_GRACE_PERIOD_HOURS,
        min_views: int = DEFAULT_MIN_VIEWS,
    ) -> dict:
        account_id = int(account_id)
        skip = self._precheck(account_id)
        if skip:
            return {
                "status": "error",
                "is_scanning": False,
                "message": skip,
                "scanned": 0,
                "candidates": [],
            }

        with self._jobs_lock:
            current = self._scan_jobs.get(account_id) or {}
            if current.get("is_scanning"):
                return {
                    "status": "running",
                    "is_scanning": True,
                    "message": "扫描已在进行中",
                    "scanned": current.get("scanned") or 0,
                    "candidates": current.get("candidates") or [],
                }
            # 在锁内标记 running，避免连点启动多个 worker。
            # 重扫期间保留旧 candidates，供删稿白名单与前端展示，直到新结果写回。
            job = self._scan_jobs.setdefault(account_id, {})
            job.update(
                {
                    "status": "running",
                    "is_scanning": True,
                    "message": "后台扫描中…",
                    "started_at": datetime.now().isoformat(),
                    "finished_at": None,
                }
            )

        thread = threading.Thread(
            target=self._scan_worker,
            args=(account_id, grace_period_hours, min_views),
            name=f"TrafficScan-{account_id}",
            daemon=True,
        )
        thread.start()
        return {
            "status": "started",
            "is_scanning": True,
            "message": "扫描已在后台启动",
            "scanned": 0,
            "candidates": [],
        }

    def _scan_worker(
        self,
        account_id: int,
        grace_period_hours: int,
        min_views: int,
    ) -> None:
        try:
            result = self.scan(
                account_id,
                grace_period_hours=grace_period_hours,
                min_views=min_views,
            )
            self._set_job(
                account_id,
                status=result.get("status") or "error",
                is_scanning=False,
                message=result.get("message") or "",
                finished_at=datetime.now().isoformat(),
                scanned=result.get("scanned") or 0,
                candidates=result.get("candidates") or [],
            )
        except Exception as e:
            logger.exception("流量筛选扫描失败 account=%s", account_id)
            self._set_job(
                account_id,
                status="error",
                is_scanning=False,
                message=str(e),
                finished_at=datetime.now().isoformat(),
                scanned=0,
                candidates=[],
            )

    def scan(
        self,
        account_id: int,
        grace_period_hours: int = DEFAULT_GRACE_PERIOD_HOURS,
        min_views: int = DEFAULT_MIN_VIEWS,
    ) -> dict:
        skip = self._precheck(account_id)
        if skip:
            return {
                "status": "error",
                "message": skip,
                "scanned": 0,
                "candidates": [],
            }

        lock = get_account_lock(account_id)
        if not lock.acquire(blocking=False):
            return {
                "status": "error",
                "message": "账号锁被占用（可能正在上传或登录）",
                "scanned": 0,
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
                    "candidates": [],
                }
            # 仅复检 Cookie，勿刷新 last_login_at（避免打乱同微信号槽位）
            self.dao.update_account_status(
                account_id, AccountStatus.ACTIVE, touch_login_at=False
            )

            posts = fetch_posts(page)
            candidates = merge_traffic_candidates(
                posts,
                grace_period_hours=grace_period_hours,
                min_views=min_views,
            )
            return {
                "status": "success",
                "message": "ok",
                "scanned": len(posts),
                "candidates": [candidate_to_dict(c) for c in candidates],
            }
        except Exception as e:
            logger.exception("流量筛选扫描失败 account=%s", account_id)
            return {
                "status": "error",
                "message": str(e),
                "scanned": 0,
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

        # 仅允许删除最近一次扫描命中的候选，降低误删/脚本乱删面
        status = self.get_scan_status(account_id)
        allowed = {
            str(c.get("post_id") or "").strip()
            for c in (status.get("candidates") or [])
            if isinstance(c, dict) and c.get("post_id")
        }
        if not allowed:
            return {
                "status": "error",
                "message": "请先扫描候选后再删除",
                "deleted": [],
                "failed": [{"post_id": pid, "error": "no_scan_candidates"} for pid in ids],
            }
        rejected = [pid for pid in ids if pid not in allowed]
        ids = [pid for pid in ids if pid in allowed]
        rejected_failed = [
            {"post_id": pid, "error": "not_in_candidates"} for pid in rejected
        ]
        if not ids:
            return {
                "status": "error",
                "message": "所选视频不在最近扫描候选中",
                "deleted": [],
                "failed": rejected_failed,
            }

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
            self.dao.update_account_status(
                account_id, AccountStatus.ACTIVE, touch_login_at=False
            )

            for pid in ids:
                try:
                    ok = delete_post(page, pid)
                    if ok:
                        deleted.append(pid)
                    else:
                        failed.append({"post_id": pid, "error": "delete_failed"})
                except Exception as e:
                    failed.append({"post_id": pid, "error": str(e)})

            all_failed = rejected_failed + failed
            return {
                "status": "success" if deleted and not all_failed else ("partial" if deleted else "error"),
                "message": f"删除成功 {len(deleted)}，失败 {len(all_failed)}",
                "deleted": deleted,
                "failed": all_failed,
            }
        except Exception as e:
            logger.exception("流量筛选删稿失败 account=%s", account_id)
            return {
                "status": "error",
                "message": str(e),
                "deleted": deleted,
                "failed": rejected_failed + (failed or [{"post_id": pid, "error": str(e)} for pid in ids]),
            }
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            lock.release()
