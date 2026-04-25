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
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 添加 src 目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core import initialize_app, config, logger
from src.ingestion.douyin import get_downloader

# ============================================================================
# 初始化
# ============================================================================

# 初始化应用
initialize_app()

# 创建 FastAPI 应用
app = FastAPI(
    title="ViralDramaBot",
    description="短剧自动化流水线 - Web 版本",
    version="0.1.0"
)

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
    
    class Config:
        example = {
            "link": "https://v.douyin.com/7PkMlgCQjjY/"
        }


class VideoInfo(BaseModel):
    """视频信息模型"""
    video_id: str
    title: str
    file_path: str
    file_size: int
    created_at: str


class AppSettings(BaseModel):
    """应用设置模型"""
    video_dir: str
    download_timeout: int = 60
    max_retries: int = 3


class DownloadProgress(BaseModel):
    """下载进度模型"""
    status: str  # "downloading", "completed", "error"
    percentage: float
    downloaded: int
    total: int
    message: str


# ============================================================================
# 全局变量（用于存储下载进度）
# ============================================================================

download_status: Dict[str, DownloadProgress] = {}


# ============================================================================
# 辅助函数
# ============================================================================

def get_video_list() -> List[VideoInfo]:
    """获取已下载的视频列表"""
    video_list = []
    video_dir = Path(config.work_dir)
    
    if not video_dir.exists():
        return video_list
    
    for video_file in video_dir.glob("*.mp4"):
        stat = video_file.stat()
        video_list.append(VideoInfo(
            video_id=video_file.stem,
            title=video_file.stem,
            file_path=str(video_file),
            file_size=stat.st_size,
            created_at=str(stat.st_ctime)
        ))
    
    return sorted(video_list, key=lambda x: x.created_at, reverse=True)


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
        
        # 定义进度回调函数
        def progress_callback(progress: Dict[str, Any]):
            """进度回调 - 实时更新下载进度"""
            download_status["current"] = {
                "status": "downloading",
                "percentage": progress.get("percentage", 0),
                "downloaded": progress.get("downloaded", 0),
                "total": progress.get("total", 0),
                "message": "下载中..."
            }
        
        # 在后台执行下载
        def download_task():
            try:
                # 立即设置下载状态为进行中
                download_status["current"] = {
                    "status": "downloading",
                    "percentage": 0,
                    "downloaded": 0,
                    "total": 0,
                    "message": "正在解析视频链接..."
                }
                
                result = downloader.download_video(
                    request.link,
                    on_progress=progress_callback
                )
                download_status["current"] = {
                    "status": "completed",
                    "percentage": 100,
                    "downloaded": 0,
                    "total": 0,
                    "message": f"✅ 下载完成: {result.get('file_path', '未知路径')}"
                }
            except Exception as e:
                logger.error(f"❌ 下载失败: {str(e)}")
                download_status["current"] = {
                    "status": "error",
                    "percentage": 0,
                    "downloaded": 0,
                    "total": 0,
                    "message": f"下载失败: {str(e)}"
                }
        
        background_tasks.add_task(download_task)
        
        return {
            "status": "started",
            "message": "视频下载已启动",
            "link": request.link
        }
    
    except Exception as e:
        logger.error(f"❌ 下载请求失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"下载失败: {str(e)}"
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
        videos = get_video_list()
        video = next((v for v in videos if v.video_id == video_id), None)
        
        if not video:
            raise HTTPException(
                status_code=404,
                detail=f"视频 {video_id} 不存在"
            )
        
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
        videos = get_video_list()
        video = next((v for v in videos if v.video_id == video_id), None)
        
        if not video:
            raise HTTPException(
                status_code=404,
                detail=f"视频 {video_id} 不存在"
            )
        
        # 删除文件
        file_path = Path(video.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"✅ 已删除视频: {file_path}")
        
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
    
    return {
        "status": "idle",
        "percentage": 0,
        "downloaded": 0,
        "total": 0,
        "message": "就绪"
    }


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
        app_config = config.get_config()
        return {
            "status": "success",
            "settings": {
                "video_dir": app_config.get("video_dir", ".data"),
                "download_timeout": 60,
                "max_retries": 3
            }
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
        # 验证目录存在
        video_path = Path(settings.video_dir)
        video_path.mkdir(parents=True, exist_ok=True)
        
        # 更新配置
        app_config = config.get_config()
        app_config["video_dir"] = str(settings.video_dir)
        
        logger.info(f"✅ 应用设置已更新: {settings}")
        
        return {
            "status": "success",
            "message": "设置已更新",
            "settings": {
                "video_dir": settings.video_dir,
                "download_timeout": settings.download_timeout,
                "max_retries": settings.max_retries
            }
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
    
    logger.info("🚀 启动 ViralDramaBot Web 服务器...")
    logger.info("📱 打开浏览器访问: http://localhost:8000")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式，文件改动时自动重启
        log_level="info"
    )
