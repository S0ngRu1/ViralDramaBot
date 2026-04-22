#!/usr/bin/env python3
"""
Douyin (抖音) Watermark-Free Video Downloader

提供抖音视频的无水印下载功能，支持链接解析、视频提取、本地保存等
"""

import os
import json
import re
import logging
import tempfile
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import subprocess
import requests
from urllib.parse import urlparse, parse_qs
import time

logger = logging.getLogger(__name__)


class DouyinDownloader:
    """抖音视频下载工具类"""
    
    # 抖音常见的URL格式
    DOUYIN_PATTERNS = {
        'share_link': r'https://v\.douyin\.com/\w+/',
        'video_id': r'video/(\d+)',
        'aweme_id': r'aweme_id=(\d+)',
    }
    
    # 请求头信息
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Origin': 'https://www.douyin.com',
        'Referer': 'https://www.douyin.com/',
    }
    
    def __init__(self, output_dir: str = './downloads'):
        """
        初始化下载器
        
        Args:
            output_dir: 视频保存目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
    def _resolve_redirect(self, short_url: str) -> str:
        """
        解析抖音短链接，获取实际URL
        
        Args:
            short_url: 抖音分享链接
            
        Returns:
            实际视频页面URL或视频ID
        """
        try:
            # 尝试解析短链接
            response = self.session.head(
                short_url,
                allow_redirects=True,
                timeout=10
            )
            
            # 从最终URL中提取视频ID
            final_url = response.url
            
            # 尝试从URL中提取视频ID
            if 'video/' in final_url:
                match = re.search(r'video/(\d+)', final_url)
                if match:
                    return match.group(1)
            
            if 'aweme_id=' in final_url:
                match = re.search(r'aweme_id=(\d+)', final_url)
                if match:
                    return match.group(1)
            
            return final_url
            
        except Exception as e:
            logger.error(f"Failed to resolve redirect: {e}")
            raise Exception(f"无法解析链接: {str(e)}")
    
    def _extract_video_id(self, url_or_id: str) -> str:
        """
        从URL或文本中提取视频ID
        
        Args:
            url_or_id: 抖音URL或视频ID
            
        Returns:
            视频ID
        """
        # 如果已经是纯数字，直接返回
        if url_or_id.isdigit():
            return url_or_id
        
        # 尝试从各种格式的URL中提取
        patterns = [
            r'video/(\d+)',
            r'aweme_id=(\d+)',
            r'item_id=(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        raise ValueError(f"无法从 {url_or_id} 提取视频ID")
    
    def _get_video_data_from_api(self, video_id: str) -> Dict[str, Any]:
        """
        从抖音API获取视频数据
        
        Args:
            video_id: 视频ID
            
        Returns:
            视频数据字典
        """
        try:
            # 构建API请求
            # 注意：这是抖音内部使用的一个端点示例
            api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
            
            # 获取页面内容
            response = self.session.get(
                api_url,
                timeout=15,
                verify=True
            )
            response.raise_for_status()
            
            # 尝试解析JSON响应
            data = response.json()
            
            # 检查响应状态
            if data.get('status_code') != 0:
                raise Exception(f"API返回错误: {data.get('status_msg', 'Unknown error')}")
            
            return data.get('aweme_detail', {})
            
        except Exception as e:
            logger.error(f"Failed to get video data from API: {e}")
            raise
    
    def _extract_video_url(self, video_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        从视频数据中提取无水印视频URL和标题
        
        Args:
            video_data: 视频数据字典
            
        Returns:
            (视频URL, 视频标题) 元组
        """
        try:
            # 获取视频信息
            video_info = video_data.get('video', {})
            
            # 优先获取无水印版本 (play_addr 是无水印，download_addr 是有水印)
            download_url = None
            
            # 方法1: 从 play_addr 获取 (原始无水印版本)
            if 'play_addr' in video_info:
                download_url = video_info['play_addr'].get('url_list', [None])[0]
            
            # 方法2: 如果上面没有，尝试从 dynamic_cover 获取
            if not download_url and 'dynamic_cover' in video_info:
                download_url = video_info['dynamic_cover'].get('url_list', [None])[0]
            
            # 获取视频标题/描述
            title = video_data.get('desc', 'douyin_video')
            
            # 清理标题，移除不合法的文件名字符
            title = re.sub(r'[<>:"/\\|?*]', '', title)
            title = title[:50]  # 限制长度
            
            if not title:
                title = f"douyin_{video_data.get('aweme_id', 'unknown')}"
            
            if not download_url:
                raise Exception("无法获取视频下载链接")
            
            return download_url, title
            
        except Exception as e:
            logger.error(f"Failed to extract video URL: {e}")
            raise
    
    def _download_video(self, url: str, title: str) -> str:
        """
        下载视频文件
        
        Args:
            url: 视频下载URL
            title: 视频标题
            
        Returns:
            保存的本地文件路径
        """
        try:
            output_path = self.output_dir / f"{title}.mp4"
            
            # 如果文件已存在，添加时间戳
            if output_path.exists():
                timestamp = int(time.time())
                output_path = self.output_dir / f"{title}_{timestamp}.mp4"
            
            logger.info(f"Downloading video to {output_path}")
            
            # 下载视频
            response = self.session.get(
                url,
                timeout=60,
                stream=True,
                verify=True
            )
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            # 写入文件
            downloaded_size = 0
            chunk_size = 8192
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 记录下载进度
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if int(progress) % 10 == 0:
                                logger.info(f"Download progress: {progress:.1f}%")
            
            logger.info(f"Video downloaded successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to download video: {e}")
            raise
    
    def download(self, url: str) -> Dict[str, Any]:
        """
        下载抖音视频的主方法
        
        Args:
            url: 抖音分享链接或视频ID
            
        Returns:
            包含下载结果信息的字典
        """
        try:
            logger.info(f"Starting download for URL: {url}")
            
            # 步骤1: 解析并获取视频ID
            if url.startswith('http'):
                video_id = self._resolve_redirect(url)
            else:
                video_id = self._extract_video_id(url)
            
            logger.info(f"Extracted video ID: {video_id}")
            
            # 步骤2: 获取视频数据
            video_data = self._get_video_data_from_api(video_id)
            
            # 步骤3: 提取无水印视频URL和标题
            download_url, title = self._extract_video_url(video_data)
            
            logger.info(f"Got download URL for video: {title}")
            
            # 步骤4: 下载视频
            local_path = self._download_video(download_url, title)
            
            return {
                "success": True,
                "video_id": video_id,
                "title": title,
                "local_path": local_path,
                "file_size": os.path.getsize(local_path),
                "message": "视频下载成功"
            }
            
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": f"下载失败: {str(e)}"
            }
    
    def download_batch(self, urls: list) -> Dict[str, Any]:
        """
        批量下载多个视频
        
        Args:
            urls: 抖音链接列表
            
        Returns:
            包含批量下载结果的字典
        """
        results = []
        successful = 0
        failed = 0
        
        for url in urls:
            try:
                logger.info(f"Processing URL: {url}")
                result = self.download(url)
                results.append(result)
                
                if result.get('success'):
                    successful += 1
                else:
                    failed += 1
                
                # 避免频繁请求，添加延迟
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to process URL {url}: {e}")
                results.append({
                    "success": False,
                    "url": url,
                    "error": str(e)
                })
                failed += 1
        
        return {
            "success": True,
            "total": len(urls),
            "successful": successful,
            "failed": failed,
            "results": results,
            "message": f"批量下载完成: 成功 {successful}, 失败 {failed}"
        }


def download_douyin_video(url: str, output_dir: str = './downloads') -> Dict[str, Any]:
    """
    快捷函数：直接下载抖音视频
    
    Args:
        url: 抖音分享链接或视频ID
        output_dir: 输出目录
        
    Returns:
        下载结果字典
    """
    downloader = DouyinDownloader(output_dir)
    return downloader.download(url)


if __name__ == '__main__':
    # 示例使用
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python douyin_download.py <url> [output_dir]")
        print("Example: python douyin_download.py 'https://v.douyin.com/xxxxx/' ./videos")
        sys.exit(1)
    
    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './downloads'
    
    result = download_douyin_video(url, output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
