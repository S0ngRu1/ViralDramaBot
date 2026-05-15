"""
视频号模块配置
"""

import os
from pathlib import Path


class WeixinConfig:
    """视频号上传模块配置"""

    # 视频号创作者中心 URL
    CHANNELS_URL = "https://channels.weixin.qq.com"
    POST_CREATE_URL = f"{CHANNELS_URL}/platform/post/create"
    POST_LIST_URL = f"{CHANNELS_URL}/platform/post/list"
    LOGIN_URL = f"{CHANNELS_URL}/login.html?from=assistant"

    # 数据目录
    DATA_DIR = Path(os.getenv("WORK_DIR", Path.home() / ".viraldramabot_data")) / "weixin"
    COOKIES_DIR = DATA_DIR / "cookies"
    LOGS_DIR = DATA_DIR / "logs"
    DB_PATH = DATA_DIR / "weixin.db"

    # 浏览器配置
    BROWSER_PATH = os.getenv("BROWSER_PATH", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    MAX_BROWSER_INSTANCES = 3  # 最大同时运行的浏览器实例数
    BROWSER_HEADLESS = False  # 视频号需要扫码，默认不使用无头模式
    PAGE_LOAD_TIMEOUT = 30  # 页面加载超时（秒）
    UPLOAD_TIMEOUT = 600  # 上传超时（秒）
    # 连续上传（如同一批任务）时，上一个视频成功后到开始下一个的间隔（秒）
    INTER_UPLOAD_COOLDOWN_SEC = max(0, int(os.getenv("WEIXIN_INTER_UPLOAD_COOLDOWN_SEC", "20")))
    OPERATION_DELAY_MIN = 0.5  # 操作间最小延迟（秒）
    OPERATION_DELAY_MAX = 2.0  # 操作间最大延迟（秒）

    # 上传配置
    # 同时进行的上传任务数（跨账号全局）。DrissionPage 每任务会启独立浏览器，
    # 多实例并发易导致调试端口/进程互斥，后启动的任务会打断前一个，表现为「抢占」。
    # 默认 1 表示全局串行上传；机器强劲且已验证可多开时再改为 2+。
    MAX_CONCURRENT_UPLOADS = max(1, int(os.getenv("WEIXIN_MAX_CONCURRENT_UPLOADS", "1")))
    MAX_RETRIES = 3  # 最大重试次数
    MAX_ACCOUNTS = 50  # 最大账号数
    SUPPORTED_VIDEO_FORMATS = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"]
    MAX_VIDEO_SIZE_MB = 2048  # 最大视频大小（MB）

    # 定时调度配置
    SCHEDULER_TIMEZONE = "Asia/Shanghai"
    PROXY_ENABLED = os.getenv("WEIXIN_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    PROXY_SCHEME = os.getenv("WEIXIN_PROXY_SCHEME", "http").strip().lower()
    PROXY_HOST = os.getenv("WEIXIN_PROXY_HOST", "127.0.0.1").strip()
    PROXY_PORT = int(os.getenv("WEIXIN_PROXY_PORT", "0") or "0")
    LOCATION_MODE = os.getenv("WEIXIN_LOCATION_MODE", "proxy_ip").strip().lower()

    @classmethod
    def proxy_url(cls) -> str:
        if not cls.PROXY_ENABLED or not cls.PROXY_HOST or not cls.PROXY_PORT:
            return ""
        return f"{cls.PROXY_SCHEME}://{cls.PROXY_HOST}:{cls.PROXY_PORT}"

    @classmethod
    def ensure_dirs(cls):
        """确保所有必要目录存在"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.COOKIES_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
