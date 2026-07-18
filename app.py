#!/usr/bin/env python3
"""
ViralDramaBot Web 应用服务器

提供以下 API 接口：
- POST /api/videos/download - 下载视频
- GET /api/videos - 获取已下载视频列表
- GET /api/videos/{video_id} - 获取视频详情
- DELETE /api/videos/{video_id} - 删除视频
- GET /api/settings - 获取应用设置
- PUT /api/settings - 更新应用设置
"""

import sys
import asyncio
import os
import time
import shutil
import uuid


import platform
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread, Timer

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

# ============================================================================
# 打包环境检测和路径处理
# ============================================================================

def get_project_root() -> Path:
    """
    获取项目根目录路径，支持打包环境

    在打包版本中，sys.executable 是可执行文件的路径，
    在开发环境中，使用当前脚本的路径。
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 解压后的临时目录（包含通过 --add-data 加入的所有文件）
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent

# 获取项目根目录
project_root = get_project_root()

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(project_root))

# 统一数据目录：开发版、安装版、后台模块全部只使用 AppData\Roaming\ViralDramaBot。
# 必须在导入 WeixinConfig / WeixinDAO 之前设置 WORK_DIR，否则微信模块会落到旧默认路径。
APPDATA_ROOT = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
DATA_DIR = APPDATA_ROOT / "ViralDramaBot"
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["WORK_DIR"] = str(DATA_DIR)

from src.ingestion.douyin import get_downloader, DouyinDownloader
from src.publishing.weixin.config import WeixinConfig
from src.publishing.weixin.dao import WeixinDAO
from src.publishing.weixin.account_manager import (
    AccountManager,
    CookieChecker,
    account_refresh_state,
    run_refresh_all_accounts,
)
from src.publishing.weixin.uploader import Uploader
from src.publishing.weixin.scheduler import UploadScheduler
from src.publishing.weixin.batch_queue import batch_upload_queue
from src.publishing.weixin.proxy import (
    ProxyCheckError,
    check_profile,
    check_configured_proxy,
    invalidate_proxy_check_cache,
    _friendly_proxy_error,
)
from src.publishing.weixin.schemas import (
    AccountCreate, AccountBatchDelete, AccountStatus, TaskStatus,
    BatchUploadCreate, ScheduleCreate,
    MetadataSource, TaskBatchDeleteRequest,
    ProxyProfileCreate, ProxyProfileUpdate,
    FavoriteLocationCreate,
    TrafficScanRequest, TrafficDeleteRequest,
)
from src.publishing.weixin.traffic_filter import TrafficFilterService
from src.publishing.weixin.traffic_dashboard import TrafficDashboardService, DEFAULT_HOURS as TRAFFIC_DASHBOARD_HOURS

# ===== 统一数据目录 =====
# DATA_DIR 已在导入微信模块前固定为 %APPDATA%\ViralDramaBot，禁止回退到项目 .data 或 ~/.viraldramabot_data。

# 数据目录路径
VIDEO_METADATA_DIR = DATA_DIR / "metadata"
VIDEO_INDEX_DB_PATH = VIDEO_METADATA_DIR / "video_index.db"
SETTINGS_FILE_PATH = DATA_DIR / "settings.json"
INDEX_REPAIR_INTERVAL_SECONDS = 300
MAX_TASKS_PER_BATCH = 50
DEFAULT_MAX_CONCURRENT = 6

# ============================================================================
# 初始化
# ============================================================================
from src.core import initialize_app, config, logger
config.update(work_dir=str(DATA_DIR))
initialize_app()

def _load_persisted_settings() -> None:
    """从磁盘加载上次保存的设置，覆盖默认值。"""
    import json
    if not SETTINGS_FILE_PATH.exists():
        return
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            saved: dict = json.load(f)
        if saved:
            config.update(**{k: v for k, v in saved.items() if k in {
                "work_dir", "download_timeout", "max_retries",
                "weixin_upload_timeout", "weixin_inter_upload_cooldown",
                "weixin_max_retries", "weixin_proxy_enabled",
                "weixin_proxy_scheme", "weixin_proxy_host",
                "weixin_proxy_port", "weixin_location_mode",
            }})
            logger.info("✅ 已加载持久化设置: video_dir=%s", config.work_dir)
    except Exception as exc:
        logger.warning("⚠️ 加载持久化设置失败（将使用默认值）: %s", exc)

_load_persisted_settings()


def _migrate_legacy_weixin_accounts() -> None:
    """将旧路径 ~/.viraldramabot_data/weixin/weixin.db 的账号一次性迁移到当前数据目录。"""
    import shutil as _shutil
    old_db = Path.home() / ".viraldramabot_data" / "weixin" / "weixin.db"
    if not old_db.exists():
        return
    from src.publishing.weixin.config import WeixinConfig as _WC
    new_db = Path(_WC.DB_PATH)
    new_cookies = Path(_WC.COOKIES_DIR)
    marker = new_db.parent / ".legacy_accounts_migrated"
    if marker.exists():
        return
    if not new_db.exists():
        return
    try:
        old = sqlite3.connect(old_db)
        old.row_factory = sqlite3.Row
        new = sqlite3.connect(new_db)
        new.row_factory = sqlite3.Row
        existing_count = new.execute("SELECT COUNT(*) AS cnt FROM accounts").fetchone()["cnt"]
        if existing_count:
            marker.write_text(
                f"skipped because destination already has {existing_count} account(s)\n",
                encoding="utf-8",
            )
            old.close()
            new.close()
            logger.info("已检测到当前账号库已有账号，跳过旧路径账号迁移: %s", old_db.parent)
            return
        old_accounts = old.execute("SELECT * FROM accounts").fetchall()
        migrated = 0
        for acc in old_accounts:
            a = dict(acc)
            if new.execute("SELECT id FROM accounts WHERE name=?", (a["name"],)).fetchone():
                continue
            old_cookie = Path(a["cookie_path"]) if a.get("cookie_path") else None
            new_cookie_path = None
            if old_cookie and old_cookie.exists():
                dest = new_cookies / old_cookie.name
                new_cookies.mkdir(parents=True, exist_ok=True)
                _shutil.copy2(old_cookie, dest)
                new_cookie_path = str(dest)
            new.execute(
                "INSERT INTO accounts (name, wechat_id, status, cookie_path, created_at, last_login_at)"
                " VALUES (?,?,?,?,?,?)",
                (a["name"], a.get("wechat_id"), a["status"],
                 new_cookie_path, a["created_at"], a.get("last_login_at")),
            )
            migrated += 1
        new.commit()
        marker.write_text(f"migrated {migrated} account(s)\n", encoding="utf-8")
        old.close()
        new.close()
        if migrated:
            logger.info("✅ 自动迁移旧账号 %d 个（来自 %s）", migrated, old_db.parent)
    except Exception as exc:
        logger.warning("⚠️ 旧账号迁移失败（不影响运行）: %s", exc)


# 用户要求只使用 %APPDATA%\ViralDramaBot\weixin\weixin.db。
# 旧路径账号迁移停用，避免 .data / ~/.viraldramabot_data 的账号再次写回当前库。


# 创建 FastAPI 应用
@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理：启动时初始化索引，关闭时清理后台任务"""
    global repair_task
    # 同步建表（快，必须在第一个请求前完成）
    ensure_video_index_storage()
    # 耗时的文件扫描和索引修复放到后台线程，不阻塞事件循环
    asyncio.create_task(asyncio.to_thread(repair_missing_video_entries))
    asyncio.create_task(asyncio.to_thread(scan_and_import_videos, config.work_path))
    if repair_task is None or repair_task.done():
        repair_task = asyncio.create_task(periodic_index_repair())
    # 同步视频号配置到 WeixinConfig
    WeixinConfig.UPLOAD_TIMEOUT = config.weixin_upload_timeout
    WeixinConfig.INTER_UPLOAD_COOLDOWN_SEC = config.weixin_inter_upload_cooldown
    WeixinConfig.MAX_RETRIES = config.weixin_max_retries
    WeixinConfig.PROXY_ENABLED = config.weixin_proxy_enabled
    WeixinConfig.PROXY_SCHEME = config.weixin_proxy_scheme
    WeixinConfig.PROXY_HOST = config.weixin_proxy_host
    WeixinConfig.PROXY_PORT = config.weixin_proxy_port
    WeixinConfig.LOCATION_MODE = config.weixin_location_mode
    # 启动视频号定时调度器
    weixin_scheduler.start()
    # 启动 Cookie 后台轮询（每小时检查一次）
    weixin_cookie_checker.start()
    # 启动批量上传串行队列
    batch_upload_queue.start()
    # 启动后延迟刷新账号，避免与桌面窗口启动争抢 CPU/磁盘（多个 headless Edge）。
    # 不阻塞 lifespan；前端通过 /accounts/refresh-status 轮询进度。
    delay_sec = max(0, int(os.getenv("WEIXIN_STARTUP_REFRESH_DELAY_SEC", "20")))
    if delay_sec <= 0:
        run_refresh_all_accounts(weixin_account_mgr)
    else:
        Timer(delay_sec, run_refresh_all_accounts, args=(weixin_account_mgr,)).start()
        logger.info("视频号账号状态将在 %s 秒后后台刷新", delay_sec)
    yield
    if repair_task and not repair_task.done():
        repair_task.cancel()
        try:
            await repair_task
        except asyncio.CancelledError:
            pass
    # 停止批量上传队列
    batch_upload_queue.stop()
    # 停止 Cookie 轮询
    weixin_cookie_checker.stop()
    # 停止视频号调度器
    weixin_scheduler.stop()

