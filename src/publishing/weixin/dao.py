"""
数据访问层

管理账号和上传任务的 SQLite 持久化
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import WeixinConfig
from .schemas import AccountStatus, TaskStatus


class WeixinDAO:
    """视频号数据访问对象"""

    def __init__(self, db_path: Optional[str] = None):
        WeixinConfig.ensure_dirs()
        self.db_path = db_path or str(WeixinConfig.DB_PATH)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    wechat_id TEXT,
                    status TEXT NOT NULL DEFAULT 'expired',
                    cookie_path TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS upload_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    video_path TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    tags TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    metadata_source TEXT NOT NULL DEFAULT 'manual',
                    scheduled_at TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_msg TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    proxy_ip TEXT,
                    proxy_location TEXT,
                    proxy_profile_id INTEGER,
                    location_label TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
                );

                CREATE TABLE IF NOT EXISTS favorite_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proxy_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    scheme TEXT NOT NULL DEFAULT 'http',
                    host TEXT NOT NULL DEFAULT '127.0.0.1',
                    port INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT,
                    last_ip TEXT,
                    last_country TEXT,
                    last_region TEXT,
                    last_city TEXT,
                    last_isp TEXT,
                    last_check_error TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    video_paths TEXT NOT NULL,
                    cron_expr TEXT,
                    interval_minutes INTEGER,
                    titles TEXT,
                    descriptions TEXT,
                    tags TEXT,
                    metadata_source TEXT NOT NULL DEFAULT 'manual',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    next_run_at TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status ON upload_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_account ON upload_tasks(account_id);
                CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
                CREATE INDEX IF NOT EXISTS idx_proxy_profiles_enabled ON proxy_profiles(enabled, id);
            """)
            # 轻量迁移：老库的 upload_tasks 缺少代理审计列，需要补齐。
            # SQLite 没有「ADD COLUMN IF NOT EXISTS」语法，所以先看 PRAGMA 再决定。
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(upload_tasks)").fetchall()
            }
            for col_name, col_def in (
                ("proxy_ip", "TEXT"),
                ("proxy_location", "TEXT"),
                ("proxy_profile_id", "INTEGER"),
                ("location_label", "TEXT"),
            ):
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE upload_tasks ADD COLUMN {col_name} {col_def}")

    # ==================== 账号操作 ====================

    def create_account(self, name: str) -> int:
        """创建账号，返回账号ID"""
        now = datetime.now().isoformat()
        cookie_path = str(WeixinConfig.COOKIES_DIR / f"{name}_{now.replace(':', '-')}.json")
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO accounts (name, status, cookie_path, created_at) VALUES (?, ?, ?, ?)",
                (name, AccountStatus.EXPIRED.value, cookie_path, now),
            )
            return cursor.lastrowid

    def get_account(self, account_id: int) -> Optional[dict]:
        """获取单个账号"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_accounts(self) -> list[dict]:
        """获取所有账号"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_account_status(
        self, account_id: int, status: AccountStatus, wechat_id: Optional[str] = None
    ):
        """更新账号状态"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            if status == AccountStatus.ACTIVE:
                conn.execute(
                    "UPDATE accounts SET status = ?, wechat_id = COALESCE(?, wechat_id), last_login_at = ? WHERE id = ?",
                    (status.value, wechat_id, now, account_id),
                )
            else:
                conn.execute(
                    "UPDATE accounts SET status = ? WHERE id = ?",
                    (status.value, account_id),
                )

    def delete_account(self, account_id: int) -> bool:
        """删除账号及其Cookie文件"""
        account = self.get_account(account_id)
        if not account:
            return False
        # 删除Cookie文件
        cookie_path = account.get("cookie_path")
        if cookie_path:
            Path(cookie_path).unlink(missing_ok=True)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM upload_tasks WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        return True

    def get_account_count(self) -> int:
        """获取账号总数"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()
            return row["cnt"]

    # ==================== 代理 Profile 操作 ====================

    def create_proxy_profile(
        self,
        name: str,
        scheme: str,
        host: str,
        port: int,
        enabled: bool = True,
    ) -> int:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO proxy_profiles
                (name, scheme, host, port, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (name, scheme, host, int(port), 1 if enabled else 0, now),
            )
            return cursor.lastrowid

    def list_proxy_profiles(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM proxy_profiles ORDER BY id ASC").fetchall()
            return [dict(r) for r in rows]

    def get_proxy_profile(self, profile_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_proxy_profile(self, profile_id: int, **fields) -> bool:
        allowed = {"name", "scheme", "host", "port", "enabled"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_proxy_profile(profile_id) is not None
        if "enabled" in updates:
            updates["enabled"] = 1 if updates["enabled"] else 0
        if "port" in updates:
            updates["port"] = int(updates["port"])
        assignments = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [profile_id]
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"UPDATE proxy_profiles SET {assignments} WHERE id = ?", params
            )
            return cursor.rowcount > 0

    def delete_proxy_profile(self, profile_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM proxy_profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    def update_proxy_profile_check_result(
        self,
        profile_id: int,
        ip: Optional[str],
        country: Optional[str],
        region: Optional[str],
        city: Optional[str],
        isp: Optional[str],
        error: Optional[str],
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE proxy_profiles
                SET last_checked_at = ?, last_ip = ?, last_country = ?, last_region = ?,
                    last_city = ?, last_isp = ?, last_check_error = ?
                WHERE id = ?""",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    ip,
                    country,
                    region,
                    city,
                    isp,
                    error,
                    profile_id,
                ),
            )

    def get_first_enabled_proxy_profile(self) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_profiles WHERE enabled = 1 ORDER BY id ASC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # ==================== 常用发表位置 ====================

    def create_favorite_location(self, name: str) -> int:
        """新增常用位置。name 唯一 —— 已存在的直接返回旧 id。"""
        now = datetime.now().isoformat()
        name = (name or "").strip()
        if not name:
            raise ValueError("位置名称不能为空")
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM favorite_locations WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO favorite_locations (name, created_at) VALUES (?, ?)",
                (name, now),
            )
            return cursor.lastrowid

    def list_favorite_locations(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM favorite_locations ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_favorite_location(self, location_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM favorite_locations WHERE id = ?", (location_id,)
            )
            return cursor.rowcount > 0

    # ==================== 任务操作 ====================

    def create_task(
        self,
        account_id: int,
        video_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata_source: str = "manual",
        scheduled_at: Optional[str] = None,
        proxy_profile_id: Optional[int] = None,
        location_label: Optional[str] = None,
    ) -> int:
        """创建上传任务"""
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO upload_tasks
                (account_id, video_path, title, description, tags, status, metadata_source,
                 scheduled_at, created_at, proxy_profile_id, location_label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    video_path,
                    title,
                    description,
                    tags_json,
                    TaskStatus.PENDING.value,
                    metadata_source,
                    scheduled_at,
                    now,
                    proxy_profile_id,
                    location_label,
                ),
            )
            return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[dict]:
        """获取单个任务"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM upload_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row:
                d = dict(row)
                if d.get("tags"):
                    d["tags"] = json.loads(d["tags"])
                return d
            return None

    def get_tasks(
        self,
        account_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
    ) -> list[dict]:
        """获取任务列表"""
        query = "SELECT * FROM upload_tasks WHERE 1=1"
        params = []
        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("tags"):
                    d["tags"] = json.loads(d["tags"])
                result.append(d)
            return result

    def get_pending_tasks(self, account_id: Optional[int] = None) -> list[dict]:
        """获取待处理的任务"""
        return self.get_tasks(account_id=account_id, status=TaskStatus.PENDING)

    def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_msg: Optional[str] = None,
    ):
        """更新任务状态"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            if status in (TaskStatus.UPLOADING, TaskStatus.PROCESSING, TaskStatus.FILLING, TaskStatus.PUBLISHING):
                conn.execute(
                    "UPDATE upload_tasks SET status = ?, started_at = COALESCE(started_at, ?) WHERE id = ?",
                    (status.value, now, task_id),
                )
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                conn.execute(
                    "UPDATE upload_tasks SET status = ?, completed_at = ?, error_msg = ? WHERE id = ?",
                    (status.value, now, error_msg, task_id),
                )
            else:
                conn.execute(
                    "UPDATE upload_tasks SET status = ? WHERE id = ?",
                    (status.value, task_id),
                )

    def update_task_proxy(
        self,
        task_id: int,
        proxy_ip: Optional[str],
        proxy_location: Optional[str],
    ) -> None:
        """记录该任务实际使用的代理出口 IP 和归属地，便于后续审计。"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE upload_tasks SET proxy_ip = ?, proxy_location = ? WHERE id = ?",
                (proxy_ip, proxy_location, task_id),
            )

    def increment_retry(self, task_id: int) -> int:
        """增加重试次数，返回当前重试次数"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE upload_tasks SET retry_count = retry_count + 1, status = ? WHERE id = ?",
                (TaskStatus.PENDING.value, task_id),
            )
            row = conn.execute(
                "SELECT retry_count FROM upload_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return row["retry_count"] if row else 0

    def delete_task(self, task_id: int) -> bool:
        """删除任务"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM upload_tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    def delete_tasks(self, task_ids: list[int]) -> dict:
        """
        批量删除任务。跳过活动状态（uploading/processing/filling/publishing）的任务，
        避免误删正在跑的浏览器自动化任务而导致状态错乱。

        Returns:
            dict: {
                "deleted_ids": [int],           # 实际被删除的 id
                "skipped_active": [int],        # 因处于活动状态而被跳过的 id
                "not_found": [int],             # 数据库里不存在的 id
            }
        """
        if not task_ids:
            return {"deleted_ids": [], "skipped_active": [], "not_found": []}

        unique_ids = list({int(i) for i in task_ids})
        active_statuses = (
            TaskStatus.UPLOADING.value,
            TaskStatus.PROCESSING.value,
            TaskStatus.FILLING.value,
            TaskStatus.PUBLISHING.value,
        )

        with self._get_conn() as conn:
            placeholders = ",".join("?" for _ in unique_ids)
            rows = conn.execute(
                f"SELECT id, status FROM upload_tasks WHERE id IN ({placeholders})",
                unique_ids,
            ).fetchall()
            existing = {row["id"]: row["status"] for row in rows}

            deletable = [i for i, st in existing.items() if st not in active_statuses]
            skipped_active = [i for i, st in existing.items() if st in active_statuses]
            not_found = [i for i in unique_ids if i not in existing]

            if deletable:
                del_placeholders = ",".join("?" for _ in deletable)
                conn.execute(
                    f"DELETE FROM upload_tasks WHERE id IN ({del_placeholders})",
                    deletable,
                )

        return {
            "deleted_ids": deletable,
            "skipped_active": skipped_active,
            "not_found": not_found,
        }

    def has_active_task(self, account_id: int) -> bool:
        """检查指定账号是否有正在执行的上传任务（UPLOADING/PROCESSING/FILLING/PUBLISHING）"""
        active_statuses = (
            TaskStatus.UPLOADING.value,
            TaskStatus.PROCESSING.value,
            TaskStatus.FILLING.value,
            TaskStatus.PUBLISHING.value,
        )
        with self._get_conn() as conn:
            placeholders = ",".join("?" for _ in active_statuses)
            row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM upload_tasks WHERE account_id = ? AND status IN ({placeholders})",
                (account_id, *active_statuses),
            ).fetchone()
            return row["cnt"] > 0

    # ==================== 定时计划操作 ====================

    def create_schedule(
        self,
        account_id: int,
        video_paths: list[str],
        cron_expr: Optional[str] = None,
        interval_minutes: Optional[int] = None,
        titles: Optional[list[str]] = None,
        descriptions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        metadata_source: str = "manual",
    ) -> int:
        """创建定时计划"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO schedules
                (account_id, video_paths, cron_expr, interval_minutes, titles, descriptions, tags, metadata_source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    json.dumps(video_paths, ensure_ascii=False),
                    cron_expr,
                    interval_minutes,
                    json.dumps(titles, ensure_ascii=False) if titles else None,
                    json.dumps(descriptions, ensure_ascii=False) if descriptions else None,
                    json.dumps(tags, ensure_ascii=False) if tags else None,
                    metadata_source,
                    now,
                ),
            )
            return cursor.lastrowid

    def get_active_schedules(self) -> list[dict]:
        """获取所有活跃的定时计划"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE is_active = 1"
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for key in ["video_paths", "titles", "descriptions", "tags"]:
                    if d.get(key):
                        d[key] = json.loads(d[key])
                result.append(d)
            return result

    def update_schedule_next_run(self, schedule_id: int, next_run_at: str):
        """更新定时计划下次执行时间"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE schedules SET next_run_at = ? WHERE id = ?",
                (next_run_at, schedule_id),
            )

    def deactivate_schedule(self, schedule_id: int):
        """停用定时计划"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE schedules SET is_active = 0 WHERE id = ?", (schedule_id,)
            )

    def delete_schedule(self, schedule_id: int) -> bool:
        """删除定时计划"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            return cursor.rowcount > 0
