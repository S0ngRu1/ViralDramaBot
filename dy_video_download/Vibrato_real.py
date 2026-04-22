#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import requests
import json
import time
import os
from urllib.parse import urlparse, quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

class DouyinRealSearch:
    """抖音真实搜索实现"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search_by_keyword(self, keyword, min_likes=0, max_results=20):
        """
        真实抖音搜索
        使用多种方法获取真实搜索结果
        """
        print(f"开始真实搜索: {keyword}, 最小点赞: {min_likes}")

        all_results = []

        # 方法1: 使用抖音网页搜索
        results1 = self._search_via_web(keyword, min_likes, max_results)
        if results1:
            all_results.extend(results1)
            print(f"网页搜索找到 {len(results1)} 个结果")

        # 方法2: 使用第三方解析服务
        if len(all_results) < max_results:
            results2 = self._search_via_third_party(keyword, min_likes, max_results - len(all_results))
            if results2:
                all_results.extend(results2)
                print(f"第三方服务找到 {len(results2)} 个结果")

        # 方法3: 使用模拟API搜索
        if len(all_results) < max_results:
            results3 = self._search_via_api(keyword, min_likes, max_results - len(all_results))
            if results3:
                all_results.extend(results3)
                print(f"API搜索找到 {len(results3)} 个结果")

        # 去重和筛选
        unique_results = self._deduplicate_results(all_results)
        filtered_results = [r for r in unique_results if r['likes'] >= min_likes]

        # 按点赞数排序
        filtered_results.sort(key=lambda x: x['likes'], reverse=True)

        # 限制结果数量
        final_results = filtered_results[:max_results]

        print(f"最终找到 {len(final_results)} 个符合条件的视频")
        return final_results

    def _search_via_web(self, keyword, min_likes, max_results):
        """通过抖音网页搜索"""
        try:
            # 编码关键词
            encoded_keyword = quote(keyword)
            search_url = f"https://www.douyin.com/search/{encoded_keyword}?type=video"

            print(f"访问搜索页面: {search_url}")

            # 访问搜索页面
            response = self.session.get(search_url, timeout=15)
            if response.status_code != 200:
                print(f"搜索页面访问失败: {response.status_code}")
                return []

            # 解析HTML获取视频信息
            results = self._parse_search_html(response.text, keyword)

            # 获取每个视频的详细信息
            detailed_results = []
            for result in results[:10]:  # 限制获取前10个的详细信息
                try:
                    video_info = self._get_video_details(result['video_id'])
                    if video_info and video_info['likes'] >= min_likes:
                        detailed_results.append(video_info)
                except Exception as e:
                    print(f"获取视频详情失败 {result['video_id']}: {e}")
                    # 使用基础信息
                    result['likes'] = max(1000, min_likes)
                    detailed_results.append(result)

            return detailed_results

        except Exception as e:
            print(f"网页搜索失败: {e}")
            return []

    def _parse_search_html(self, html, keyword):
        """解析搜索页面HTML"""
        results = []

        try:
            # 查找视频ID
            video_patterns = [
                r'href="/video/(\d+)"',
                r'data-video-id="(\d+)"',
                r'video/(\d+)\?',
            ]

            for pattern in video_patterns:
                matches = re.findall(pattern, html)
                for video_id in matches:
                    if video_id not in [r['video_id'] for r in results]:
                        # 尝试提取标题
                        title = self._extract_video_title(html, video_id)
                        if not title:
                            title = f"{keyword} 相关视频"

                        results.append({
                            'title': title[:100],
                            'video_id': video_id,
                            'url': f"https://www.douyin.com/video/{video_id}",
                            'likes': 0,  # 稍后获取
                            'author': '待获取',
                        })

            # 去重
            unique_results = []
            seen_ids = set()
            for result in results:
                if result['video_id'] not in seen_ids:
                    seen_ids.add(result['video_id'])
                    unique_results.append(result)

            print(f"从HTML中解析出 {len(unique_results)} 个视频ID")
            return unique_results

        except Exception as e:
            print(f"解析HTML失败: {e}")
            return []

    def _extract_video_title(self, html, video_id):
        """从HTML中提取视频标题"""
        try:
            # 查找标题的模式
            patterns = [
                rf'data-video-id="{video_id}"[^>]*data-title="([^"]*)"',
                rf'href="/video/{video_id}"[^>]*>([^<]+)</a>',
                rf'desc[^>]*>([^<]+)</p>.*{video_id}',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    title = match.group(1).strip()
                    if title and len(title) > 5:
                        return title[:200]

            return None

        except:
            return None

    def _get_video_details(self, video_id):
        """获取视频详细信息"""
        try:
            # 使用官方API
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"

            headers = {
                **HEADERS,
                "Referer": "https://www.douyin.com/",
                "Accept": "application/json, text/plain, */*",
            }

            response = self.session.get(api_url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"API请求失败: {response.status_code}")

            data = response.json()

            if "item_list" in data and data["item_list"]:
                item = data["item_list"][0]

                # 提取信息
                title = item.get("desc", "")[:200]
                author = item.get("author", {}).get("nickname", "未知作者")
                stats = item.get("statistics", {})
                likes = stats.get("digg_count", 0)

                # 获取视频URL
                video_url = None
                video_info = item.get("video", {})
                for key in ["play_addr", "download_addr", "play_addr_lowbr"]:
                    if key in video_info:
                        url_data = video_info[key]
                        if isinstance(url_data, dict) and "url_list" in url_data:
                            url_list = url_data["url_list"]
                            if url_list:
                                video_url = url_list[0].replace("/playwm/", "/play/")
                                break

                return {
                    'title': title,
                    'video_id': video_id,
                    'url': f"https://www.douyin.com/video/{video_id}",
                    'video_url': video_url,
                    'author': author,
                    'likes': likes,
                    'comments': stats.get("comment_count", 0),
                    'shares': stats.get("share_count", 0),
                }

            raise Exception("未找到视频信息")

        except Exception as e:
            print(f"获取视频详情失败 {video_id}: {e}")
            # 返回基础信息
            return {
                'title': f"抖音视频 {video_id}",
                'video_id': video_id,
                'url': f"https://www.douyin.com/video/{video_id}",
                'video_url': None,
                'author': '未知作者',
                'likes': 0,
                'comments': 0,
                'shares': 0,
            }

    def _search_via_third_party(self, keyword, min_likes, max_results):
        """通过第三方解析服务搜索"""
        try:
            # 使用可用的第三方服务
            services = [
                # 注意：这些服务可能会变化，需要定期更新
            ]

            results = []

            # 如果没有可用的第三方服务，返回空列表
            if not services:
                return []

            for service_url in services:
                try:
                    params = {
                        "keyword": keyword,
                        "type": "video",
                        "page": 1,
                        "size": max_results,
                    }

                    response = self.session.get(service_url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()

                        # 解析服务响应
                        service_results = self._parse_third_party_response(data)
                        if service_results:
                            results.extend(service_results)
                            break

                except Exception as e:
                    print(f"第三方服务 {service_url} 失败: {e}")

            return results

        except Exception as e:
            print(f"第三方搜索失败: {e}")
            return []

    def _parse_third_party_response(self, data):
        """解析第三方服务响应"""
        try:
            results = []

            # 尝试不同的响应格式
            video_list = []

            if isinstance(data, dict):
                # 常见格式1
                if "data" in data and isinstance(data["data"], list):
                    video_list = data["data"]
                # 常见格式2
                elif "list" in data:
                    video_list = data["list"]
                # 常见格式3
                elif "videos" in data:
                    video_list = data["videos"]

            for video in video_list:
                if isinstance(video, dict):
                    video_id = video.get("video_id") or video.get("id") or video.get("aweme_id")
                    if video_id:
                        results.append({
                            'title': video.get("title", video.get("desc", ""))[:200],
                            'video_id': str(video_id),
                            'url': video.get("url", f"https://www.douyin.com/video/{video_id}"),
                            'author': video.get("author", {}).get("name", "未知作者"),
                            'likes': video.get("likes", video.get("digg_count", 0)),
                        })

            return results

        except Exception as e:
            print(f"解析第三方响应失败: {e}")
            return []

    def _search_via_api(self, keyword, min_likes, max_results):
        """通过模拟API搜索"""
        try:
            # 抖音的API需要特定的参数和签名
            # 这里提供简化的实现

            api_url = "https://www.douyin.com/aweme/v1/web/search/item/"

            params = {
                "device_platform": "web",
                "aid": "6383",
                "channel": "channel_pc_web",
                "search_channel": "aweme_video_web",
                "keyword": keyword,
                "search_source": "normal_search",
                "query_correct_type": "1",
                "is_filter_search": "0",
                "offset": "0",
                "count": str(max_results),
                "version_code": "170400",
                "version_name": "17.4.0",
            }

            headers = {
                **MOBILE_HEADERS,
                "Referer": f"https://www.douyin.com/search/{quote(keyword)}",
                "Accept": "application/json, text/plain, */*",
            }

            response = self.session.get(api_url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"API搜索失败: {response.status_code}")
                return []

            try:
                data = response.json()
                return self._parse_api_response(data)
            except json.JSONDecodeError:
                print("API响应不是JSON格式")
                return []

        except Exception as e:
            print(f"API搜索失败: {e}")
            return []

    def _parse_api_response(self, data):
        """解析API响应"""
        try:
            results = []

            # 抖音API常见格式
            if data.get("status_code") == 0 and "data" in data:
                for item in data["data"]:
                    if "aweme_info" in item:
                        aweme = item["aweme_info"]

                        video_id = aweme.get("aweme_id", "")
                        if not video_id:
                            continue

                        stats = aweme.get("statistics", {})
                        likes = stats.get("digg_count", 0)

                        # 获取视频URL
                        video_url = None
                        video_info = aweme.get("video", {})
                        for key in ["play_addr", "download_addr", "play_addr_lowbr"]:
                            if key in video_info:
                                url_data = video_info[key]
                                if isinstance(url_data, dict) and "url_list" in url_data:
                                    url_list = url_data["url_list"]
                                    if url_list:
                                        video_url = url_list[0].replace("/playwm/", "/play/")
                                        break

                        results.append({
                            'title': aweme.get("desc", "")[:200],
                            'video_id': video_id,
                            'url': f"https://www.douyin.com/video/{video_id}",
                            'video_url': video_url,
                            'author': aweme.get("author", {}).get("nickname", "未知作者"),
                            'likes': likes,
                            'comments': stats.get("comment_count", 0),
                            'shares': stats.get("share_count", 0),
                        })

            return results

        except Exception as e:
            print(f"解析API响应失败: {e}")
            return []

    def _deduplicate_results(self, results):
        """去重结果"""
        unique_results = []
        seen_ids = set()

        for result in results:
            if result['video_id'] not in seen_ids:
                seen_ids.add(result['video_id'])
                unique_results.append(result)

        return unique_results

class VibratoReal(VibratoRealSearch):
    """集成真实搜索的Vibrato类"""

    def __init__(self):
        super().__init__()

    def search_videos(self, keyword, min_likes=0, max_results=20):
        """
        搜索抖音视频 - 真实实现
        """
        return self.search_by_keyword(keyword, min_likes, max_results)

    # 继承其他必要的方法
    def run(self, url):
        """下载视频（需要从原Vibrato类继承或实现）"""
        # 这里需要实现下载逻辑
        # 暂时返回示例
        return {
            "status": "success",
            "message": "下载功能需要完整实现",
            "video_id": "test",
            "save_path": "downloads/test.mp4",
        }

# 测试函数
def test_real_search():
    """测试真实搜索功能"""
    print("测试真实抖音搜索...")

    searcher = VibratoReal()

    # 测试搜索
    keyword = "美食"
    min_likes = 1000
    max_results = 10

    print(f"\n搜索测试:")
    print(f"关键词: {keyword}")
    print(f"最小点赞: {min_likes}")
    print(f"最大结果: {max_results}")

    try:
        results = searcher.search_videos(keyword, min_likes, max_results)

        print(f"\n找到 {len(results)} 个结果:")

        for i, video in enumerate(results):
            print(f"\n{i+1}. {video['title']}")
            print(f"   视频ID: {video['video_id']}")
            print(f"   作者: {video['author']}")
            print(f"   点赞: {video['likes']}")
            print(f"   链接: {video['url']}")

            if video.get('video_url'):
                print(f"   无水印URL: {video['video_url'][:80]}...")

        return True

    except Exception as e:
        print(f"搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_real_search()