app = FastAPI(
    title="ViralDramaBot",
    description="短剧自动化流水线 - Web 版本",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 仅对 /frontend 下静态资源禁用缓存，避免浏览器长期持有旧的 app.js / weixin.html
@app.middleware("http")
async def _no_cache_frontend_static(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/frontend/") and path.endswith(
        (".js", ".html", ".css", ".json")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# 挂载前端静态文件到 /frontend 路径
frontend_dir = project_root / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

# 根路径重定向到前端首页
from fastapi.responses import RedirectResponse
@app.get("/")
async def root():
    return RedirectResponse(url="/frontend/index.html")

# ============================================================================
# 数据模型
# ============================================================================

class DownloadRequest(BaseModel):
    """下载请求模型"""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tasks": [
                        {"link": "https://v.douyin.com/7PkMlgCQjjY/", "file_name": "第一条视频"},
                        {"link": "https://v.douyin.com/xxxxxxx/", "file_name": ""}
                    ],
                    "save_path": ".data",
                    "max_concurrent": DEFAULT_MAX_CONCURRENT
                }
            ]
        }
    )

    tasks: Optional[List[Dict[str, Optional[str]]]] = None
    link: Optional[str] = None
    links: Optional[List[str]] = None
    save_path: Optional[str] = None
    file_name: Optional[str] = None
    max_concurrent: int = DEFAULT_MAX_CONCURRENT


class VideoInfo(BaseModel):
    """视频信息模型"""
    video_id: str
    title: str
    file_path: str
    file_size: int
    created_at: str
    save_dir: Optional[str] = None


class AppSettings(BaseModel):
    """应用设置模型"""
    video_dir: str
    download_timeout: int = 1200
    max_retries: int = 3
    # 视频号配置
    weixin_upload_timeout: int = 600
    weixin_inter_upload_cooldown: int = 20
    weixin_max_retries: int = 3
    weixin_proxy_enabled: bool = False
    weixin_proxy_scheme: str = "http"
    weixin_proxy_host: str = "127.0.0.1"
    weixin_proxy_port: int = 0
    weixin_location_mode: str = "proxy_ip"


class DownloadProgress(BaseModel):
    """下载进度模型"""
    status: str  # "downloading", "completed", "error"
    percentage: float
    downloaded: int
    total: int
    message: str
    file_path: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    """批量删除请求模型"""
    video_ids: List[str]


class CleanupRequest(BaseModel):
    """维护清理请求。默认不删除账号、Cookie 或本地视频文件。"""
    logs: bool = True
    cache: bool = True
    upload_history: bool = True


class EmbeddedBrowserInput(BaseModel):
    """桌面端内嵌视频号浏览器的输入事件。"""
    type: str
    x_ratio: float = 0.5
    y_ratio: float = 0.5
    delta_x: float = 0
    delta_y: float = 0
    key: str = ""
    code: str = ""


# ============================================================================
# 全局变量（用于存储下载进度）
# ============================================================================

download_status: Dict[str, DownloadProgress] = {}
repair_task: Optional[asyncio.Task] = None
download_status_lock = Lock()
embedded_login_sessions: Dict[str, Dict[str, Any]] = {}
embedded_login_lock = Lock()

# 视频号模块初始化
weixin_dao = WeixinDAO()
weixin_account_mgr = AccountManager(weixin_dao)
weixin_uploader = Uploader(weixin_dao)
weixin_scheduler = UploadScheduler(weixin_dao)
weixin_cookie_checker = CookieChecker(weixin_account_mgr)
weixin_traffic_filter = TrafficFilterService(weixin_dao, weixin_account_mgr)
weixin_traffic_dashboard = TrafficDashboardService(weixin_dao, weixin_account_mgr)


# ============================================================================
# 辅助函数
# ============================================================================

def get_video_list() -> List[VideoInfo]:
    """从 SQLite 索引中获取已下载的视频列表"""
    with get_index_connection() as conn:
        rows = conn.execute(
            """
            SELECT video_id, title, file_path, file_size, created_at, save_dir
            FROM videos
            ORDER BY CAST(created_at AS REAL) DESC
            """
        ).fetchall()
    return [row_to_video_info(row) for row in rows]


def ensure_video_index_storage() -> None:
    """确保索引目录和 SQLite 表已创建"""
    VIDEO_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_index_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                save_dir TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(file_path)"
        )
        conn.commit()


def get_index_connection() -> sqlite3.Connection:
    """获取 SQLite 连接"""
    conn = sqlite3.connect(VIDEO_INDEX_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_video_info(row: sqlite3.Row) -> VideoInfo:
    """将 SQLite 行转换为 VideoInfo"""
    return VideoInfo(
        video_id=row["video_id"],
        title=row["title"],
        file_path=row["file_path"],
        file_size=row["file_size"],
        created_at=row["created_at"],
        save_dir=row["save_dir"]
    )


def upsert_video_index_entry(video_id: str, file_path: str, title: Optional[str] = None) -> VideoInfo:
    """写入或更新一条 SQLite 视频索引"""
    ensure_video_index_storage()
    path = Path(file_path)
    stat = path.stat()
    entry = VideoInfo(
        video_id=video_id,
        title=title or path.stem,
        file_path=str(path),
        file_size=stat.st_size,
        created_at=str(stat.st_ctime),
        save_dir=str(path.parent)
    )

    with get_index_connection() as conn:
        conn.execute(
            "DELETE FROM videos WHERE video_id = ? OR file_path = ?",
            (entry.video_id, entry.file_path)
        )
        conn.execute(
            """
            INSERT INTO videos (video_id, title, file_path, file_size, created_at, save_dir)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry.video_id,
                entry.title,
                entry.file_path,
                entry.file_size,
                entry.created_at,
                entry.save_dir
            )
        )
        conn.commit()
    return entry


def remove_video_index_entry(video_id: str) -> None:
    """从 SQLite 视频索引中移除一条视频记录"""
    ensure_video_index_storage()
    with get_index_connection() as conn:
        conn.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
        conn.commit()


def remove_video_index_entries(video_ids: List[str]) -> None:
    """批量从 SQLite 视频索引中移除多条视频记录"""
    if not video_ids:
        return
    ensure_video_index_storage()
    placeholders = ", ".join("?" for _ in video_ids)
    with get_index_connection() as conn:
        conn.execute(
            f"DELETE FROM videos WHERE video_id IN ({placeholders})",
            tuple(video_ids)
        )
        conn.commit()


def get_video_by_id(video_id: str) -> Optional[VideoInfo]:
    """按视频 ID 从 SQLite 索引查找视频"""
    ensure_video_index_storage()
    with get_index_connection() as conn:
        row = conn.execute(
            """
            SELECT video_id, title, file_path, file_size, created_at, save_dir
            FROM videos
            WHERE video_id = ?
            """,
            (video_id,)
        ).fetchone()
    return row_to_video_info(row) if row else None


def get_videos_by_ids(video_ids: List[str]) -> List[VideoInfo]:
    """批量按视频 ID 从 SQLite 索引查找视频"""
    if not video_ids:
        return []
    ensure_video_index_storage()
    placeholders = ", ".join("?" for _ in video_ids)
    with get_index_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT video_id, title, file_path, file_size, created_at, save_dir
            FROM videos
            WHERE video_id IN ({placeholders})
            """,
            tuple(video_ids)
        ).fetchall()
    return [row_to_video_info(row) for row in rows]


def repair_missing_video_entries() -> int:
    """后台修复索引，移除已不存在的文件记录"""
    ensure_video_index_storage()
    removed_ids: List[str] = []

    with get_index_connection() as conn:
        rows = conn.execute("SELECT video_id, file_path FROM videos").fetchall()
        for row in rows:
            if not Path(row["file_path"]).exists():
                removed_ids.append(row["video_id"])

        if removed_ids:
            placeholders = ", ".join("?" for _ in removed_ids)
            conn.execute(
                f"DELETE FROM videos WHERE video_id IN ({placeholders})",
                tuple(removed_ids)
            )
            conn.commit()

    if removed_ids:
        logger.info(f"🧹 后台修复索引完成，已移除 {len(removed_ids)} 条失效记录")

    return len(removed_ids)


def save_settings_to_disk(settings_dict: dict) -> None:
    """将当前设置持久化到磁盘，下次启动时自动恢复。"""
    import json
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("⚠️ 持久化设置失败: %s", exc)


def scan_and_import_videos(directory: Path) -> int:
    """扫描目录中未被索引的 .mp4 文件并导入数据库。"""
    import hashlib
    if not directory.is_dir():
        return 0
    ensure_video_index_storage()
    with get_index_connection() as conn:
        existing_paths = {
            row[0] for row in conn.execute("SELECT file_path FROM videos").fetchall()
        }
    imported = 0
    for mp4_file in sorted(directory.glob("*.mp4")):
        if str(mp4_file) in existing_paths:
            continue
        try:
            video_id = hashlib.sha256(str(mp4_file).encode()).hexdigest()[:20]
            upsert_video_index_entry(
                video_id=video_id,
                file_path=str(mp4_file),
                title=mp4_file.stem,
            )
            imported += 1
        except Exception as exc:
            logger.warning("⚠️ 导入视频文件失败 %s: %s", mp4_file, exc)
    if imported:
        logger.info("✅ 自动导入 %d 个视频文件（来自 %s）", imported, directory)
    return imported


def build_progress(
    status: str,
    percentage: float,
    downloaded: int,
    total: int,
    message: str,
    file_path: Optional[str] = None
) -> Dict[str, Any]:
    """构建统一的下载进度响应"""
    return {
        "status": status,
        "percentage": percentage,
        "downloaded": downloaded,
        "total": total,
        "message": message,
        "file_path": file_path
    }


def find_video_by_id(video_id: str) -> VideoInfo:
    """按视频 ID 查找视频信息"""
    video = get_video_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=404,
            detail=f"视频 {video_id} 不存在"
        )
    return video


