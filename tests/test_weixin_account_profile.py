import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.publishing.weixin.account_manager import AccountManager
from src.publishing.weixin.config import WeixinConfig
from src.publishing.weixin.dao import WeixinDAO


class WeixinAccountProfileTests(unittest.TestCase):
    def test_create_account_without_name_uses_placeholder_and_id_cookie(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            with patch.object(WeixinConfig, "COOKIES_DIR", cookies_dir), patch.object(
                WeixinConfig, "DB_PATH", db_path
            ):
                dao = WeixinDAO(str(db_path))
                account_id = dao.create_account()
                account = dao.get_account(account_id)

            self.assertEqual(WeixinConfig.DEFAULT_ACCOUNT_NAME, account["name"])
            self.assertTrue(account["cookie_path"].endswith(f"account_{account_id}.json"))
            self.assertIsNone(account.get("avatar_url"))

    def test_update_account_profile_writes_nickname_avatar_and_uniq_id(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            with patch.object(WeixinConfig, "COOKIES_DIR", cookies_dir), patch.object(
                WeixinConfig, "DB_PATH", db_path
            ):
                dao = WeixinDAO(str(db_path))
                account_id = dao.create_account()
                self.assertTrue(
                    dao.update_account_profile(
                        account_id,
                        name="平安12386",
                        avatar_url="https://wx.qlogo.cn/finderhead/demo/0",
                        wechat_id="sph0EsWCBF86AZF",
                    )
                )
                account = dao.get_account(account_id)

            self.assertEqual("平安12386", account["name"])
            self.assertEqual("https://wx.qlogo.cn/finderhead/demo/0", account["avatar_url"])
            self.assertEqual("sph0EsWCBF86AZF", account["wechat_id"])

    def test_avatar_url_column_migrated_on_old_schema(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    wechat_id TEXT,
                    status TEXT NOT NULL DEFAULT 'expired',
                    cookie_path TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()

            dao = WeixinDAO(str(db_path))
            cols = {
                row["name"]
                for row in dao._get_conn().execute("PRAGMA table_info(accounts)").fetchall()
            }
            self.assertIn("avatar_url", cols)

    def test_parse_auth_data_profile(self):
        payload = {
            "errCode": 0,
            "data": {
                "userAttr": {"nickname": "我是如此相信"},
                "finderUser": {
                    "nickname": "平安12386",
                    "headImgUrl": "https://wx.qlogo.cn/finderhead/demo/0",
                    "uniqId": "sph0EsWCBF86AZF",
                    "finderUsername": "v2_xxx@finder",
                },
            },
        }
        manager = AccountManager.__new__(AccountManager)
        profile = manager.parse_auth_data_profile(payload)
        self.assertEqual("平安12386", profile["nickname"])
        self.assertEqual("https://wx.qlogo.cn/finderhead/demo/0", profile["avatar_url"])
        self.assertEqual("sph0EsWCBF86AZF", profile["uniq_id"])

    def test_extract_and_save_profile_prefers_auth_data(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "weixin.db"
            cookies_dir = Path(tmp) / "cookies"
            cookies_dir.mkdir()
            with patch.object(WeixinConfig, "COOKIES_DIR", cookies_dir), patch.object(
                WeixinConfig, "DB_PATH", db_path
            ):
                dao = WeixinDAO(str(db_path))
                account_id = dao.create_account()
                account = dao.get_account(account_id)
                Path(account["cookie_path"]).write_text("[]", encoding="utf-8")
                manager = AccountManager(dao)

                with patch.object(
                    manager,
                    "fetch_account_profile_via_auth_data",
                    return_value={
                        "nickname": "平安12386",
                        "avatar_url": "https://wx.qlogo.cn/finderhead/demo/0",
                        "uniq_id": "sph0EsWCBF86AZF",
                    },
                ):
                    profile = manager.extract_and_save_profile(account_id, page=None)

                saved = dao.get_account(account_id)

            self.assertEqual("平安12386", profile["nickname"])
            self.assertEqual("平安12386", saved["name"])
            self.assertEqual("https://wx.qlogo.cn/finderhead/demo/0", saved["avatar_url"])
            self.assertEqual("sph0EsWCBF86AZF", saved["wechat_id"])


if __name__ == "__main__":
    unittest.main()
