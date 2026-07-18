import os
import subprocess
import sys
import unittest
from pathlib import Path


class WeixinConfigPathTests(unittest.TestCase):
    def test_default_db_path_uses_appdata(self):
        appdata = os.environ.get("APPDATA")
        self.assertTrue(appdata, "APPDATA must be set on Windows test environment")

        code = (
            "from src.publishing.weixin.config import WeixinConfig; "
            "print(WeixinConfig.DB_PATH)"
        )
        env = os.environ.copy()
        env.pop("WORK_DIR", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        expected = Path(appdata) / "ViralDramaBot" / "weixin" / "weixin.db"
        self.assertEqual(str(expected), result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
