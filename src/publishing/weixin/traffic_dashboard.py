"""
概览页近 N 小时流量快照：账号播放汇总 + 按剧集链接（drama_link）排行。
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .account_manager import AccountManager, get_account_lock
from .channel_post import ChannelPost
from .config import WeixinConfig
from .dao import WeixinDAO
from .post_list import fetch_posts
from .schemas import AccountStatus, TaskStatus
from src.core.logger import logger

SNAPSHOT_FILENAME = "traffic_snapshot.json"
DEFAULT_HOURS = 24
MATCH_WINDOW = timedelta(hours=2)
TASK_TIME_BUFFER = timedelta(hours=6)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def filter_posts_in_window(
    posts: List[ChannelPost],
    hours: int,
    now: Optional[datetime] = None,
) -> List[ChannelPost]:
    now = now or datetime.now()
    cutoff = now - timedelta(hours=max(0, int(hours)))
    return [p for p in posts if p.published_at >= cutoff]


def normalize_drama_link(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    return text or None


def task_match_time(task: dict) -> Optional[datetime]:
    """本地任务用于匹配的时间：优先 completed_at，其次 created_at。"""
    return _parse_iso(task.get("completed_at")) or _parse_iso(task.get("created_at"))


def match_posts_to_drama_tasks(
    posts: List[ChannelPost],
    tasks: List[dict],
    match_window: timedelta = MATCH_WINDOW,
) -> Dict[str, str]:
    """
    一对一匹配：平台作品 post_id -> drama_link。

    仅使用有 drama_link 的任务；按 |published_at - task_time| 升序贪心配对，
    且差值不超过 match_window。
    """
    indexed = []
    for i, task in enumerate(tasks):
        drama = normalize_drama_link(task.get("drama_link"))
        t_at = task_match_time(task)
        if not drama or t_at is None:
            continue
        indexed.append((i, drama, t_at))

    candidates: List[Tuple[float, str, int, str]] = []
    for post in posts:
        for i, drama, t_at in indexed:
            delta = abs((post.published_at - t_at).total_seconds())
            if delta <= match_window.total_seconds():
                candidates.append((delta, post.post_id, i, drama))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))

    mapping: Dict[str, str] = {}
    used_posts: set = set()
    used_task_idx: set = set()
    for _delta, post_id, task_idx, drama in candidates:
        if post_id in used_posts or task_idx in used_task_idx:
            continue
        mapping[post_id] = drama
        used_posts.add(post_id)
        used_task_idx.add(task_idx)
    return mapping


def aggregate_account_stats(
    account_id: int,
    account_name: str,
    posts: List[ChannelPost],
) -> dict:
    views = [int(p.view_count or 0) for p in posts]
    return {
        "account_id": account_id,
        "account_name": account_name,
        "post_count": len(posts),
        "total_views": sum(views),
        "max_views": max(views) if views else 0,
    }


def aggregate_drama_stats(
    posts: List[ChannelPost],
    post_to_drama: Dict[str, str],
    account_id: int,
) -> Dict[str, dict]:
    """返回 drama_link -> 部分聚合（单账号），后续再跨账号合并。"""
    result: Dict[str, dict] = {}
    for post in posts:
        drama = post_to_drama.get(post.post_id)
        if not drama:
            continue
        row = result.get(drama)
        if not row:
            row = {
                "drama_link": drama,
                "post_count": 0,
                "total_views": 0,
                "account_ids": set(),
            }
            result[drama] = row
        row["post_count"] += 1
        row["total_views"] += int(post.view_count or 0)
        row["account_ids"].add(account_id)
    return result


def build_snapshot_from_account_results(
    hours: int,
    account_rows: List[dict],
    drama_partials: List[Dict[str, dict]],
    errors: List[dict],
    refreshed_at: Optional[datetime] = None,
) -> dict:
    accounts = sorted(
        account_rows,
        key=lambda r: (int(r.get("total_views") or 0), int(r.get("post_count") or 0)),
        reverse=True,
    )
    merged: Dict[str, dict] = {}
    for part in drama_partials:
        for drama, row in part.items():
            cur = merged.get(drama)
            if not cur:
                merged[drama] = {
                    "drama_link": drama,
                    "post_count": int(row["post_count"]),
                    "total_views": int(row["total_views"]),
                    "account_ids": set(row.get("account_ids") or []),
                }
            else:
                cur["post_count"] += int(row["post_count"])
                cur["total_views"] += int(row["total_views"])
                cur["account_ids"].update(row.get("account_ids") or [])

    dramas = []
    for drama, row in merged.items():
        dramas.append(
            {
                "drama_link": row["drama_link"],
                "post_count": row["post_count"],
                "total_views": row["total_views"],
                "account_count": len(row["account_ids"]),
            }
        )
    dramas.sort(key=lambda r: (r["total_views"], r["post_count"]), reverse=True)
    dramas = dramas[:10]

    top_account = accounts[0] if accounts and accounts[0].get("total_views", 0) > 0 else None
    return {
        "status": "success",
        "hours": hours,
        "refreshed_at": (refreshed_at or datetime.now()).isoformat(),
        "top_account": top_account,
        "accounts": accounts,
        "dramas": dramas,
        "errors": errors,
    }


class TrafficDashboardService:
    """拉取平台播放量并与本地 drama_link 任务匹配，生成概览快照。"""

    def __init__(
        self,
        dao: Optional[WeixinDAO] = None,
        account_manager: Optional[AccountManager] = None,
    ):
        self.dao = dao or WeixinDAO()
        self.account_manager = account_manager or AccountManager(self.dao)
        self._lock = threading.Lock()
        self._refreshing = False
        self._refresh_started_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._snapshot_path = WeixinConfig.DATA_DIR / SNAPSHOT_FILENAME

    def get_snapshot(self) -> dict:
        path = self._snapshot_path
        refreshing = False
        started = None
        with self._lock:
            refreshing = self._refreshing
            started = self._refresh_started_at
            last_error = self._last_error
        if not path.exists():
            return {
                "status": "empty",
                "message": "暂无流量缓存，请点击刷新",
                "is_refreshing": refreshing,
                "refresh_started_at": started,
                "last_error": last_error,
                "hours": DEFAULT_HOURS,
                "refreshed_at": None,
                "top_account": None,
                "accounts": [],
                "dramas": [],
                "errors": [],
            }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "status": "error",
                "message": f"读取流量缓存失败: {e}",
                "is_refreshing": refreshing,
                "refresh_started_at": started,
                "last_error": last_error,
                "hours": DEFAULT_HOURS,
                "refreshed_at": None,
                "top_account": None,
                "accounts": [],
                "dramas": [],
                "errors": [],
            }
        data["status"] = data.get("status") or "success"
        data["is_refreshing"] = refreshing
        data["refresh_started_at"] = started
        data["last_error"] = last_error
        return data

    def start_refresh(self, hours: int = DEFAULT_HOURS) -> dict:
        with self._lock:
            if self._refreshing:
                return {
                    "status": "running",
                    "message": "流量刷新已在进行中",
                    "refresh_started_at": self._refresh_started_at,
                }
            self._refreshing = True
            self._refresh_started_at = datetime.now().isoformat()
            self._last_error = None

        thread = threading.Thread(
            target=self._refresh_worker,
            args=(max(1, int(hours)),),
            name="TrafficDashboardRefresh",
            daemon=True,
        )
        thread.start()
        return {
            "status": "started",
            "message": "流量刷新已在后台启动",
            "refresh_started_at": self._refresh_started_at,
        }

    def _refresh_worker(self, hours: int) -> None:
        try:
            snapshot = self.refresh_traffic_snapshot(hours=hours)
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            # 落盘时去掉不可序列化字段（已无）
            self._snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "流量快照已更新: accounts=%s dramas=%s errors=%s",
                len(snapshot.get("accounts") or []),
                len(snapshot.get("dramas") or []),
                len(snapshot.get("errors") or []),
            )
        except Exception as e:
            logger.exception("流量快照刷新失败")
            with self._lock:
                self._last_error = str(e)
        finally:
            with self._lock:
                self._refreshing = False

    def refresh_traffic_snapshot(self, hours: int = DEFAULT_HOURS) -> dict:
        now = datetime.now()
        accounts = [
            a
            for a in self.dao.get_all_accounts()
            if a.get("status") == AccountStatus.ACTIVE.value
        ]
        account_rows: List[dict] = []
        drama_partials: List[Dict[str, dict]] = []
        errors: List[dict] = []

        for account in accounts:
            account_id = int(account["id"])
            name = account.get("name") or f"#{account_id}"
            try:
                posts_window, drama_part = self._scan_account(account, hours=hours, now=now)
                account_rows.append(aggregate_account_stats(account_id, name, posts_window))
                if drama_part:
                    drama_partials.append(drama_part)
            except Exception as e:
                logger.warning(f"账号 {account_id} 流量扫描失败: {e}")
                errors.append({"account_id": account_id, "account_name": name, "error": str(e)})
                account_rows.append(
                    {
                        "account_id": account_id,
                        "account_name": name,
                        "post_count": 0,
                        "total_views": 0,
                        "max_views": 0,
                    }
                )

        return build_snapshot_from_account_results(
            hours=hours,
            account_rows=account_rows,
            drama_partials=drama_partials,
            errors=errors,
            refreshed_at=now,
        )

    def _scan_account(
        self, account: dict, hours: int, now: datetime
    ) -> Tuple[List[ChannelPost], Dict[str, dict]]:
        account_id = int(account["id"])
        cookie_path = account.get("cookie_path") or ""
        if not Path(cookie_path).exists():
            raise RuntimeError("Cookie 文件不存在")

        lock = get_account_lock(account_id)
        if not lock.acquire(blocking=False):
            raise RuntimeError("账号锁被占用")

        page = None
        try:
            page = AccountManager._create_headless_browser(cookie_path, proxy_url=None)
            self.account_manager._load_cookies(page, cookie_path)
            page.get(WeixinConfig.POST_LIST_URL)
            login = self.account_manager._check_login_status(page)
            if not login.get("success"):
                self.dao.update_account_status(account_id, AccountStatus.EXPIRED)
                raise RuntimeError(login.get("error") or "Cookie 已失效")

            posts = fetch_posts(page)
            posts_window = filter_posts_in_window(posts, hours=hours, now=now)

            # 本地 completed + drama_link 任务（时间窗口加缓冲）
            tasks = self.dao.get_tasks(
                account_id=account_id,
                status=TaskStatus.COMPLETED,
                limit=500,
            )
            cutoff = now - timedelta(hours=hours) - TASK_TIME_BUFFER
            drama_tasks = []
            for t in tasks:
                if not normalize_drama_link(t.get("drama_link")):
                    continue
                t_at = task_match_time(t)
                if t_at is None:
                    continue
                if t_at < cutoff:
                    continue
                drama_tasks.append(t)

            mapping = match_posts_to_drama_tasks(posts_window, drama_tasks)
            drama_part = aggregate_drama_stats(posts_window, mapping, account_id)
            return posts_window, drama_part
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            lock.release()
