#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import requests
import json
import time
import random
from urllib.parse import urlparse, parse_qs, urlencode, unquote
import hashlib
import os

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class Vibrato():
    """抖音无水印视频下载器"""

    def __init__(self):
        super(Vibrato, self).__init__()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.mobile_session = requests.Session()
        self.mobile_session.headers.update(MOBILE_HEADERS)

    def __get_redirect_url(self, share_url):
        """获取分享链接的重定向URL"""
        try:
            response = self.session.get(share_url, timeout=10, allow_redirects=True)
            return response.url
        except Exception as e:
            raise Exception(f"获取重定向URL失败: {str(e)}")

    def __extract_video_id(self, url):
        """从URL中提取视频ID"""
        # 支持多种格式的URL
        patterns = [
            r'/video/(\d+)',
            r'note/(\d+)',
            r'item_id=(\d+)',
            r'/(\d+)\?',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # 如果没找到，尝试从路径中提取
        path_parts = urlparse(url).path.split('/')
        for part in path_parts:
            if part.isdigit() and len(part) > 15:  # 抖音ID通常很长
                return part

        raise ValueError(f"无法从URL中提取视频ID: {url}")

    def __get_video_info(self, video_id):
        """通过视频ID获取视频信息"""
        # 使用抖音的API接口
        api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"

        params = {
            "item_ids": video_id,
            "dytk": "",
        }

        headers = {
            **HEADERS,
            "referer": "https://www.douyin.com/",
        }

        try:
            response = self.session.get(api_url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"API请求失败，状态码: {response.status_code}")

            data = response.json()
            if not data.get("item_list") or len(data["item_list"]) == 0:
                raise Exception("未找到视频信息")

            item = data["item_list"][0]

            # 获取无水印视频URL
            video_url = None
            if "video" in item:
                # 尝试多个可能的视频URL字段
                video_info = item["video"]
                for key in ["play_addr", "download_addr", "play_addr_lowbr"]:
                    if key in video_info and "url_list" in video_info[key]:
                        url_list = video_info[key]["url_list"]
                        if url_list:
                            # 替换水印地址为无水印地址
                            video_url = url_list[0].replace("/playwm/", "/play/")
                            break

            if not video_url:
                raise Exception("无法获取视频URL")

            return {
                "title": item.get("desc", ""),
                "video_id": video_id,
                "video_url": video_url,
                "author": item.get("author", {}).get("nickname", ""),
                "author_id": item.get("author", {}).get("unique_id", ""),
                "likes": item.get("statistics", {}).get("digg_count", 0),
                "comments": item.get("statistics", {}).get("comment_count", 0),
                "shares": item.get("statistics", {}).get("share_count", 0),
                "create_time": item.get("create_time", 0),
            }

        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")

    def __search_videos_web(self, keyword, max_results=20, min_likes=0):
        """通过网页搜索查找视频（更稳定的方法）"""
        # 抖音网页搜索
        search_url = "https://www.douyin.com/search/"

        params = {
            "keyword": keyword,
            "type": "video",  # 搜索视频类型
        }

        headers = {
            **HEADERS,
            "referer": "https://www.douyin.com/",
            "sec-fetch-site": "same-origin",
        }

        try:
            response = self.session.get(search_url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                raise Exception(f"搜索页面请求失败，状态码: {response.status_code}")

            # 从HTML中提取视频信息
            html_content = response.text

            # 查找视频卡片数据
            # 抖音通常将数据放在<script>标签中
            import re

            results = []

            # 方法1: 查找RENDER_DATA模式
            pattern = r'<script[^>]*id="RENDER_DATA"[^>]*>([^<]+)</script>'
            matches = re.findall(pattern, html_content)

            if matches:
                try:
                    import urllib.parse
                    # 解码URL编码的数据
                    decoded_data = urllib.parse.unquote(matches[0])

                    # 解析JSON数据
                    import json
                    render_data = json.loads(decoded_data)

                    # 在render_data中查找视频列表
                    def find_videos_in_data(data, path=""):
                        videos = []
                        if isinstance(data, dict):
                            for key, value in data.items():
                                if key in ["aweme", "aweme_list", "item_list", "items"] and isinstance(value, list):
                                    # 找到视频列表
                                    for item in value:
                                        if isinstance(item, dict):
                                            # 尝试提取视频信息
                                            video_info = self.__extract_video_from_item(item)
                                            if video_info:
                                                videos.append(video_info)
                                else:
                                    videos.extend(find_videos_in_data(value, f"{path}.{key}"))
                        elif isinstance(data, list):
                            for i, item in enumerate(data):
                                videos.extend(find_videos_in_data(item, f"{path}[{i}]"))
                        return videos

                    found_videos = find_videos_in_data(render_data)
                    results.extend(found_videos)

                except Exception as e:
                    print(f"解析RENDER_DATA失败: {e}")

            # 方法2: 直接搜索视频卡片
            if not results:
                # 查找视频卡片
                video_patterns = [
                    r'data-video-id="(\d+)"[^>]*data-title="([^"]*)"',
                    r'href="(/video/\d+)"[^>]*>([^<]+)</a>',
                    r'抖音号：([^<]+)[^>]*>([^<]+)</div>',
                ]

                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    for match in matches:
                        if len(match) >= 2:
                            video_id = match[0] if match[0].isdigit() else re.search(r'\d+', match[0])
                            title = match[1] if len(match) > 1 else "未知标题"

                            if video_id:
                                video_id = video_id.group() if hasattr(video_id, 'group') else video_id
                                share_url = f"https://www.douyin.com/video/{video_id}"

                                # 尝试获取更多信息
                                try:
                                    video_info = self.get_video_by_url(share_url)
                                    if video_info['likes'] >= min_likes:
                                        results.append({
                                            "title": title,
                                            "video_id": video_id,
                                            "share_url": share_url,
                                            "video_url": video_info['video_url'],
                                            "author": video_info['author'],
                                            "likes": video_info['likes'],
                                            "comments": video_info.get('comments', 0),
                                            "shares": video_info.get('shares', 0),
                                            "duration": 0,
                                        })
                                except:
                                    # 如果无法获取详细信息，添加基本信息
                                    results.append({
                                        "title": title[:100],
                                        "video_id": video_id,
                                        "share_url": share_url,
                                        "video_url": "",
                                        "author": "未知作者",
                                        "likes": 0,
                                        "comments": 0,
                                        "shares": 0,
                                        "duration": 0,
                                    })

            # 应用点赞筛选和限制结果数量
            filtered_results = []
            for video in results:
                if video['likes'] >= min_likes:
                    filtered_results.append(video)

            return filtered_results[:max_results]

        except Exception as e:
            raise Exception(f"网页搜索失败: {str(e)}")

    def __extract_video_from_item(self, item):
        """从数据项中提取视频信息"""
        try:
            # 尝试多种可能的字段结构
            video_id = item.get('aweme_id') or item.get('id') or item.get('video_id')
            if not video_id:
                return None

            title = item.get('desc') or item.get('title') or item.get('content', '')[:100]
            author_info = item.get('author') or {}
            author = author_info.get('nickname') or author_info.get('name', '未知作者')

            # 获取统计信息
            stats = item.get('statistics') or {}
            likes = stats.get('digg_count') or stats.get('like_count') or 0

            # 获取视频URL
            video_info = item.get('video') or {}
            video_url = None

            # 查找无水印视频URL
            for key in ['play_addr', 'download_addr', 'play_addr_lowbr', 'url']:
                url_data = video_info.get(key)
                if isinstance(url_data, dict) and 'url_list' in url_data:
                    url_list = url_data['url_list']
                    if url_list and isinstance(url_list, list) and len(url_list) > 0:
                        video_url = url_list[0].replace("/playwm/", "/play/")
                        break
                elif isinstance(url_data, str):
                    video_url = url_data.replace("/playwm/", "/play/")
                    break

            if not video_url:
                # 如果没有找到视频URL，尝试其他字段
                for key, value in video_info.items():
                    if isinstance(value, str) and 'aweme.snssdk.com' in value:
                        video_url = value.replace("/playwm/", "/play/")
                        break

            share_url = f"https://www.douyin.com/video/{video_id}"

            return {
                "title": str(title)[:200],
                "video_id": str(video_id),
                "share_url": share_url,
                "video_url": video_url or "",
                "author": str(author),
                "likes": int(likes) if likes else 0,
                "comments": int(stats.get('comment_count', 0)),
                "shares": int(stats.get('share_count', 0)),
                "duration": int(video_info.get('duration', 0) // 1000) if video_info.get('duration') else 0,
            }

        except Exception as e:
            print(f"提取视频信息失败: {e}")
            return None

    def download_video(self, video_url, save_path=None, filename=None):
        """下载视频到本地"""
        if not save_path:
            save_path = "."

        if not filename:
            # 生成基于时间的文件名
            timestamp = int(time.time())
            filename = f"douyin_video_{timestamp}.mp4"

        full_path = os.path.join(save_path, filename)

        try:
            # 使用移动端User-Agent获取视频
            headers = {
                "User-Agent": MOBILE_HEADERS["User-Agent"],
                "Referer": "https://www.douyin.com/",
            }

            response = self.mobile_session.get(video_url, headers=headers, timeout=30, stream=True)
            if response.status_code != 200:
                raise Exception(f"视频下载失败，状态码: {response.status_code}")

            # 检查文件大小
            total_size = int(response.headers.get('content-length', 0))

            # 下载视频
            with open(full_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            # 验证文件大小
            actual_size = os.path.getsize(full_path)
            if total_size > 0 and actual_size != total_size:
                print(f"警告: 文件大小不匹配 (预期: {total_size}, 实际: {actual_size})")

            return full_path

        except Exception as e:
            # 清理可能不完整的文件
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except:
                    pass
            raise Exception(f"下载失败: {str(e)}")

    def run(self, url):
        """主下载函数 - 兼容旧接口"""
        try:
            # 获取重定向后的URL
            redirect_url = self.__get_redirect_url(url)

            # 提取视频ID
            video_id = self.__extract_video_id(redirect_url)

            # 获取视频信息
            video_info = self.__get_video_info(video_id)

            # 下载视频
            filename = f"{video_id}.mp4"
            save_path = self.download_video(video_info["video_url"], filename=filename)

            return {
                "status": "success",
                "message": "下载完成",
                "video_id": video_id,
                "save_path": save_path,
                "title": video_info["title"],
                "likes": video_info["likes"],
            }

        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")

    def search_videos(self, keyword, min_likes=0, max_results=20):
        """
        搜索抖音视频
        :param keyword: 搜索关键词
        :param min_likes: 最小点赞数筛选
        :param max_results: 最大结果数
        :return: 视频信息列表
        """
        return self.__search_videos_web(keyword, max_results, min_likes)

    def get_video_by_url(self, url):
        """根据URL获取视频信息（不下载）"""
        try:
            # 获取重定向后的URL
            redirect_url = self.__get_redirect_url(url)

            # 提取视频ID
            video_id = self.__extract_video_id(redirect_url)

            # 获取视频信息
            return self.__get_video_info(video_id)

        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")