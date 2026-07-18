import tempfile
import unittest
import gc
from pathlib import Path

from src.publishing.weixin.dao import WeixinDAO
from src.publishing.weixin.schemas import TaskStatus


class WeixinDAOTests(unittest.TestCase):
    def test_delete_account_removes_account_tasks_and_schedules(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            dao = WeixinDAO(str(db_path))
            account_id = dao.create_account("to-delete")
            dao.create_task(account_id=account_id, video_path="C:/tmp/a.mp4")
            dao.create_schedule(account_id=account_id, video_paths=["C:/tmp/a.mp4"], interval_minutes=30)

            self.assertTrue(dao.delete_account(account_id))

            conn = dao._get_conn()
            try:
                account_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM accounts WHERE id = ?", (account_id,)
                ).fetchone()["cnt"]
                task_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM upload_tasks WHERE account_id = ?", (account_id,)
                ).fetchone()["cnt"]
                schedule_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM schedules WHERE account_id = ?", (account_id,)
                ).fetchone()["cnt"]
            finally:
                conn.close()
                gc.collect()

            self.assertEqual(0, account_count)
            self.assertEqual(0, task_count)
            self.assertEqual(0, schedule_count)

    def test_clear_upload_history_skips_active_tasks(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            dao = WeixinDAO(str(db_path))
            account_id = dao.create_account("history")
            old_task_id = dao.create_task(account_id=account_id, video_path="C:/tmp/old.mp4")
            active_task_id = dao.create_task(account_id=account_id, video_path="C:/tmp/active.mp4")
            dao.update_task_status(active_task_id, TaskStatus.UPLOADING)

            result = dao.clear_upload_history()

            self.assertEqual(1, result["deleted"])
            self.assertEqual(1, result["skipped_active"])
            self.assertIsNone(dao.get_task(old_task_id))
            self.assertIsNotNone(dao.get_task(active_task_id))

    def test_invalidate_sibling_accounts_expires_same_wechat_id(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            dao = WeixinDAO(str(db_path))
            from src.publishing.weixin.schemas import AccountStatus

            a1 = dao.create_account("slot1")
            a2 = dao.create_account("slot2")
            a3 = dao.create_account("other")
            cookie1 = cookies_dir / "a1.json"
            cookie2 = cookies_dir / "a2.json"
            cookie1.write_text("[]", encoding="utf-8")
            cookie2.write_text("[]", encoding="utf-8")
            with dao._get_conn() as conn:
                conn.execute(
                    "UPDATE accounts SET cookie_path=?, wechat_id=?, status=? WHERE id=?",
                    (str(cookie1), "sphSAME", AccountStatus.ACTIVE.value, a1),
                )
                conn.execute(
                    "UPDATE accounts SET cookie_path=?, wechat_id=?, status=? WHERE id=?",
                    (str(cookie2), "sphSAME", AccountStatus.ACTIVE.value, a2),
                )
                conn.execute(
                    "UPDATE accounts SET wechat_id=?, status=? WHERE id=?",
                    ("sphOTHER", AccountStatus.ACTIVE.value, a3),
                )

            expired = dao.invalidate_sibling_accounts(a2, "sphSAME")

            self.assertEqual([a1], expired)
            self.assertEqual(AccountStatus.EXPIRED.value, dao.get_account(a1)["status"])
            self.assertEqual(AccountStatus.ACTIVE.value, dao.get_account(a2)["status"])
            self.assertEqual(AccountStatus.ACTIVE.value, dao.get_account(a3)["status"])
            self.assertFalse(cookie1.exists())
            self.assertTrue(cookie2.exists())

    def test_invalidate_sibling_skips_active_upload(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            dao = WeixinDAO(str(db_path))
            from src.publishing.weixin.schemas import AccountStatus

            a1 = dao.create_account("slot1")
            a2 = dao.create_account("slot2")
            cookie1 = cookies_dir / "a1.json"
            cookie1.write_text("[]", encoding="utf-8")
            with dao._get_conn() as conn:
                conn.execute(
                    "UPDATE accounts SET cookie_path=?, wechat_id=?, status=? WHERE id=?",
                    (str(cookie1), "sphSAME", AccountStatus.ACTIVE.value, a1),
                )
                conn.execute(
                    "UPDATE accounts SET wechat_id=?, status=? WHERE id=?",
                    ("sphSAME", AccountStatus.ACTIVE.value, a2),
                )
            task_id = dao.create_task(account_id=a1, video_path=str(Path(tmp) / "v.mp4"))
            dao.update_task_status(task_id, TaskStatus.UPLOADING)

            expired = dao.invalidate_sibling_accounts(a2, "sphSAME")

            self.assertEqual([], expired)
            self.assertEqual(AccountStatus.ACTIVE.value, dao.get_account(a1)["status"])
            self.assertTrue(cookie1.exists())

    def test_find_superseding_account_by_newer_login(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            dao = WeixinDAO(str(db_path))
            from src.publishing.weixin.schemas import AccountStatus

            old_id = dao.create_account("old")
            new_id = dao.create_account("new")
            dao.update_account_status(old_id, AccountStatus.ACTIVE, wechat_id="sphX")
            dao.update_account_status(new_id, AccountStatus.ACTIVE, wechat_id="sphX")

            superseder = dao.find_superseding_account(old_id)
            self.assertIsNotNone(superseder)
            self.assertEqual(new_id, superseder["id"])
            self.assertIsNone(dao.find_superseding_account(new_id))

    def test_delete_accounts_batch_and_skip_active(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            dao = WeixinDAO(str(db_path))

            a1 = dao.create_account("ok1")
            a2 = dao.create_account("busy")
            a3 = dao.create_account("ok2")
            for aid in (a1, a2, a3):
                acc = dao.get_account(aid)
                Path(acc["cookie_path"]).parent.mkdir(parents=True, exist_ok=True)
                Path(acc["cookie_path"]).write_text("[]", encoding="utf-8")

            busy_task = dao.create_task(account_id=a2, video_path="C:/tmp/busy.mp4")
            dao.update_task_status(busy_task, TaskStatus.UPLOADING)

            result = dao.delete_accounts([a1, a2, a3, 99999, a1])

            self.assertEqual([a1, a3], result["deleted"])
            self.assertEqual([a2], result["skipped_active"])
            self.assertEqual([99999], result["not_found"])
            self.assertIsNone(dao.get_account(a1))
            self.assertIsNotNone(dao.get_account(a2))
            self.assertIsNone(dao.get_account(a3))


if __name__ == "__main__":
    unittest.main()
