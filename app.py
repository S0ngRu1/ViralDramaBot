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


import platform
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

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

from src.core import initialize_app, config, logger
from src.ingestion.douyin import get_downloader

# ===== 新增：数据目录自动适配 =====
if getattr(sys, 'frozen', False):
    # 打包后 → 使用系统 AppData 目录（对用户不可见）
    DATA_DIR = Path(os.getenv("APPDATA")) / "ViralDramaBot"
else:
    # 开发环境 → 仍然使用项目根目录下的 .data
    DATA_DIR = project_root / ".data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# 数据目录路径
VIDEO_METADATA_DIR = DATA_DIR / "metadata"
VIDEO_INDEX_DB_PATH = VIDEO_METADATA_DIR / "video_index.db"
INDEX_REPAIR_INTERVAL_SECONDS = 300

# ============================================================================
# 初始化
# ============================================================================

# 初始化应用
config.update(work_dir=str(DATA_DIR))
initialize_app()


# 创建 FastAPI 应用
app = FastAPI(
    title="ViralDramaBot",
    description="短剧自动化流水线 - Web 版本",
    version="0.1.0"
)


@app.on_event("startup")
async def on_startup() -> None:
    """初始化 SQLite 索引并启动后台修复任务"""
    global repair_task
    ensure_video_index_storage()
    repair_missing_video_entries()
    if repair_task is None or repair_task.done():
        repair_task = asyncio.create_task(periodic_index_repair())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """关闭后台修复任务"""
    global repair_task
    if repair_task and not repair_task.done():
        repair_task.cancel()
        try:
            await repair_task
        except asyncio.CancelledError:
            pass

# 配置 CORS（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    link: str
    save_path: Optional[str] = None
    file_name: Optional[str] = None
    
    class Config:
        example = {
            "link": "https://v.douyin.com/7PkMlgCQjjY/",
            "save_path": ".data",
            "file_name": "视频标题"
        }


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


# ============================================================================
# 全局变量（用于存储下载进度）
# ============================================================================

download_status: Dict[str, DownloadProgress] = {}
repair_task: Optional[asyncio.Task] = None


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
        logger.info(f"📥 开始下载视频: {request.link}")
        
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
        
        # 定义进度回调函数
        def progress_callback(progress: Dict[str, Any]):
            """进度回调 - 实时更新下载进度"""
            current_progress = download_status.get("current", {})
            download_status["current"] = build_progress(
                status="downloading",
                percentage=progress.get("percentage", 0),
                downloaded=progress.get("downloaded", 0),
                total=progress.get("total", 0),
                message="正在下载视频文件...",
                file_path=current_progress.get("file_path")
            )
        
        # 在后台执行下载
        def download_task():
            try:
                # 立即设置下载状态为进行中
                download_status["current"] = build_progress(
                    status="downloading",
                    percentage=0,
                    downloaded=0,
                    total=0,
                    message="正在解析视频链接并准备下载...",
                    file_path=str(Path(resolved_save_path).resolve())
                )
                
                result = downloader.download_video(
                    request.link,
                    on_progress=progress_callback,
                    file_name=request.file_name
                )
                result_file_path = result.get("file_path")
                if result.get("status") == "success" and result_file_path:
                    upsert_video_index_entry(
                        video_id=result.get("video_id", Path(result_file_path).stem),
                        file_path=result_file_path,
                        title=Path(result_file_path).stem
                    )
                download_status["current"] = build_progress(
                    status="completed",
                    percentage=100,
                    downloaded=0,
                    total=0,
                    message=f"✅ 下载完成，文件已保存到: {result_file_path or '未知路径'}",
                    file_path=result_file_path
                )
            except Exception as e:
                logger.error(f"❌ 下载失败: {str(e)}")
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
            "message": "视频下载任务已启动",
            "link": request.link,
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


@app.get("/api/browse-directory")
async def browse_directory() -> Dict[str, Any]:
    """打开系统目录选择器并返回用户选择的路径"""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected_dir = filedialog.askdirectory(
            initialdir=str(Path(config.work_dir).resolve()),
            title="选择视频保存目录"
        )
        root.destroy()

        if not selected_dir:
            return {
                "status": "cancelled",
                "message": "未选择目录"
            }

        return {
            "status": "success",
            "path": selected_dir
        }
    except Exception as e:
        logger.error(f"❌ 打开目录选择器失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"打开目录选择器失败: {str(e)}"
        )


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

        # 验证目录存在
        video_path = Path(settings.video_dir)
        video_path.mkdir(parents=True, exist_ok=True)
        
        # 更新配置
        updated_settings = config.update(
            work_dir=str(settings.video_dir),
            download_timeout=settings.download_timeout,
            max_retries=settings.max_retries
        )
        get_downloader().configure(
            download_timeout=settings.download_timeout,
            max_retries=settings.max_retries
        )
        
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


# ---- 系统信息 ----

@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """
    获取系统状态
    
    返回：
        {
            "status": "success",
            "app_name": "ViralDramaBot",
            "version": "0.1.0",
            "video_count": 5
        }
    """
    try:
        videos = get_video_list()
        return {
            "status": "success",
            "app_name": "ViralDramaBot",
            "version": "0.1.0",
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