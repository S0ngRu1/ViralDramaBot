"""一次性迁移：将旧路径 ~/.viraldramabot_data/weixin 的账号合并到新 AppData 路径。"""

import os
import shutil
import sqlite3
from pathlib import Path

OLD_DB = Path.home() / ".viraldramabot_data" / "weixin" / "weixin.db"
NEW_DB = Path(os.environ["APPDATA"]) / "ViralDramaBot" / "weixin" / "weixin.db"
NEW_COOKIES = NEW_DB.parent / "cookies"


def migrate():
    if not OLD_DB.exists():
        print("旧数据库不存在，无需迁移")
        return

    NEW_COOKIES.mkdir(parents=True, exist_ok=True)

    old = sqlite3.connect(OLD_DB)
    old.row_factory = sqlite3.Row
    new = sqlite3.connect(NEW_DB)
    new.row_factory = sqlite3.Row

    old_accounts = old.execute("SELECT * FROM accounts").fetchall()
    print(f"旧库账号: {len(old_accounts)}")

    migrated = 0
    for acc in old_accounts:
        a = dict(acc)
        name = a["name"]
        exists = new.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
        if exists:
            print(f"  跳过（已存在）: {name}")
            continue

        old_cookie = Path(a["cookie_path"]) if a["cookie_path"] else None
        new_cookie_path = None
        if old_cookie and old_cookie.exists():
            dest = NEW_COOKIES / old_cookie.name
            shutil.copy2(old_cookie, dest)
            new_cookie_path = str(dest)

        new.execute(
            "INSERT INTO accounts (name, wechat_id, status, cookie_path, created_at, last_login_at)"
            " VALUES (?,?,?,?,?,?)",
            (name, a["wechat_id"], a["status"], new_cookie_path,
             a["created_at"], a["last_login_at"]),
        )
        migrated += 1
        print(f"  已迁移: {name}")

    new.commit()
    old.close()
    new.close()
    print(f"完成，共迁移 {migrated} 个账号")


if __name__ == "__main__":
    migrate()
