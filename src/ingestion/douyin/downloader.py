"""
抖音下载工具

提供高级接口函数，用于：
1. 获取视频下载链接
2. 下载视频文件
3. 解析视频信息
"""

from typing import Dict, Any, Optional, Callable

from .processor import DouyinProcessor, DouyinVideoInfo, DownloadProgress
from ...core import logger


class DouyinDownloader:
    """抖音下载工具类"""
    
    def __init__(self):
        """初始化下载工具"""
        self.processor = DouyinProcessor()
    
    @staticmethod
    def _format_result(
        status: str,
        message: str = "",
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        格式化结果
        
        Args:
            status: 状态（success 或 error）
            message: 消息
            data: 附加数据
        
        Returns:
            Dict: 格式化后的结果字典
        """
        result = {
            "status": status,
            "message": message
        }
        if data:
            result.update(data)
        return result
    
    def get_download_link(self, share_link: str) -> Dict[str, Any]:
        """
        获取抖音无水印下载链接
        
        功能：
        1. 解析分享链接
        2. 提取视频信息
        3. 返回无水印下载链接
        
        Args:
            share_link: 抖音分享链接或包含链接的文本
        
        Returns:
            Dict: 包含以下字段的字典：
                - status: "success" 或 "error"
                - video_id: 视频 ID
                - title: 视频标题
                - download_url: 无水印下载链接
                - message: 相关消息
        
        Example:
            >>> downloader = DouyinDownloader()
            >>> result = downloader.get_download_link("https://v.douyin.com/xxxxx")
            >>> if result['status'] == 'success':
            >>>     print(f"下载链接: {result['download_url']}")
        """
        try:
            logger.info("📱 获取抖音无水印下载链接...")
            
            # 解析分享链接
            video_info = self.processor.parse_share_url(share_link)
            
            return self._format_result(
                status="success",
                message=f"✅ 成功获取视频下载链接",
                data={
                    "video_id": video_info.video_id,
                    "title": video_info.title,
                    "download_url": video_info.url,
                    "description": f"视频标题: {video_info.title}",
                }
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 获取下载链接失败: {error_msg}")
            return self._format_result(
                status="error",
                message=f"获取下载链接失败: {error_msg}",
            )
    
    def download_video(
        self, 
        share_link: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        下载抖音视频文件
        
        功能：
        1. 解析分享链接
        2. 获取视频信息
        3. 下载视频文件到工作目录
        4. 显示下载进度
        
        Args:
            share_link: 抖音分享链接或包含链接的文本
            on_progress: 进度回调函数（可选）
        
        Returns:
            Dict: 包含以下字段的字典：
                - status: "success" 或 "error"
                - video_id: 视频 ID
                - title: 视频标题
                - file_path: 保存的文件路径
                - message: 相关消息
        
        Example:
            >>> def progress_callback(progress):
            >>>     print(f"下载进度: {progress['percentage']:.1f}%")
            >>> 
            >>> downloader = DouyinDownloader()
            >>> result = downloader.download_video(
            >>>     "https://v.douyin.com/xxxxx",
            >>>     on_progress=progress_callback
            >>> )
            >>> if result['status'] == 'success':
            >>>     print(f"文件已保存: {result['file_path']}")
        """
        try:
            logger.info("🎬 开始下载抖音视频...")
            
            # 步骤1: 解析分享链接
            logger.info("正在解析抖音分享链接...")
            video_info = self.processor.parse_share_url(share_link)
            
            # 步骤2: 创建进度回调包装器
            def progress_wrapper(progress: DownloadProgress) -> None:
                """包装进度回调函数"""
                if on_progress:
                    on_progress({
                        "downloaded": progress.downloaded,
                        "total": progress.total,
                        "percentage": progress.percentage
                    })
            
            # 步骤3: 下载视频
            file_path = self.processor.download_video(
                video_info,
                on_progress=progress_wrapper if on_progress else None
            )
            
            return self._format_result(
                status="success",
                message=f"✅ 视频下载完成",
                data={
                    "video_id": video_info.video_id,
                    "title": video_info.title,
                    "file_path": file_path,
                }
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 下载视频失败: {error_msg}")
            return self._format_result(
                status="error",
                message=f"下载视频失败: {error_msg}",
            )
    
    def parse_video_info(self, share_link: str) -> Dict[str, Any]:
        """
        解析抖音视频信息
        
        功能：
        1. 解析分享链接
        2. 提取视频信息
        3. 返回视频详情（不下载）
        
        Args:
            share_link: 抖音分享链接或包含链接的文本
        
        Returns:
            Dict: 包含以下字段的字典：
                - status: "success" 或 "error"
                - video_id: 视频 ID
                - title: 视频标题
                - download_url: 无水印下载链接
                - message: 相关消息
        
        Example:
            >>> downloader = DouyinDownloader()
            >>> result = downloader.parse_video_info("https://v.douyin.com/xxxxx")
            >>> if result['status'] == 'success':
            >>>     print(f"视频ID: {result['video_id']}")
            >>>     print(f"标题: {result['title']}")
        """
        try:
            logger.info("📋 解析视频信息...")
            
            # 解析分享链接
            video_info = self.processor.parse_share_url(share_link)
            
            return self._format_result(
                status="success",
                message="✅ 视频信息解析成功",
                data={
                    "video_id": video_info.video_id,
                    "title": video_info.title,
                    "download_url": video_info.url,
                    "description": video_info.description,
                }
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 解析视频信息失败: {error_msg}")
            return self._format_result(
                status="error",
                message=f"解析视频信息失败: {error_msg}",
            )


# 全局单例
_downloader_instance = None


def get_downloader() -> DouyinDownloader:
    """获取或创建全局下载器实例"""
    global _downloader_instance
    if _downloader_instance is None:
        _downloader_instance = DouyinDownloader()
    return _downloader_instance
