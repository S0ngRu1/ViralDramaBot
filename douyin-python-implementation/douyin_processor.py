"""
抖音视频处理器模块

核心功能：
1. 解析抖音分享链接
2. 提取视频信息（ID、标题、下载链接）
3. 下载视频文件
4. 处理无水印视频链接转换
"""

import re
import os
import sys
from typing import Optional, Callable, Dict, Tuple
from dataclasses import dataclass
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from logger import logger
from config import config


# 请求头 - 模拟 iPhone 移动端访问
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class DouyinVideoInfo:
    """抖音视频信息数据类
    
    Attributes:
        url: 视频下载链接
        title: 视频标题
        video_id: 视频ID
        description: 视频描述
    """
    url: str
    title: str
    video_id: str
    description: Optional[str] = None


@dataclass
class DownloadProgress:
    """下载进度数据类
    
    Attributes:
        downloaded: 已下载字节数
        total: 总字节数
        percentage: 下载百分比
    """
    downloaded: int
    total: int
    percentage: float


class DouyinProcessor:
    """抖音视频处理器
    
    主要功能：
    - 解析抖音分享链接
    - 提取视频信息
    - 下载视频文件
    - 处理重定向和反爬虫
    """
    
    # 无水印视频页面 URL 模板
    VIDEO_PAGE_TEMPLATE = "https://www.iesdouyin.com/share/video/{video_id}"
    
    # 备用下载 URL 模板
    BACKUP_URL_TEMPLATE = "https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}"
    
    # 单个块的大小（8KB）
    CHUNK_SIZE = 8192
    
    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        初始化处理器
        
        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """
        创建带有重试机制的会话
        
        返回一个配置好重试策略的 requests Session 对象
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _extract_url_from_text(self, text: str) -> Optional[str]:
        """
        从文本中提取 URL
        
        使用正则表达式从文本中找出第一个 URL
        
        Args:
            text: 输入文本
        
        Returns:
            Optional[str]: 提取出的 URL，如果未找到则返回 None
        """
        # 正则表达式：匹配 http 或 https 开头的 URL
        url_pattern = r'https?://[^\s]+'
        matches = re.findall(url_pattern, text)
        return matches[0] if matches else None
    
    def _get_redirect_url(self, share_url: str) -> str:
        """
        获取重定向后的真实 URL
        
        跟随 HTTP 重定向，最多 5 次，获取最终的真实 URL
        
        过程：
        1. 短链接 (https://v.douyin.com/xxxxx)
           ↓ 301/302 重定向
        2. 中间链接 (https://www.douyin.com/video/xxxxx?param=value)
           ↓ 可能还有重定向
        3. 真实 URL (https://www.douyin.com/video/7374567890123456789)
        
        Args:
            share_url: 分享链接
        
        Returns:
            str: 重定向后的真实 URL
        
        Raises:
            Exception: 请求失败时抛出异常
        """
        try:
            logger.debug(f"正在获取重定向 URL: {share_url}")
            
            response = self.session.get(
                share_url,
                headers=HEADERS,
                timeout=self.timeout,
                allow_redirects=True  # 自动跟随重定向
            )
            
            # 获取最终的 URL
            final_url = response.url
            logger.debug(f"重定向后的 URL: {final_url}")
            
            return final_url
        except Exception as e:
            logger.error(f"获取重定向 URL 失败: {str(e)}")
            raise
    
    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """
        从 URL 中提取视频 ID
        
        抖音视频 URL 格式：
        - https://www.douyin.com/video/{videoId}
        - https://www.douyin.com/video/{videoId}?param=value
        
        Args:
            url: 视频 URL
        
        Returns:
            Optional[str]: 提取出的视频 ID，如果未找到则返回 None
        """
        # 匹配 /video/{videoId} 中的 videoId
        match = re.search(r'/video/(\d+)', url)
        return match.group(1) if match else None
    
    def _fetch_video_page(self, video_id: str) -> str:
        """
        获取视频页面 HTML 内容
        
        Args:
            video_id: 视频 ID
        
        Returns:
            str: 页面 HTML 内容
        
        Raises:
            Exception: 请求失败时抛出异常
        """
        video_page_url = self.VIDEO_PAGE_TEMPLATE.format(video_id=video_id)
        
        try:
            logger.debug(f"正在获取视频页面: {video_page_url}")
            
            response = self.session.get(
                video_page_url,
                headers=HEADERS,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return response.text
        except Exception as e:
            logger.error(f"获取视频页面失败: {str(e)}")
            raise
    
    def _extract_video_info_from_html(
        self, 
        html: str, 
        video_id: str
    ) -> DouyinVideoInfo:
        """
        从 HTML 中提取视频信息
        
        解析步骤：
        1. 使用正则表达式提取视频下载 URL
        2. 将有水印的 URL 转换为无水印 URL（playwm → play）
        3. 提取视频标题
        4. 如果提取失败，使用备用方法
        
        Args:
            html: HTML 内容
            video_id: 视频 ID
        
        Returns:
            DouyinVideoInfo: 视频信息对象
        """
        logger.debug("正在从 HTML 中提取视频信息...")
        
        # 提取视频 URL：查找 "play_addr" 字段中的 url_list 数组的第一个元素
        # 正则表达式说明：
        # - "play_addr"[^}]*"url_list": 匹配 play_addr 字段到 url_list
        # - [^[]*\[\s*"([^"]+)": 匹配到 [ 和引号之间的 URL
        video_url_pattern = r'"play_addr"[^}]*"url_list"[^[]*\[\s*"([^"]+)"'
        video_url_match = re.search(video_url_pattern, html)
        
        if video_url_match:
            # 获取原始 URL（通常是有水印版本）
            original_url = video_url_match.group(1)
            
            # 转换为无水印版本：将 playwm 替换为 play
            clean_url = original_url.replace("playwm", "play")
            logger.debug(f"提取到视频 URL: {clean_url}")
            
            # 提取视频标题
            # 方法1: 从 JSON 的 desc 字段中提取
            title_match = re.search(r'"desc"\s*:\s*"([^"]*)"', html)
            
            # 方法2: 如果方法1失败，从 HTML title 标签中提取
            if not title_match:
                title_match = re.search(r'<title>([^<]+)</title>', html)
            
            title = title_match.group(1) if title_match else f"douyin_{video_id}"
            
            # 清理标题中的非法文件名字符
            title = re.sub(r'[\\/:*?"<>|]', '_', title).strip()
            logger.debug(f"提取到视频标题: {title}")
            
            return DouyinVideoInfo(
                url=clean_url,
                title=title,
                video_id=video_id
            )
        
        # 如果无法从 HTML 中提取，使用备用方法
        logger.warn("无法从 HTML 中提取视频 URL，使用备用方法")
        backup_url = self.BACKUP_URL_TEMPLATE.format(video_id=video_id)
        
        return DouyinVideoInfo(
            url=backup_url,
            title=f"douyin_{video_id}",
            video_id=video_id
        )
    
    def parse_share_url(self, share_text: str) -> DouyinVideoInfo:
        """
        解析抖音分享链接
        
        完整流程：
        1. 从输入文本中提取 URL
        2. 跟随重定向获取真实 URL
        3. 从 URL 中提取视频 ID
        4. 获取视频页面 HTML
        5. 从 HTML 中提取视频信息
        6. 转换为无水印链接
        
        Args:
            share_text: 分享文本（可包含链接）
        
        Returns:
            DouyinVideoInfo: 视频信息
        
        Raises:
            Exception: 如果解析失败抛出异常
        """
        try:
            logger.info("🔍 开始解析抖音分享链接...")
            
            # 步骤1: 提取 URL
            share_url = self._extract_url_from_text(share_text)
            if not share_url:
                raise ValueError("未找到有效的分享链接")
            
            logger.debug(f"提取到分享链接: {share_url}")
            
            # 步骤2: 获取重定向后的 URL
            final_url = self._get_redirect_url(share_url)
            
            # 步骤3: 提取视频 ID
            video_id = self._extract_video_id_from_url(final_url)
            if not video_id:
                # 如果从 URL 中无法提取，生成一个随机 ID
                video_id = self._generate_video_id()
                logger.warn(f"无法从 URL 提取视频 ID，生成随机 ID: {video_id}")
            
            logger.debug(f"提取到视频 ID: {video_id}")
            
            # 步骤4-5: 获取视频页面并提取信息
            html_content = self._fetch_video_page(video_id)
            video_info = self._extract_video_info_from_html(html_content, video_id)
            
            logger.info(f"✅ 成功解析视频信息: {video_info.title}")
            return video_info
        
        except Exception as e:
            logger.error(f"❌ 解析抖音分享链接失败: {str(e)}")
            raise
    
    def download_video(
        self, 
        video_info: DouyinVideoInfo,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None
    ) -> str:
        """
        下载视频文件
        
        下载流程：
        1. 获取视频文件的总大小（从 Content-Length 响应头）
        2. 以流的方式逐块读取和写入文件
        3. 每读取一块数据，计算进度并调用进度回调函数
        4. 显示下载进度到控制台
        5. 保存文件到工作目录
        
        Args:
            video_info: 视频信息对象
            on_progress: 进度回调函数（可选）
        
        Returns:
            str: 下载文件的完整路径
        
        Raises:
            Exception: 如果下载失败抛出异常
        """
        try:
            output_path = config.get_video_path(video_info.video_id)
            
            logger.info(f"📥 开始下载视频: {video_info.title}")
            logger.debug(f"下载 URL: {video_info.url}")
            logger.debug(f"保存路径: {output_path}")
            
            # 发起 GET 请求，使用流模式
            response = self.session.get(
                video_info.url,
                headers=HEADERS,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 获取文件总大小
            total_size = int(response.headers.get('content-length', 0))
            logger.debug(f"视频文件大小: {self._format_bytes(total_size)}")
            
            downloaded_size = 0
            
            # 逐块读取并写入文件
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:  # 过滤掉保活数据块
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 计算进度
                        percentage = (downloaded_size / total_size * 100) if total_size > 0 else 0
                        
                        # 调用进度回调函数
                        if on_progress:
                            progress = DownloadProgress(
                                downloaded=downloaded_size,
                                total=total_size,
                                percentage=percentage
                            )
                            on_progress(progress)
                        
                        # 显示进度到控制台
                        if total_size > 0:
                            progress_bar = self._create_progress_bar(percentage)
                            sys.stdout.write(
                                f"\r下载进度: {percentage:.1f}% {progress_bar} "
                                f"({self._format_bytes(downloaded_size)}/"
                                f"{self._format_bytes(total_size)})"
                            )
                            sys.stdout.flush()
            
            print()  # 换行
            logger.info(f"✅ 视频下载完成: {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"❌ 下载视频失败: {str(e)}")
            # 尝试删除不完整的文件
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            raise
    
    @staticmethod
    def _format_bytes(bytes_size: int) -> str:
        """
        格式化字节大小为可读的字符串
        
        示例：
        - 1024 → "1.0 KB"
        - 1048576 → "1.0 MB"
        - 1073741824 → "1.0 GB"
        
        Args:
            bytes_size: 字节大小
        
        Returns:
            str: 格式化后的大小字符串
        """
        if bytes_size == 0:
            return "0 B"
        
        sizes = ["B", "KB", "MB", "GB", "TB"]
        size_index = 0
        size = float(bytes_size)
        
        while size >= 1024 and size_index < len(sizes) - 1:
            size /= 1024
            size_index += 1
        
        return f"{size:.1f} {sizes[size_index]}"
    
    @staticmethod
    def _create_progress_bar(percentage: float, length: int = 20) -> str:
        """
        创建简单的进度条
        
        示例：
        - 0% → "▯▯▯▯▯▯▯▯▯▯"
        - 50% → "█████▯▯▯▯▯"
        - 100% → "██████████"
        
        Args:
            percentage: 百分比（0-100）
            length: 进度条长度
        
        Returns:
            str: 进度条字符串
        """
        filled = int(length * percentage / 100)
        bar = "█" * filled + "▯" * (length - filled)
        return bar
    
    @staticmethod
    def _generate_video_id() -> str:
        """
        生成随机视频 ID
        
        当无法从 URL 中提取视频 ID 时使用
        
        Returns:
            str: 生成的视频 ID
        """
        import time
        import random
        timestamp = int(time.time() * 1000)
        random_suffix = ''.join(str(random.randint(0, 9)) for _ in range(5))
        return f"douyin_{timestamp}_{random_suffix}"
    
    def cleanup_files(self, *file_paths: str) -> None:
        """
        清理临时文件
        
        Args:
            *file_paths: 要删除的文件路径
        """
        for file_path in file_paths:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.debug(f"已删除文件: {file_path}")
            except Exception as e:
                logger.warn(f"无法删除文件 {file_path}: {str(e)}")
