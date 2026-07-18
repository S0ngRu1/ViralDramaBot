"""
概览页近 N 小时流量快照：账号播放汇总 + 按描述首段剧集链接排行。

post_list 无结构化剧集字段；上传时描述为「{剧集链接} {原描述}」或仅剧集链接，
因此取描述空白符分割后的第一段作为剧集键。
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
from .schemas import AccountStatus
from src.core.logger import logger

SNAPSHOT_FILENAME = "traffic_snapshot.json"
DEFAULT_HOURS = 24


def filter_posts_in_window(
    posts: List[ChannelPost],
    hours: int,
    now: Optional[datetime] = None,
) -> List[ChannelPost]:
    now = now or datetime.now()
    cutoff = now - timedelta(hours=max(0, int(hours)))
    return [p for p in posts if p.published_at >= cutoff]


def extract_drama_link_from_description(description: Optional[str]) -> Optional[str]:
    """从视频描述提取剧集链接：空白符分割后的第一个非空字符串。"""
    text = (description or "").strip()
    if not text:
        return None
    token = text.split(None, 1)[0].strip()
    return token or None


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
    account_id: int,
) -> Dict[str, dict]:
    """按描述首段剧集链接聚合（单账号），后续再跨账号合并。"""
    result: Dict[str, dict] = {}
    for post in posts:
        drama = extract_drama_link_from_description(post.title)
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
    """拉取平台播放量，并从作品描述首段提取剧集链接生成概览快照。"""

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
        prev_accounts = {
            int(a["account_id"]): a
            for a in (self.get_snapshot().get("accounts") or [])
            if a.get("account_id") is not None
        }

        for account in accounts:
            account_id = int(account["id"])
            name = account.get("name") or f"#{account_id}"
            try:
                posts_window, drama_part = self._scan_account(account, hours=hours, now=now)
                account_rows.append(aggregate_account_stats(account_id, name, posts_window))
                if drama_part:
                    drama_partials.append(drama_part)
            except Exception as e:
                err_text = str(e)
                logger.warning(f"账号 {account_id} 流量扫描失败: {e}")
                errors.append({"account_id": account_id, "account_name": name, "error": err_text})
                # 锁冲突：沿用上次缓存，勿写入假 0 播放
                if "账号锁被占用" in err_text and account_id in prev_accounts:
                    cached = dict(prev_accounts[account_id])
                    cached["account_name"] = name
                    account_rows.append(cached)
                    continue
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

            # 只拉近 N 小时窗口附近的页，避免全量历史翻页
            cutoff = now - timedelta(hours=max(0, int(hours)))
            posts = fetch_posts(page, published_after=cutoff)
            posts_window = filter_posts_in_window(posts, hours=hours, now=now)
            drama_part = aggregate_drama_stats(posts_window, account_id)
            return posts_window, drama_part
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            lock.release()