def open_local_path(target_path: Path) -> None:
    """使用系统默认方式打开文件或目录"""
    system_name = platform.system()

    if system_name == "Windows":
        os.startfile(str(target_path))
        return

    if system_name == "Darwin":
        subprocess.Popen(["open", str(target_path)])
        return

    subprocess.Popen(["xdg-open", str(target_path)])


async def periodic_index_repair() -> None:
    """后台定时修复视频索引"""
    while True:
        try:
            repair_missing_video_entries()
        except Exception as e:
            logger.error(f"❌ 后台修复视频索引失败: {str(e)}")
        await asyncio.sleep(INDEX_REPAIR_INTERVAL_SECONDS)


# ============================================================================
# API 路由
# ============================================================================

@app.get("/")
async def root():
    """根路由 - 返回前端应用"""
    return {"message": "ViralDramaBot API Server"}


# ---- 视频下载 ----

@app.post("/api/videos/download")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    下载抖音视频
    
    请求体：
        {
            "link": "https://v.douyin.com/7PkMlgCQjjY/"
        }
    
    返回：
        {
            "status": "success",
            "video_id": "7374567890123456789",
            "title": "视频标题",
            "file_path": "/path/to/video.mp4",
            "message": "视频下载中..."
        }
    """
    try:
        normalized_tasks: List[Dict[str, Optional[str]]] = []

        if request.tasks:
            for item in request.tasks:
                if not isinstance(item, dict):
                    continue
                link = (item.get("link") or "").strip()
                if not link:
                    continue
                file_name = (item.get("file_name") or "").strip() or None
                normalized_tasks.append({"link": link, "file_name": file_name})
        else:
            raw_links: List[str] = []
            if request.link:
                raw_links.append(request.link)
            if request.links:
                raw_links.extend(request.links)
            links = [link.strip() for link in raw_links if isinstance(link, str) and link.strip()]
            for link in links:
                normalized_tasks.append({"link": link, "file_name": (request.file_name or "").strip() or None})

        if not normalized_tasks:
            raise HTTPException(status_code=400, detail="请至少提供一个有效链接")
        if len(normalized_tasks) > MAX_TASKS_PER_BATCH:
            raise HTTPException(
                status_code=400,
                detail=f"单次最多支持 {MAX_TASKS_PER_BATCH} 条下载任务"
            )

        max_concurrent = max(1, min(int(request.max_concurrent or DEFAULT_MAX_CONCURRENT), 10))
        logger.info(f"📥 开始批量下载视频: 数量={len(normalized_tasks)}, 并发={max_concurrent}")
        
        downloader = get_downloader()
        resolved_save_path = request.save_path or config.work_dir
        config.update(
            work_dir=resolved_save_path,
            download_timeout=config.download_timeout,
            max_retries=config.max_retries
        )
        downloader.configure(
            download_timeout=config.download_timeout,
            max_retries=config.max_retries
        )
        
        total_count = len(normalized_tasks)
        completed_count = 0
        success_count = 0
        failed_count = 0
        active_count = 0
        progress_by_link: Dict[str, Dict[str, int]] = {}
        counter_lock = Lock()

        def update_batch_progress(message: str, status: str = "downloading", file_path: Optional[str] = None) -> None:
            with counter_lock:
                aggregate_downloaded = sum(item.get("downloaded", 0) for item in progress_by_link.values())
                aggregate_total = sum(item.get("total", 0) for item in progress_by_link.values())
                local_completed = completed_count
            if aggregate_total > 0:
                percentage = min(100.0, aggregate_downloaded / aggregate_total * 100)
            else:
                percentage = (local_completed / total_count * 100) if total_count > 0 else 0
            with download_status_lock:
                download_status["current"] = build_progress(
                    status=status,
                    percentage=percentage,
                    downloaded=aggregate_downloaded,
                    total=aggregate_total,
                    message=message,
                    file_path=file_path or str(Path(resolved_save_path).resolve())
                )
        
        # 在后台执行批量下载
        def download_task():
            nonlocal completed_count, success_count, failed_count, active_count
            try:
                update_batch_progress(
                    message=f"正在准备批量下载任务... (0/{total_count})",
                    status="downloading",
                    file_path=str(Path(resolved_save_path).resolve())
                )

                def download_single(task: Dict[str, Optional[str]]) -> Dict[str, Any]:
                    nonlocal active_count
                    link = task.get("link") or ""
                    file_name = task.get("file_name")
                    with counter_lock:
                        active_count += 1
                        current_active = active_count
                    update_batch_progress(
                        message=f"正在下载中... 已完成 {completed_count}/{total_count}，进行中 {current_active}",
                        status="downloading"
                    )

                    def progress_callback(progress: Dict[str, Any]):
                        with counter_lock:
                            progress_by_link[link] = {
                                "downloaded": progress.get("downloaded", 0),
                                "total": progress.get("total", 0)
                            }
                        update_batch_progress(
                            message=f"正在下载中... 已完成 {completed_count}/{total_count}，进行中 {active_count}",
                            status="downloading"
                        )

                    try:
                        isolated_downloader = DouyinDownloader()
                        isolated_downloader.configure(
                            download_timeout=config.download_timeout,
                            max_retries=config.max_retries
                        )
                        return isolated_downloader.download_video(
                            link,
                            on_progress=progress_callback,
                            file_name=file_name
                        )
                    finally:
                        with counter_lock:
                            active_count = max(0, active_count - 1)

                results: List[Dict[str, Any]] = []
                with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                    future_map = {
                        executor.submit(download_single, task): task
                        for task in normalized_tasks
                    }
                    for future in as_completed(future_map):
                        task = future_map[future]
                        link = task.get("link")
                        try:
                            result = future.result()
                        except Exception as e:
                            result = {"status": "error", "message": str(e), "link": link}
                        results.append(result)

                        completed_count += 1
                        result_file_path = result.get("file_path")
                        if result.get("status") == "success":
                            success_count += 1
                            if result_file_path:
                                upsert_video_index_entry(
                                    video_id=result.get("video_id", Path(result_file_path).stem),
                                    file_path=result_file_path,
                                    title=Path(result_file_path).stem
                                )
                        else:
                            failed_count += 1

                        update_batch_progress(
                            message=(
                                f"批量下载进行中... 已完成 {completed_count}/{total_count}，"
                                f"成功 {success_count}，失败 {failed_count}"
                            ),
                            status="downloading"
                        )

                status = "completed" if failed_count == 0 else "error"
                update_batch_progress(
                    status=status,
                    message=(
                        f"✅ 批量下载完成，共 {total_count} 个，成功 {success_count}，失败 {failed_count}"
                        if status == "completed"
                        else f"⚠️ 批量下载结束，共 {total_count} 个，成功 {success_count}，失败 {failed_count}"
                    ),
                    file_path=str(Path(resolved_save_path).resolve())
                )
            except Exception as e:
                logger.error(f"❌ 下载失败: {str(e)}")
                with download_status_lock:
                    current_progress = download_status.get("current", {})
                    download_status["current"] = build_progress(
                        status="error",
                        percentage=current_progress.get("percentage", 0),
                        downloaded=current_progress.get("downloaded", 0),
                        total=current_progress.get("total", 0),
                        message=f"下载失败: {str(e)}",
                        file_path=current_progress.get("file_path")
                    )
        
        background_tasks.add_task(download_task)
        
        return {
            "status": "started",
            "message": f"批量下载任务已启动，共 {total_count} 个，并发 {max_concurrent}",
            "tasks": normalized_tasks,
            "total_count": total_count,
            "max_concurrent": max_concurrent,
            "save_path": str(Path(resolved_save_path).resolve()),
            "file_name": request.file_name
        }
    
    except Exception as e:
        logger.error(f"❌ 下载请求失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"下载失败: {str(e)}"
        )


@app.post("/api/videos/parse")
async def parse_video_info(request: DownloadRequest) -> Dict[str, Any]:
    """解析抖音链接并返回视频基础信息"""
    try:
        downloader = get_downloader()
        result = downloader.parse_video_info(request.link)

        if result.get("status") != "success":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "解析视频信息失败")
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 解析视频信息失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"解析视频信息失败: {str(e)}"
        )


# ---- 视频管理 ----

@app.get("/api/videos")
async def get_videos() -> Dict[str, Any]:
    """
    获取已下载的视频列表
    
    返回：
        {
            "status": "success",
            "videos": [
                {
                    "video_id": "7374567890123456789",
                    "title": "视频标题",
                    "file_path": "/path/to/video.mp4",
                    "file_size": 216000000,
                    "created_at": "2024-01-01T12:00:00"
                }
            ],
            "total": 1
        }
    """
    try:
        videos = get_video_list()
        return {
            "status": "success",
            "videos": videos,
            "total": len(videos)
        }
    except Exception as e:
        logger.error(f"❌ 获取视频列表失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取视频列表失败: {str(e)}"
        )


@app.get("/api/videos/{video_id}")
async def get_video_detail(video_id: str) -> Dict[str, Any]:
    """
    获取单个视频详情
    
    参数：
        video_id: 视频 ID
    
    返回：
        {
            "status": "success",
            "video": {
                "video_id": "7374567890123456789",
                "title": "视频标题",
                "file_path": "/path/to/video.mp4",
                "file_size": 216000000,
                "created_at": "2024-01-01T12:00:00"
            }
        }
    """
    try:
        video = find_video_by_id(video_id)
        
        return {
            "status": "success",
            "video": video
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取视频详情失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取视频详情失败: {str(e)}"
        )


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str) -> Dict[str, Any]:
    """
    删除已下载的视频文件
    
    参数：
        video_id: 视频 ID
    
    返回：
        {
            "status": "success",
            "message": "视频已删除"
        }
    """
    try:
        video = find_video_by_id(video_id)
        
        # 删除文件
        file_path = Path(video.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"✅ 已删除视频: {file_path}")
        remove_video_index_entry(video_id)
        
        return {
            "status": "success",
            "message": f"视频 {video_id} 已删除"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除视频失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"删除视频失败: {str(e)}"
        )


@app.post("/api/videos/batch-delete")
async def batch_delete_videos(request: BatchDeleteRequest) -> Dict[str, Any]:
    """批量删除已下载视频"""
    deleted_ids = []

    try:
        videos = get_videos_by_ids(request.video_ids)
        for video in videos:
            file_path = Path(video.file_path)
            if file_path.exists():
                file_path.unlink()
            deleted_ids.append(video.video_id)

        remove_video_index_entries(deleted_ids)

        logger.info(f"✅ 批量删除视频完成: {deleted_ids}")
        return {
            "status": "success",
            "deleted_ids": deleted_ids,
            "deleted_count": len(deleted_ids)
        }
    except Exception as e:
        logger.error(f"❌ 批量删除视频失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"批量删除视频失败: {str(e)}"
        )


@app.post("/api/videos/{video_id}/open")
async def open_video(video_id: str) -> Dict[str, Any]:
    """使用系统默认程序打开视频文件"""
    try:
        video = find_video_by_id(video_id)
        file_path = Path(video.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"视频 {video_id} 不存在")

        open_local_path(file_path)
        return {
            "status": "success",
            "message": "已打开视频文件",
            "file_path": str(file_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 打开视频失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"打开视频失败: {str(e)}"
        )


@app.post("/api/videos/{video_id}/open-folder")
async def open_video_folder(video_id: str) -> Dict[str, Any]:
    """打开视频所在文件夹"""
    try:
        video = find_video_by_id(video_id)
        folder_path = Path(video.file_path).parent
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail=f"目录不存在: {folder_path}")

        open_local_path(folder_path)
        return {
            "status": "success",
            "message": "已打开所在文件夹",
            "folder_path": str(folder_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 打开文件夹失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"打开文件夹失败: {str(e)}"
        )


# ---- 下载进度 ----

@app.get("/api/download-progress")
async def get_download_progress() -> Dict[str, Any]:
    """
    获取最新的下载进度
    
    返回：
        {
            "status": "downloading",
            "percentage": 75.5,
            "downloaded": 163200000,
            "total": 216000000,
            "message": "下载中..."
        }
    """
    if download_status:
        # 返回最后一条状态
        last_status = list(download_status.values())[-1]
        return last_status
    
    return build_progress(
        status="idle",
        percentage=0,
        downloaded=0,
        total=0,
        message="就绪",
        file_path=str(Path(config.work_dir).resolve())
    )


def _win_file_dialog(title: str, multi: bool = True) -> list:
    """使用 Windows 原生 GetOpenFileNameW，不依赖 tkinter。"""
    import ctypes
    import ctypes.wintypes as wt

    OFN_EXPLORER         = 0x00080000
    OFN_FILEMUSTEXIST    = 0x00001000
    OFN_PATHMUSTEXIST    = 0x00000800
    OFN_HIDEREADONLY     = 0x00000004
    OFN_ALLOWMULTISELECT = 0x00000200

    class OFN(ctypes.Structure):
        _fields_ = [
            ("lStructSize",       wt.DWORD),
            ("hwndOwner",         wt.HWND),
            ("hInstance",         ctypes.c_void_p),
            ("lpstrFilter",       ctypes.c_wchar_p),
            ("lpstrCustomFilter", ctypes.c_wchar_p),
            ("nMaxCustFilter",    wt.DWORD),
            ("nFilterIndex",      wt.DWORD),
            ("lpstrFile",         ctypes.POINTER(ctypes.c_wchar)),
            ("nMaxFile",          wt.DWORD),
            ("lpstrFileTitle",    ctypes.POINTER(ctypes.c_wchar)),
            ("nMaxFileTitle",     wt.DWORD),
            ("lpstrInitialDir",   ctypes.c_wchar_p),
            ("lpstrTitle",        ctypes.c_wchar_p),
            ("Flags",             wt.DWORD),
            ("nFileOffset",       wt.WORD),
            ("nFileExtension",    wt.WORD),
            ("lpstrDefExt",       ctypes.c_wchar_p),
            ("lCustData",         ctypes.c_ssize_t),
            ("lpfnHook",          ctypes.c_void_p),
            ("lpTemplateName",    ctypes.c_wchar_p),
            ("pvReserved",        ctypes.c_void_p),
            ("dwReserved",        wt.DWORD),
            ("FlagsEx",           wt.DWORD),
        ]

    BUF_SIZE = 65536
    buf = ctypes.create_unicode_buffer(BUF_SIZE)

    ofn = OFN()
    ofn.lStructSize  = ctypes.sizeof(OFN)
    ofn.lpstrFilter  = "视频文件\0*.mp4;*.avi;*.mov;*.mkv;*.flv;*.wmv\0所有文件\0*.*\0\0"
    ofn.nFilterIndex = 1
    ofn.lpstrFile    = ctypes.cast(buf, ctypes.POINTER(ctypes.c_wchar))
    ofn.nMaxFile     = BUF_SIZE
    ofn.lpstrTitle   = title
    ofn.Flags        = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY
    if multi:
        ofn.Flags |= OFN_ALLOWMULTISELECT

    if not ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        err = ctypes.windll.comdlg32.CommDlgExtendedError()
        if err:
            raise RuntimeError(f"Windows 文件选择器打开失败，错误码: 0x{err:04X}")
        return []

    # 缓冲区格式：单文件=完整路径\0；多文件=目录\0文件名1\0文件名2\0\0
    parts = []
    cur = []
    for i in range(BUF_SIZE):
        ch = buf[i]
        if ch == "\x00":
            if cur:
                parts.append("".join(cur))
                cur = []
            elif parts:
                break
        else:
            cur.append(ch)

    if not parts:
        return []
    if len(parts) == 1:
        return parts
    return [str(Path(parts[0]) / f) for f in parts[1:]]


def _win_dir_dialog(title: str) -> str:
    """使用 Windows 原生 SHBrowseForFolderW，不依赖 tkinter。"""
    import ctypes
    import ctypes.wintypes as wt

    BIF_RETURNONLYFSDIRS = 0x0001
    BIF_NEWDIALOGSTYLE   = 0x0040
    BIF_EDITBOX          = 0x0010

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [
            ("hwndOwner",      wt.HWND),
            ("pidlRoot",       ctypes.c_void_p),
            ("pszDisplayName", ctypes.POINTER(ctypes.c_wchar)),
            ("lpszTitle",      ctypes.c_wchar_p),
            ("ulFlags",        wt.UINT),
            ("lpfn",           ctypes.c_void_p),
            ("lParam",         ctypes.c_ssize_t),
            ("iImage",         ctypes.c_int),
        ]

    disp = ctypes.create_unicode_buffer(260)
    bi = BROWSEINFOW()
    bi.pszDisplayName = ctypes.cast(disp, ctypes.POINTER(ctypes.c_wchar))
    bi.lpszTitle      = title
    bi.ulFlags        = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_EDITBOX

    pidl = ctypes.windll.shell32.SHBrowseForFolderW(ctypes.byref(bi))
    if not pidl:
        return ""

    path_buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetPathFromIDListW(pidl, path_buf)
    ctypes.windll.ole32.CoTaskMemFree(pidl)
    return path_buf.value or ""


@app.get("/api/browse-files")
async def browse_files() -> Dict[str, Any]:
    """打开系统文件选择器（多个视频文件）"""
    try:
        paths = _win_file_dialog("选择视频文件（可多选）", multi=True)
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "paths": paths}
    except Exception as e:
        logger.error(f"❌ 打开文件选择器失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browse-file")
async def browse_file() -> Dict[str, Any]:
    """打开系统文件选择器，选择单个视频文件。"""
    try:
        paths = _win_file_dialog("选择视频文件", multi=False)
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "path": paths[0]}
    except Exception as e:
        logger.error(f"打开文件选择器失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browse-directory")
async def browse_directory() -> Dict[str, Any]:
    """打开系统目录选择器并返回用户选择的路径"""
    try:
        selected_dir = _win_dir_dialog("选择视频保存目录")
        if not selected_dir:
            return {"status": "cancelled", "message": "未选择目录"}
        return {"status": "success", "path": selected_dir}
    except Exception as e:
        logger.error(f"❌ 打开目录选择器失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"打开目录选择器失败: {str(e)}")


# ---- 视频目录重新扫描 ----

@app.post("/api/videos/rescan")
async def rescan_video_dir() -> Dict[str, Any]:
    """扫描当前视频保存目录，将未被索引的 .mp4 文件导入数据库。"""
    try:
        imported = scan_and_import_videos(config.work_path)
        return {"status": "success", "imported": imported, "directory": str(config.work_path)}
    except Exception as e:
        logger.error(f"❌ 重新扫描目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"扫描失败: {e}")


# ---- 应用设置 ----

@app.get("/api/settings")
async def get_settings() -> Dict[str, Any]:
    """
    获取应用设置
    
    返回：
        {
            "status": "success",
            "settings": {
                "video_dir": ".data",
                "download_timeout": 60,
                "max_retries": 3
            }
        }
    """
    try:
        return {
            "status": "success",
            "settings": config.to_dict()
        }
    except Exception as e:
        logger.error(f"❌ 获取设置失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取设置失败: {str(e)}"
        )


@app.put("/api/settings")
async def update_settings(settings: AppSettings) -> Dict[str, Any]:
    """
    更新应用设置
    
    请求体：
        {
            "video_dir": ".data",
            "download_timeout": 60,
            "max_retries": 3
        }
    
    返回：
        {
            "status": "success",
            "message": "设置已更新",
            "settings": {...}
        }
    """
    try:
        if settings.download_timeout < 60:
            raise ValueError("下载超时时间不能小于 60 秒")
        if settings.weixin_upload_timeout < 60:
            raise ValueError("视频号上传超时不能小于 60 秒")

        # 验证目录存在
        if settings.weixin_proxy_scheme not in {"http", "socks5"}:
            raise ValueError("Weixin proxy scheme must be http or socks5")
        if settings.weixin_proxy_enabled and not (1 <= settings.weixin_proxy_port <= 65535):
            raise ValueError("Weixin proxy port must be between 1 and 65535")
        if settings.weixin_location_mode not in {"proxy_ip", "hidden"}:
            raise ValueError("Weixin location mode must be proxy_ip or hidden")

        video_path = Path(settings.video_dir)
        video_path.mkdir(parents=True, exist_ok=True)

        # 更新配置
        updated_settings = config.update(
            work_dir=str(settings.video_dir),
            download_timeout=settings.download_timeout,
            max_retries=settings.max_retries,
            weixin_upload_timeout=settings.weixin_upload_timeout,
            weixin_inter_upload_cooldown=settings.weixin_inter_upload_cooldown,
            weixin_max_retries=settings.weixin_max_retries,
            weixin_proxy_enabled=settings.weixin_proxy_enabled,
            weixin_proxy_scheme=settings.weixin_proxy_scheme,
            weixin_proxy_host=settings.weixin_proxy_host,
            weixin_proxy_port=settings.weixin_proxy_port,
            weixin_location_mode=settings.weixin_location_mode
        )
        get_downloader().configure(
            download_timeout=settings.download_timeout,
            max_retries=settings.max_retries
        )
        save_settings_to_disk(updated_settings)

        # 同步视频号配置到 WeixinConfig
        WeixinConfig.UPLOAD_TIMEOUT = config.weixin_upload_timeout
        WeixinConfig.INTER_UPLOAD_COOLDOWN_SEC = config.weixin_inter_upload_cooldown
        WeixinConfig.MAX_RETRIES = config.weixin_max_retries
        WeixinConfig.PROXY_ENABLED = config.weixin_proxy_enabled
        WeixinConfig.PROXY_SCHEME = config.weixin_proxy_scheme
        WeixinConfig.PROXY_HOST = config.weixin_proxy_host
        WeixinConfig.PROXY_PORT = config.weixin_proxy_port
        WeixinConfig.LOCATION_MODE = config.weixin_location_mode
        # 配置改了，进程内的代理检测缓存必须失效，下次上传 / 测试要走实网
        invalidate_proxy_check_cache()

        logger.info(f"✅ 应用设置已更新: {settings}")

        return {
            "status": "success",
            "message": "设置已更新",
            "settings": updated_settings
        }

    except Exception as e:
        logger.error(f"❌ 更新设置失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"更新设置失败: {str(e)}"
        )


# ============================================================================
# 视频号上传 API
# ============================================================================

# ---- 账号管理 ----

@app.get("/api/weixin/proxy/test")
async def test_weixin_proxy() -> Dict[str, Any]:
    """测试当前代理配置，返回检测到的出口 IP 和归属地。"""
    try:
        # 用户点击「测试代理」是想看实时状态，必须绕过缓存。
        # 但测试完成后顺手把这一次结果作为新缓存写回，省得紧接着第一个上传任务又打一次。
        invalidate_proxy_check_cache()
        result = check_configured_proxy(strict_same_ip=True)
        if not result.get("enabled"):
            return {"status": "failed", "message": "代理未启用"}
        return {"status": "success", "result": result}
    except ProxyCheckError as e:
        return {"status": "failed", "message": str(e)}
    except Exception as e:
        logger.error(f"代理测试失败: {e}")
        return {"status": "failed", "message": str(e)}


@app.get("/api/weixin/proxy-profiles")
async def weixin_list_proxy_profiles() -> Dict[str, Any]:
    profiles = weixin_dao.list_proxy_profiles()
    return {"status": "success", "profiles": profiles, "total": len(profiles)}


@app.post("/api/weixin/proxy-profiles")
async def weixin_create_proxy_profile(request: ProxyProfileCreate) -> Dict[str, Any]:
    profile_id = weixin_dao.create_proxy_profile(
        name=request.name,
        scheme=request.scheme,
        host=request.host,
        port=request.port,
        enabled=request.enabled,
    )
    return {
        "status": "success",
        "profile": weixin_dao.get_proxy_profile(profile_id),
        "message": "代理 Profile 已创建",
    }


@app.put("/api/weixin/proxy-profiles/{profile_id}")
async def weixin_update_proxy_profile(
    profile_id: int, request: ProxyProfileUpdate
) -> Dict[str, Any]:
    success = weixin_dao.update_proxy_profile(
        profile_id,
        **request.model_dump(exclude_unset=True),
    )
    if not success:
        raise HTTPException(status_code=404, detail="代理 Profile 不存在")
    invalidate_proxy_check_cache()
    return {
        "status": "success",
        "profile": weixin_dao.get_proxy_profile(profile_id),
        "message": "代理 Profile 已更新",
    }


@app.delete("/api/weixin/proxy-profiles/{profile_id}")
async def weixin_delete_proxy_profile(profile_id: int) -> Dict[str, Any]:
    success = weixin_dao.delete_proxy_profile(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="代理 Profile 不存在")
    invalidate_proxy_check_cache()
    return {"status": "success", "message": "代理 Profile 已删除"}


@app.post("/api/weixin/proxy-profiles/{profile_id}/check")
async def weixin_check_proxy_profile(profile_id: int) -> Dict[str, Any]:
    profile = weixin_dao.get_proxy_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="代理 Profile 不存在")
    try:
        result = check_profile(profile)
        weixin_dao.update_proxy_profile_check_result(
            profile_id,
            result.get("ip") or None,
            result.get("country") or None,
            result.get("region") or None,
            result.get("city") or None,
            result.get("isp") or None,
            None,
        )
        return {
            "status": "success",
            "result": result,
            "profile": weixin_dao.get_proxy_profile(profile_id),
        }
    except ProxyCheckError as e:
        # 已经是友好文案，直接用
        msg = str(e)
        weixin_dao.update_proxy_profile_check_result(profile_id, None, None, None, None, None, msg)
        return {"status": "failed", "message": msg, "profile": weixin_dao.get_proxy_profile(profile_id)}
    except Exception as e:
        # requests 等底层异常 —— 走一次同样的归类器，避免裸 stack trace 流向前端
        logger.warning(f"代理 Profile #{profile_id} 检测异常：{e}")
        msg = _friendly_proxy_error([str(e)])
        weixin_dao.update_proxy_profile_check_result(profile_id, None, None, None, None, None, msg)
        return {"status": "failed", "message": msg, "profile": weixin_dao.get_proxy_profile(profile_id)}


@app.post("/api/weixin/proxy-profiles/check-all")
async def weixin_check_all_proxy_profiles() -> Dict[str, Any]:
    profiles = [p for p in weixin_dao.list_proxy_profiles() if p.get("enabled")]
    results = []
    for profile in profiles:
        profile_id = profile["id"]
        try:
            result = check_profile(profile)
            weixin_dao.update_proxy_profile_check_result(
                profile_id,
                result.get("ip") or None,
                result.get("country") or None,
                result.get("region") or None,
                result.get("city") or None,
                result.get("isp") or None,
                None,
            )
            results.append({"profile_id": profile_id, "status": "success", "result": result})
        except ProxyCheckError as e:
            msg = str(e)
            weixin_dao.update_proxy_profile_check_result(profile_id, None, None, None, None, None, msg)
            results.append({"profile_id": profile_id, "status": "failed", "message": msg})
        except Exception as e:
            logger.warning(f"批量检测代理 Profile #{profile_id} 异常：{e}")
            msg = _friendly_proxy_error([str(e)])
            weixin_dao.update_proxy_profile_check_result(profile_id, None, None, None, None, None, msg)
            results.append({"profile_id": profile_id, "status": "failed", "message": msg})
    return {"status": "success", "results": results, "profiles": weixin_dao.list_proxy_profiles()}


# ---- 常用发表位置 ----

@app.get("/api/weixin/favorite-locations")
async def weixin_list_favorite_locations() -> Dict[str, Any]:
    """获取所有常用发表位置（按 id 升序）。"""
    return {"status": "success", "locations": weixin_dao.list_favorite_locations()}


@app.post("/api/weixin/favorite-locations")
async def weixin_create_favorite_location(request: FavoriteLocationCreate) -> Dict[str, Any]:
    """新增常用发表位置。重复名称会复用现有记录。"""
    try:
        location_id = weixin_dao.create_favorite_location(request.name)
        return {"status": "success", "location_id": location_id,
                "locations": weixin_dao.list_favorite_locations()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"新增常用发表位置失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/weixin/favorite-locations/{location_id}")
async def weixin_delete_favorite_location(location_id: int) -> Dict[str, Any]:
    success = weixin_dao.delete_favorite_location(location_id)
    if not success:
        raise HTTPException(status_code=404, detail="位置不存在")
    return {"status": "success", "locations": weixin_dao.list_favorite_locations()}


@app.post("/api/weixin/accounts")
async def weixin_create_account(request: AccountCreate) -> Dict[str, Any]:
    """创建视频号账号。名称可选，登录后自动回写视频号昵称与头像。"""
    try:
        account = weixin_account_mgr.create_account(request.name)
        return {"status": "success", "account": account}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weixin/accounts")
async def weixin_get_accounts() -> Dict[str, Any]:
    """获取所有视频号账号"""
    try:
        accounts = weixin_account_mgr.get_all_accounts()
        return {"status": "success", "accounts": accounts, "total": len(accounts)}
    except Exception as e:
        logger.error(f"获取账号列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/accounts/{account_id}/login")
async def weixin_login_account(account_id: int, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """触发扫码登录"""
    account = weixin_account_mgr.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    def do_login():
        weixin_account_mgr.login_with_qrcode(account_id)

    background_tasks.add_task(do_login)
    return {"status": "started", "message": "扫码登录已启动，请在弹出的浏览器窗口中扫码"}


def _capture_login_qr_base64(page) -> Optional[str]:
    """截取视频号登录页当前可见区域，用于在桌面应用内完整呈现。"""
    try:
        return page.get_screenshot(as_base64=True, full_page=False)
    except Exception:
        return None


def _run_embedded_login(session_id: str, account_id: int) -> None:
    account = weixin_account_mgr.get_account(account_id)
    if not account:
        with embedded_login_lock:
            embedded_login_sessions[session_id]["status"] = "error"
            embedded_login_sessions[session_id]["message"] = "账号不存在"
        return

    page = None
    login_profile_dir = None
    page_lock = Lock()
    cookie_path = account["cookie_path"]
    authenticated = False
    cookies_saved = False
    try:
        page, login_profile_dir = weixin_account_mgr._create_qrcode_login_browser(cookie_path, headless=True)
        with embedded_login_lock:
            embedded_login_sessions[session_id]["page"] = page
            embedded_login_sessions[session_id]["page_lock"] = page_lock
            embedded_login_sessions[session_id]["profile_dir"] = login_profile_dir
            embedded_login_sessions[session_id]["status"] = "loading"
            embedded_login_sessions[session_id]["message"] = "正在加载视频号页面..."

        # 已登录账号恢复 Cookie 后直接进入后台；其他账号进入登录页。
        if account.get("status") == AccountStatus.ACTIVE.value and Path(cookie_path).exists():
            with page_lock:
                weixin_account_mgr._load_cookies(page, cookie_path)
                # `/platform` 根路径在部分账号上会错误重定向回登录页；作品列表
                # 是项目现有 Cookie 校验使用的稳定入口，进入后可正常操作整个后台。
                page.get(WeixinConfig.POST_LIST_URL)
            time.sleep(2)
            with page_lock:
                authenticated = weixin_account_mgr._check_login_status(page)["success"]

        if not authenticated:
            weixin_dao.update_account_status(account_id, AccountStatus.LOGGING_IN)
            with page_lock:
                page.get(WeixinConfig.LOGIN_URL)
            time.sleep(2)
            with page_lock:
                weixin_account_mgr._switch_to_qrcode_login(page)

        start_time = time.time()
        closed_count = 0
        while True:
            with embedded_login_lock:
                if embedded_login_sessions.get(session_id, {}).get("cancelled"):
                    latest_account = weixin_dao.get_account(account_id)
                    if latest_account and latest_account.get("status") == AccountStatus.LOGGING_IN.value:
                        weixin_dao.update_account_status(account_id, AccountStatus.EXPIRED)
                    embedded_login_sessions[session_id]["status"] = "cancelled"
                    embedded_login_sessions[session_id]["message"] = "页面已关闭"
                    return

            with page_lock:
                result = weixin_account_mgr._check_login_status(page)
                current_url = str(page.url or "")

            if result["error"] and "浏览器已关闭" in result["error"]:
                closed_count += 1
                if closed_count < 3:
                    time.sleep(1)
                    continue
                with embedded_login_lock:
                    embedded_login_sessions[session_id]["status"] = "failed"
                    embedded_login_sessions[session_id]["message"] = result["error"]
                return
            closed_count = 0

            is_platform = result["success"] or "/platform" in current_url
            if is_platform:
                authenticated = True
                if not cookies_saved:
                    with page_lock:
                        weixin_account_mgr._save_cookies(page, cookie_path)
                    weixin_dao.update_account_status(account_id, AccountStatus.ACTIVE)
                    with page_lock:
                        weixin_account_mgr.extract_and_save_profile(account_id, page=page)
                    cookies_saved = True
                status = "active"
                message = "视频号助手"
            else:
                if authenticated:
                    authenticated = False
                    cookies_saved = False
                    weixin_dao.update_account_status(account_id, AccountStatus.EXPIRED)
                status = "waiting"
                message = result["error"] or "请使用微信扫码登录"

            with page_lock:
                frame = _capture_login_qr_base64(page)
            with embedded_login_lock:
                session = embedded_login_sessions.get(session_id)
                if session:
                    session["status"] = status
                    session["message"] = message
                    session["qr"] = frame
                    session["url"] = current_url
                    session["elapsed"] = int(time.time() - start_time)
                    if authenticated:
                        session["account"] = weixin_dao.get_account(account_id)
            time.sleep(1)

    except Exception as e:
        logger.error(f"应用内登录失败: {e}")
        weixin_dao.update_account_status(account_id, AccountStatus.ERROR)
        with embedded_login_lock:
            if session_id in embedded_login_sessions:
                embedded_login_sessions[session_id]["status"] = "error"
                embedded_login_sessions[session_id]["message"] = str(e)
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass
        if login_profile_dir:
            shutil.rmtree(login_profile_dir, ignore_errors=True)
        with embedded_login_lock:
            if session_id in embedded_login_sessions:
                embedded_login_sessions[session_id]["page"] = None
                embedded_login_sessions[session_id]["page_lock"] = None
                embedded_login_sessions[session_id]["profile_dir"] = None


@app.post("/api/weixin/accounts/{account_id}/login-embedded")
async def weixin_login_account_embedded(account_id: int) -> Dict[str, Any]:
    """启动账号浏览器：未登录显示登录页，已登录直接显示视频号后台。"""
    account = weixin_account_mgr.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    session_id = uuid.uuid4().hex
    with embedded_login_lock:
        for old_session in embedded_login_sessions.values():
            if old_session.get("account_id") == account_id and old_session.get("page"):
                old_session["cancelled"] = True
        embedded_login_sessions[session_id] = {
            "session_id": session_id,
            "account_id": account_id,
            "status": "starting",
            "message": "正在启动应用内登录...",
            "qr": None,
            "url": WeixinConfig.LOGIN_URL,
            "elapsed": 0,
            "cancelled": False,
            "page": None,
            "page_lock": None,
            "profile_dir": None,
        }

    Thread(target=_run_embedded_login, args=(session_id, account_id), daemon=True).start()
    return {"status": "started", "session_id": session_id, "message": "应用内登录已启动"}


@app.get("/api/weixin/login-sessions/{session_id}")
async def weixin_get_login_session(session_id: str) -> Dict[str, Any]:
    with embedded_login_lock:
        session = embedded_login_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="登录会话不存在")
        public = {k: v for k, v in session.items() if k not in {"page", "page_lock", "profile_dir"}}
    return {"status": "success", "session": public}


@app.post("/api/weixin/login-sessions/{session_id}/input")
async def weixin_embedded_browser_input(session_id: str, payload: EmbeddedBrowserInput) -> Dict[str, Any]:
    """把桌面工作区里的鼠标、滚轮和键盘事件转发给 Chromium。"""
    with embedded_login_lock:
        session = embedded_login_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="浏览器会话不存在")
        page = session.get("page")
        page_lock = session.get("page_lock")
    if not page or not page_lock:
        raise HTTPException(status_code=409, detail="浏览器页面尚未就绪")

    event_type = payload.type.lower()
    x_ratio = max(0.0, min(1.0, payload.x_ratio))
    y_ratio = max(0.0, min(1.0, payload.y_ratio))
    try:
        with page_lock:
            viewport = page.rect.viewport_size
            x = round(viewport[0] * x_ratio)
            y = round(viewport[1] * y_ratio)
            if event_type == "click":
                page.run_cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
                page.run_cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
            elif event_type == "wheel":
                page.run_cdp(
                    "Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y,
                    deltaX=payload.delta_x, deltaY=payload.delta_y,
                )
            elif event_type == "key":
                special_codes = {
                    "Enter": 13, "Backspace": 8, "Tab": 9, "Escape": 27,
                    "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39,
                    "ArrowDown": 40, "Delete": 46,
                }
                key_args: Dict[str, Any] = {"key": payload.key, "code": payload.code or payload.key}
                if len(payload.key) == 1:
                    key_args["text"] = payload.key
                if payload.key in special_codes:
                    key_args["windowsVirtualKeyCode"] = special_codes[payload.key]
                page.run_cdp("Input.dispatchKeyEvent", type="keyDown", **key_args)
                page.run_cdp("Input.dispatchKeyEvent", type="keyUp", **key_args)
            elif event_type == "reload":
                page.refresh()
            elif event_type == "back":
                page.back()
            else:
                raise HTTPException(status_code=400, detail="不支持的浏览器操作")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"浏览器操作失败: {exc}")


@app.post("/api/weixin/login-sessions/{session_id}/cancel")
async def weixin_cancel_login_session(session_id: str) -> Dict[str, Any]:
    with embedded_login_lock:
        session = embedded_login_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="登录会话不存在")
        session["cancelled"] = True
        page = session.get("page")
    if page:
        try:
            page.quit()
        except Exception:
            pass
    return {"status": "success", "message": "已取消登录"}


@app.post("/api/weixin/accounts/{account_id}/refresh")
async def weixin_refresh_account(account_id: int) -> Dict[str, Any]:
    """刷新账号登录状态"""
    try:
        result = weixin_account_mgr.refresh_login(account_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"刷新登录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/accounts/{account_id}/open-post-list")
async def weixin_open_post_list(account_id: int) -> Dict[str, Any]:
    """
    使用与上传相同的 Edge/Chromium 配置，注入已保存 Cookie，打开视频号「视频」列表页。
    使用独立 viewer 用户数据目录 + Drission auto_port，可与正在上传的同一账号并行（两扇 Edge 窗口）。
    在独立线程中启动，避免阻塞接口。
    """
    account = weixin_account_mgr.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if not Path(account["cookie_path"]).exists():
        raise HTTPException(status_code=400, detail="Cookie 不存在，请先扫码登录")

    def run_open():
        try:
            result = weixin_account_mgr.open_channels_post_list(account_id)
            if result.get("status") == "error":
                logger.error(f"打开视频管理页: {result.get('message')}")
        except Exception as e:
            logger.error(f"打开视频管理页异常: {e}")

    Thread(target=run_open, daemon=True).start()
    return {
        "status": "started",
        "message": "正在打开视频管理页",
    }


@app.post("/api/weixin/accounts/check-cookies")
async def weixin_check_cookies(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """手动触发所有账号的 Cookie 有效性检查"""
    def do_check():
        weixin_account_mgr.check_all_accounts_cookies()
    background_tasks.add_task(do_check)
    return {"status": "started", "message": "Cookie 检查已在后台启动"}


@app.get("/api/weixin/accounts/refresh-status")
async def weixin_accounts_refresh_status() -> Dict[str, Any]:
    """全量账号刷新状态（前端 polling 用）：是否正在刷新、上次起止时间、最近统计。"""
    return {"status": "success", **account_refresh_state.snapshot()}


@app.post("/api/weixin/accounts/refresh-all")
async def weixin_accounts_refresh_all() -> Dict[str, Any]:
    """手动触发一次全量账号刷新（已在跑则不重复触发）。"""
    snap_before = account_refresh_state.snapshot()
    if snap_before.get("is_refreshing"):
        return {"status": "running", "message": "已有刷新任务在进行中"}
    run_refresh_all_accounts(weixin_account_mgr)
    return {"status": "started", "message": "全量账号刷新已启动"}


@app.delete("/api/weixin/accounts/{account_id}")
async def weixin_delete_account(account_id: int) -> Dict[str, Any]:
    """删除账号"""
    try:
        success = weixin_account_mgr.delete_account(account_id)
        if not success:
            raise HTTPException(status_code=404, detail="账号不存在")
        return {"status": "success", "message": "账号已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/accounts/{account_id}/traffic/scan")
async def weixin_traffic_scan(account_id: int, body: TrafficScanRequest) -> Dict[str, Any]:
    """扫描低播放 / 作品优化建议候选视频（OR）"""
    account = weixin_dao.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    try:
        result = await asyncio.to_thread(
            weixin_traffic_filter.scan,
            account_id,
            body.grace_period_hours,
            body.min_views,
        )
        return result
    except Exception as e:
        logger.error(f"流量筛选扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/accounts/{account_id}/traffic/delete")
async def weixin_traffic_delete(account_id: int, body: TrafficDeleteRequest) -> Dict[str, Any]:
    """删除勾选的候选视频"""
    account = weixin_dao.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    try:
        result = await asyncio.to_thread(
            weixin_traffic_filter.delete_posts,
            account_id,
            body.post_ids,
        )
        return result
    except Exception as e:
        logger.error(f"流量筛选删稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/accounts/batch-delete")
async def weixin_batch_delete_accounts(request: AccountBatchDelete) -> Dict[str, Any]:
    """批量删除账号；有进行中上传任务的账号会跳过。"""
    try:
        result = weixin_account_mgr.delete_accounts(request.account_ids)
        deleted = result.get("deleted") or []
        skipped = result.get("skipped_active") or []
        not_found = result.get("not_found") or []
        parts = [f"删除 {len(deleted)} 个"]
        if skipped:
            parts.append(f"跳过进行中 {len(skipped)} 个")
        if not_found:
            parts.append(f"不存在 {len(not_found)} 个")
        return {
            "status": "success",
            "message": "，".join(parts),
            "deleted": deleted,
            "skipped_active": skipped,
            "not_found": not_found,
        }
    except Exception as e:
        logger.error(f"批量删除账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 上传任务 ----

@app.post("/api/weixin/upload/batch")
async def weixin_batch_upload(request: BatchUploadCreate) -> Dict[str, Any]:
    """
    批量创建上传任务

    本接口仅入队，每个「批量提交」都按提交时间串行执行：
    前一个批量任务（含其中所有视频）执行完毕后，才会开始下一个批量任务。
    """
    try:
        account = weixin_dao.get_account(request.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        task_ids: List[int] = []
        for i, video_path in enumerate(request.video_paths):
            title = request.titles[i] if request.titles and i < len(request.titles) else None
            desc = request.descriptions[i] if request.descriptions and i < len(request.descriptions) else None

            task_id = weixin_dao.create_task(
                account_id=request.account_id,
                video_path=video_path,
                title=title,
                description=desc,
                tags=None,
                metadata_source=request.metadata_source.value,
                proxy_profile_id=request.proxy_profile_id,
                location_label=(request.location_label or "").strip() or None,
                drama_link=request.drama_link,
            )
            task_ids.append(task_id)

        account_id = request.account_id
        metadata_source = request.metadata_source.value
        drama_link = request.drama_link
        proxy_profile_id = request.proxy_profile_id
        location_label = (request.location_label or "").strip() or None

        def do_batch_upload():
            for idx, task_id in enumerate(task_ids):
                task = weixin_dao.get_task(task_id)
                if not task:
                    continue

                # 从第 2 个视频起：
                #   - 失效代理检测缓存，强制下一个 upload_video 重新打网验代理。
                #     默认 5 分钟 TTL 会让批量任务全程复用首次结果，代理在中途挂掉时
                #     后续视频带着「代理良好」的假结论冲进去就会失败。
                #   - 额外预留 1.5s 让 Windows 文件系统释放上一个 Edge 的 user-data-dir
                #     锁；同账号视频共用 user_data_dir，紧接着开下一个偶发抢占。
                if idx > 0:
                    try:
                        invalidate_proxy_check_cache()
                    except Exception as e:
                        logger.warning(f"批量上传：失效代理缓存失败（忽略）：{e}")
                    time.sleep(1.5)

                result = weixin_uploader.upload_video(
                    task_id=task_id,
                    account_id=account_id,
                    video_path=task["video_path"],
                    title=task.get("title"),
                    description=task.get("description"),
                    metadata_source=metadata_source,
                    drama_link=drama_link,
                    proxy_profile_id=proxy_profile_id,
                    location_label=location_label,
                )
                if (
                    result.get("status") == "success"
                    and idx < len(task_ids) - 1
                    and WeixinConfig.INTER_UPLOAD_COOLDOWN_SEC > 0
                ):
                    logger.info(
                        f"批量上传：本视频已成功，等待 {WeixinConfig.INTER_UPLOAD_COOLDOWN_SEC} 秒后继续下一个"
                    )
                    time.sleep(WeixinConfig.INTER_UPLOAD_COOLDOWN_SEC)

        enqueue_info = batch_upload_queue.submit(
            do_batch_upload,
            label=f"account#{account_id} x{len(task_ids)}",
        )

        position = enqueue_info["queue_position"]
        msg = (
            f"批量任务已入队，共 {len(task_ids)} 个视频；当前队列第 {position} 位"
            + ("，将立即开始" if position == 1 else "，需等待前序批量任务完成后再开始")
        )
        return {
            "status": "queued",
            "task_ids": task_ids,
            "total": len(task_ids),
            "queue": enqueue_info,
            "message": msg,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weixin/upload/batch/queue")
async def weixin_batch_queue_status() -> Dict[str, Any]:
    """查看批量上传队列状态：当前正在执行 + 等待中的数量"""
    return {
        "status": "success",
        "queue": batch_upload_queue.snapshot(),
    }


@app.get("/api/weixin/tasks")
async def weixin_get_tasks(
    account_id: Optional[int] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """获取上传任务列表"""
    try:
        task_status = TaskStatus(status) if status else None
        tasks = weixin_dao.get_tasks(account_id=account_id, status=task_status)
        return {"status": "success", "tasks": tasks, "total": len(tasks)}
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/weixin/tasks/{task_id}")
async def weixin_delete_task(task_id: int) -> Dict[str, Any]:
    """删除上传任务"""
    try:
        success = weixin_dao.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"status": "success", "message": "任务已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/tasks/batch-delete")
async def weixin_batch_delete_tasks(request: TaskBatchDeleteRequest) -> Dict[str, Any]:
    """
    批量删除上传任务。

    处于活动状态（uploading/processing/filling/publishing）的任务会被自动跳过，
    避免删除正在跑的浏览器任务导致状态错乱。
    """
    try:
        result = weixin_dao.delete_tasks(request.task_ids)
        deleted = len(result["deleted_ids"])
        skipped = len(result["skipped_active"])
        not_found = len(result["not_found"])

        parts = [f"已删除 {deleted} 条"]
        if skipped:
            parts.append(f"跳过进行中 {skipped} 条")
        if not_found:
            parts.append(f"未找到 {not_found} 条")

        return {
            "status": "success",
            "message": "，".join(parts),
            "deleted_ids": result["deleted_ids"],
            "skipped_active": result["skipped_active"],
            "not_found": result["not_found"],
        }
    except Exception as e:
        logger.error(f"批量删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/weixin/tasks/{task_id}/retry")
async def weixin_retry_task(task_id: int, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """重试失败任务"""
    try:
        task = weixin_dao.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task["status"] != TaskStatus.FAILED.value:
            raise HTTPException(status_code=400, detail="只能重试失败的任务")

        retry_count = weixin_dao.increment_retry(task_id)
        if retry_count > weixin_dao.get_task(task_id).get("retry_count", 3):
            raise HTTPException(status_code=400, detail="已达到最大重试次数")

        def do_retry():
            weixin_uploader.upload_video(
                task_id=task_id,
                account_id=task["account_id"],
                video_path=task["video_path"],
                title=task.get("title"),
                description=task.get("description"),
                metadata_source=task.get("metadata_source", "manual"),
                proxy_profile_id=task.get("proxy_profile_id"),
                location_label=task.get("location_label"),
                drama_link=task.get("drama_link"),
            )

        background_tasks.add_task(do_retry)
        return {"status": "started", "message": "重试任务已启动"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 定时计划 ----

@app.post("/api/weixin/schedule")
async def weixin_create_schedule(request: ScheduleCreate) -> Dict[str, Any]:
    """创建定时计划"""
    try:
        account = weixin_dao.get_account(request.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        schedule_id = weixin_dao.create_schedule(
            account_id=request.account_id,
            video_paths=request.video_paths,
            cron_expr=request.cron_expr,
            interval_minutes=request.interval_minutes,
            titles=request.titles,
            descriptions=request.descriptions,
            tags=request.tags,
            metadata_source=request.metadata_source.value,
        )

        job_id = weixin_scheduler.add_schedule(
            schedule_id=schedule_id,
            account_id=request.account_id,
            video_paths=request.video_paths,
            cron_expr=request.cron_expr,
            interval_minutes=request.interval_minutes,
            titles=request.titles,
            descriptions=request.descriptions,
            tags=request.tags,
            metadata_source=request.metadata_source.value,
        )

        return {"status": "success", "schedule_id": schedule_id, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建定时计划失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weixin/schedule")
async def weixin_get_schedules() -> Dict[str, Any]:
    """获取定时计划列表"""
    try:
        schedules = weixin_dao.get_active_schedules()
        jobs = weixin_scheduler.get_jobs()
        return {"status": "success", "schedules": schedules, "jobs": jobs}
    except Exception as e:
        logger.error(f"获取定时计划失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/weixin/schedule/{schedule_id}")
async def weixin_delete_schedule(schedule_id: int) -> Dict[str, Any]:
    """删除定时计划"""
    try:
        weixin_scheduler.remove_job(f"weixin_schedule_{schedule_id}")
        success = weixin_dao.delete_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail="定时计划不存在")
        return {"status": "success", "message": "定时计划已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除定时计划失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 系统信息 ----

@app.get("/api/logs")
async def get_app_logs(since: int = 0, limit: int = 100) -> Dict[str, Any]:
    """返回进程内最新日志条目，供前端实时展示（不写 DB，仅内存缓冲区）。"""
    from src.core.logger import get_log_entries
    entries = get_log_entries(since_id=since, limit=min(limit, 200))
    return {"status": "success", "entries": entries}


def _truncate_logging_files() -> List[str]:
    """清空当前进程已打开的 FileHandler 日志文件，兼容 Windows 文件锁。"""
    import logging as _logging

    cleared: List[str] = []
    seen: set[str] = set()
    for logger_name in ("", "ViralDramaBot.app", "ViralDramaBot 运营工作台"):
        target_logger = _logging.getLogger(logger_name)
        for handler in list(target_logger.handlers):
            base_filename = getattr(handler, "baseFilename", None)
            if not base_filename or base_filename in seen:
                continue
            seen.add(base_filename)
            try:
                handler.acquire()
                try:
                    if getattr(handler, "stream", None):
                        handler.stream.seek(0)
                        handler.stream.truncate(0)
                        handler.flush()
                    else:
                        Path(base_filename).write_text("", encoding="utf-8")
                finally:
                    handler.release()
                cleared.append(base_filename)
            except Exception as exc:
                logger.warning("清空日志文件失败 %s: %s", base_filename, exc)

    fallback = DATA_DIR / "logs" / "app.log"
    if str(fallback) not in seen and fallback.exists():
        fallback.write_text("", encoding="utf-8")
        cleared.append(str(fallback))
    return cleared


def _clear_runtime_cache() -> Dict[str, Any]:
    """清理运行缓存：代理检测缓存、临时浏览器 profile、视频索引缓存。"""
    removed_paths: List[str] = []
    removed_video_index_rows = 0

    invalidate_proxy_check_cache()

    cache_targets = [
        WeixinConfig.COOKIES_DIR / "login_profiles",
        WeixinConfig.COOKIES_DIR / "viewer",
    ]
    if WeixinConfig.COOKIES_DIR.exists():
        cache_targets.extend(
            p for p in WeixinConfig.COOKIES_DIR.iterdir()
            if p.is_dir() and p.name.startswith("profile_")
        )

    for target in cache_targets:
        try:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                removed_paths.append(str(target))
        except Exception as exc:
            logger.warning("清理缓存目录失败 %s: %s", target, exc)

    ensure_video_index_storage()
    with get_index_connection() as conn:
        cursor = conn.execute("DELETE FROM videos")
        removed_video_index_rows = cursor.rowcount if cursor.rowcount is not None else 0
        conn.commit()

    return {
        "removed_paths": removed_paths,
        "video_index_rows": removed_video_index_rows,
    }


@app.post("/api/maintenance/cleanup")
async def cleanup_maintenance(request: CleanupRequest) -> Dict[str, Any]:
    """
    清除日志、运行缓存、历史视频上传记录。

    不删除账号、不删除账号 Cookie JSON、不删除已下载视频文件。
    上传中的任务会被保留。
    """
    result: Dict[str, Any] = {
        "logs": None,
        "cache": None,
        "upload_history": None,
    }

    if request.logs:
        from src.core.logger import clear_log_entries
        memory_count = clear_log_entries()
        files = _truncate_logging_files()
        result["logs"] = {"memory_entries": memory_count, "files": files}

    if request.cache:
        result["cache"] = _clear_runtime_cache()

    if request.upload_history:
        result["upload_history"] = weixin_dao.clear_upload_history()

    logger.info(
        "维护清理完成：logs=%s cache=%s upload_history=%s",
        bool(request.logs),
        bool(request.cache),
        bool(request.upload_history),
    )
    return {"status": "success", "result": result}


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """轻量探活，供桌面版启动时检测服务是否就绪（不访问数据库）。"""
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    获取系统状态
    
    返回：
        {
            "status": "success",
            "app_name": "ViralDramaBot",
            "version": "1.0.0",
            "video_count": 5
        }
    """
    try:
        videos = get_video_list()
        return {
            "status": "success",
            "app_name": "ViralDramaBot",
            "version": "1.0.0",
            "video_count": len(videos)
        }
    except Exception as e:
        logger.error(f"❌ 获取状态失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取状态失败: {str(e)}"
        )


