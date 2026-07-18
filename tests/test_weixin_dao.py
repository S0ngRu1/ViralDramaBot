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


if __name__ == "__main__":
    unittest.main()
