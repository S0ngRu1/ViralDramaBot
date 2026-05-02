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
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
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
            """)

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
    ) -> int:
        """创建上传任务"""
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO upload_tasks
                (account_id, video_path, title, description, tags, status, metadata_source, scheduled_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (account_id, video_path, title, description, tags_json, TaskStatus.PENDING.value, metadata_source, scheduled_at, now),
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