# ============================================================================
# 启动脚本
# ============================================================================

@app.get("/api/dashboard")
async def get_dashboard() -> Dict[str, Any]:
    """聚合运营工作台首页所需的下载、素材、账号、任务、代理和日志概览。"""
    try:
        videos = get_video_list()
        accounts = weixin_account_mgr.get_all_accounts()
        tasks = weixin_dao.get_tasks()
        proxies = weixin_dao.list_proxy_profiles()
        queue = batch_upload_queue.snapshot()
        from src.core.logger import get_log_entries

        def count_by(items, key):
            stats: Dict[str, int] = {}
            for item in items:
                value = item.get(key) or "unknown"
                stats[value] = stats.get(value, 0) + 1
            return stats

        failed_tasks = [t for t in tasks if t.get("status") == TaskStatus.FAILED.value]
        return {
            "status": "success",
            "download": download_status.get("current") if download_status else build_progress(
                status="idle",
                percentage=0,
                downloaded=0,
                total=0,
                message="就绪",
                file_path=str(Path(config.work_dir).resolve()),
            ),
            "videos": {"total": len(videos), "recent": videos[:5]},
            "accounts": {"total": len(accounts), "by_status": count_by(accounts, "status")},
            "tasks": {
                "total": len(tasks),
                "by_status": count_by(tasks, "status"),
                "failed_recent": failed_tasks[:5],
            },
            "queue": queue,
            "proxies": {
                "total": len(proxies),
                "enabled": len([p for p in proxies if p.get("enabled")]),
            },
            "logs": get_log_entries(limit=8),
        }
    except Exception as e:
        logger.error(f"获取工作台概览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/traffic")
async def get_dashboard_traffic() -> Dict[str, Any]:
    """返回近 24 小时流量缓存快照（不含实时拉取）。"""
    try:
        return weixin_traffic_dashboard.get_snapshot()
    except Exception as e:
        logger.error(f"读取流量快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboard/traffic/refresh")
async def refresh_dashboard_traffic(hours: int = TRAFFIC_DASHBOARD_HOURS) -> Dict[str, Any]:
    """后台刷新近 N 小时流量快照。"""
    try:
        hours = max(1, min(int(hours or TRAFFIC_DASHBOARD_HOURS), 24 * 14))
        return weixin_traffic_dashboard.start_refresh(hours=hours)
    except Exception as e:
        logger.error(f"启动流量刷新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    
    multiprocessing.freeze_support()
    
    logger.info("🚀 启动 ViralDramaBot Web 服务器...")
    logger.info("📱 打开浏览器访问: http://localhost:8000")
    
    # 修改点：在打包环境中，不能传字符串 "app:app"，必须直接传 app 对象
    # 同时在打包环境中，reload 必须为 False
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        # 打包环境：直接运行对象，关闭 reload
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000, 
            log_level="info"
        )
    else:
        # 开发环境：使用字符串路径，开启 reload
        # 注意："app:app" 里的第一个 app 指的是 app.py 这个文件名
        uvicorn.run(
            "app:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True, 
            log_level="info"
        )
