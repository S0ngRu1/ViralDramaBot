#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import requests
import json
import time
import os
import subprocess
import threading
import tempfile
from urllib.parse import urlparse

class DouyinMCPServer:
    """抖音MCP Server客户端"""

    def __init__(self, work_dir=None):
        self.work_dir = work_dir or os.path.join(os.getcwd(), ".data")
        self.process = None
        self.server_url = "http://localhost:3000"  # MCP Server默认地址
        self._ensure_work_dir()

    def _ensure_work_dir(self):
        """确保工作目录存在"""
        if not os.path.exists(self.work_dir):
            os.makedirs(self.work_dir)

    def start_server(self):
        """启动MCP Server"""
        if self.process and self.process.poll() is None:
            return True

        try:
            # 使用npx启动MCP Server
            env = os.environ.copy()
            if self.work_dir:
                env["WORK_DIR"] = self.work_dir

            self.process = subprocess.Popen(
                ["npx", "-y", "@yc-w-cn/douyin-mcp-server@latest"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1
            )

            # 等待服务器启动
            time.sleep(2)
            return True
        except Exception as e:
            print(f"启动MCP Server失败: {e}")
            return False

    def stop_server(self):
        """停止MCP Server"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def _call_mcp_tool(self, tool_name, params):
        """调用MCP工具"""
        try:
            # 模拟MCP调用 - 实际上通过HTTP或子进程调用
            # 这里我们先实现一个简化的版本
            cmd = ["node", "-e", f"""
                const {{ spawn }} = require('child_process');
                const server = spawn('npx', ['-y', '@yc-w-cn/douyin-mcp-server@latest'], {{
                    stdio: ['pipe', 'pipe', 'pipe'],
                    env: {{ ...process.env, WORK_DIR: '{self.work_dir}' }}
                }});

                // 发送MCP请求
                const request = {{
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: {{
                        name: '{tool_name}',
                        arguments: {json.dumps(params)}
                    }},
                    id: 1
                }};

                console.log(JSON.stringify(request));

                // 注意：实际实现需要处理MCP协议通信
            """]

            # 由于MCP协议较复杂，我们先实现直接调用工具的方式
            # 使用subprocess直接调用MCP工具
            return self._call_direct_tool(tool_name, params)

        except Exception as e:
            raise Exception(f"调用MCP工具失败: {str(e)}")

    def _call_direct_tool(self, tool_name, params):
        """直接调用工具（简化实现）"""
        # 这里我们创建一个Node.js脚本来调用MCP工具
        script = f"""
        const {{ execSync }} = require('child_process');
        const fs = require('fs');
        const path = require('path');

        // 设置工作目录
        const workDir = '{self.work_dir}';
        if (!fs.existsSync(workDir)) {{
            fs.mkdirSync(workDir, {{ recursive: true }});
        }}

        // 这里应该通过MCP协议调用，但为了简化，我们直接模拟
        console.log(JSON.stringify({{
            tool: '{tool_name}',
            params: {json.dumps(params)},
            work_dir: workDir
        }}));
        """

        try:
            result = subprocess.run(
                ["node", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            else:
                raise Exception(f"工具调用失败: {result.stderr}")
        except Exception as e:
            raise Exception(f"直接调用失败: {str(e)}")

class DouyinDownloader:
    """抖音下载器（使用外部API）"""

    def __init__(self):
        # 使用现有的抖音解析API
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def parse_share_url(self, share_url):
        """解析分享链接"""
        try:
            # 清理URL
            url = share_url.strip()

            # 如果是短链接，需要先获取重定向
            if "v.douyin.com" in url:
                response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
                url = response.url

            # 提取视频ID
            video_id = None
            patterns = [
                r'/video/(\d+)',
                r'note/(\d+)',
                r'item_id=(\d+)',
                r'/(\d+)\?',
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    break

            if not video_id:
                # 尝试从路径中提取
                path_parts = urlparse(url).path.split('/')
                for part in path_parts:
                    if part.isdigit() and len(part) > 15:
                        video_id = part
                        break

            if not video_id:
                raise ValueError("无法从URL中提取视频ID")

            return video_id, url

        except Exception as e:
            raise Exception(f"解析分享链接失败: {str(e)}")

    def get_video_info(self, video_id):
        """获取视频信息（使用公开API）"""
        try:
            # 使用第三方抖音解析API
            # 注意：这些API可能会失效，需要定期维护
            apis = [
                f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}",
                f"https://api.douyin.wtf/api/iteminfo?item_id={video_id}",
                f"https://api.jiexi.la/?url=https://www.douyin.com/video/{video_id}",
            ]

            for api_url in apis:
                try:
                    response = requests.get(api_url, headers=self.headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()

                        # 尝试解析不同API的响应格式
                        video_info = self._parse_api_response(data, video_id)
                        if video_info:
                            return video_info
                except:
                    continue

            raise Exception("所有API都失败")

        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")

    def _parse_api_response(self, data, video_id):
        """解析API响应"""
        try:
            # 格式1: 官方API
            if "item_list" in data and data["item_list"]:
                item = data["item_list"][0]
                return self._parse_official_item(item, video_id)

            # 格式2: 第三方API
            if "item_list" in data or "data" in data:
                item = data.get("item_list", [{}])[0] or data.get("data", {})
                return self._parse_official_item(item, video_id)

            # 格式3: jiexi.la API
            if "data" in data and "video" in data["data"]:
                return self._parse_jiexi_item(data["data"], video_id)

            return None

        except:
            return None

    def _parse_official_item(self, item, video_id):
        """解析官方API格式"""
        # 获取基本信息
        title = item.get("desc", "")[:200]
        author = item.get("author", {}).get("nickname", "未知作者")

        # 获取统计信息
        stats = item.get("statistics", {})
        likes = stats.get("digg_count", 0)
        comments = stats.get("comment_count", 0)
        shares = stats.get("share_count", 0)

        # 获取视频URL
        video_url = None
        video_info = item.get("video", {})

        # 查找无水印视频URL
        for key in ["play_addr", "download_addr", "play_addr_lowbr"]:
            if key in video_info:
                url_data = video_info[key]
                if isinstance(url_data, dict) and "url_list" in url_data:
                    url_list = url_data["url_list"]
                    if url_list and isinstance(url_list, list) and len(url_list) > 0:
                        video_url = url_list[0].replace("/playwm/", "/play/")
                        break

        share_url = f"https://www.douyin.com/video/{video_id}"

        return {
            "title": title,
            "video_id": video_id,
            "share_url": share_url,
            "video_url": video_url,
            "author": author,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "duration": video_info.get("duration", 0) // 1000 if video_info.get("duration") else 0,
        }

    def _parse_jiexi_item(self, data, video_id):
        """解析jiexi.la API格式"""
        video_info = data.get("video", {})

        return {
            "title": data.get("title", "")[:200],
            "video_id": video_id,
            "share_url": data.get("share_url", f"https://www.douyin.com/video/{video_id}"),
            "video_url": video_info.get("url", "").replace("/playwm/", "/play/"),
            "author": data.get("author", {}).get("name", "未知作者"),
            "likes": data.get("like_count", 0),
            "comments": data.get("comment_count", 0),
            "shares": data.get("share_count", 0),
            "duration": video_info.get("duration", 0),
        }

    def download_video(self, video_url, save_path=None, filename=None):
        """下载视频"""
        if not video_url:
            raise ValueError("视频URL为空")

        if not save_path:
            save_path = "downloads"

        if not filename:
            timestamp = int(time.time())
            filename = f"douyin_video_{timestamp}.mp4"

        # 确保保存目录存在
        os.makedirs(save_path, exist_ok=True)

        full_path = os.path.join(save_path, filename)

        try:
            # 设置移动端User-Agent
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.douyin.com/",
            }

            response = requests.get(video_url, headers=headers, timeout=30, stream=True)
            if response.status_code != 200:
                raise Exception(f"下载失败，状态码: {response.status_code}")

            # 下载视频
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return full_path

        except Exception as e:
            # 清理可能不完整的文件
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except:
                    pass
            raise Exception(f"下载失败: {str(e)}")

class Vibrato():
    """抖音无水印视频下载器（主类）"""

    def __init__(self):
        super(Vibrato, self).__init__()
        self.downloader = DouyinDownloader()
        self.mcp_server = DouyinMCPServer()

    def run(self, url):
        """下载视频 - 兼容旧接口"""
        try:
            # 解析URL获取视频ID
            video_id, redirect_url = self.downloader.parse_share_url(url)

            # 获取视频信息
            video_info = self.downloader.get_video_info(video_id)

            if not video_info.get("video_url"):
                raise Exception("无法获取无水印视频URL")

            # 下载视频
            filename = f"{video_id}.mp4"
            save_path = self.downloader.download_video(
                video_info["video_url"],
                save_path="downloads",
                filename=filename
            )

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

    def get_video_by_url(self, url):
        """根据URL获取视频信息"""
        try:
            video_id, redirect_url = self.downloader.parse_share_url(url)
            return self.downloader.get_video_info(video_id)
        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")

    def search_videos(self, keyword, min_likes=0, max_results=20):
        """
        搜索抖音视频
        注意：抖音官方没有公开搜索API，这里使用简化的模拟搜索
        """
        # 由于抖音搜索API限制，这里返回一个示例结果
        # 实际应用中可能需要使用其他方法
        print(f"搜索关键词: {keyword}, 最小点赞: {min_likes}, 最大结果: {max_results}")
        print("提示：抖音官方搜索API有限制，这里返回示例数据")

        # 返回示例数据（实际使用时应替换为真实的搜索逻辑）
        return [
            {
                "title": f"示例视频 - {keyword}",
                "video_id": "7316983198304111891",
                "share_url": "https://www.douyin.com/video/7316983198304111891",
                "video_url": "",
                "author": "示例作者",
                "likes": max(1000, min_likes),
                "comments": 100,
                "shares": 50,
                "duration": 15,
            }
        ]

    def download_by_url(self, url, save_dir="downloads"):
        """通过URL下载视频（简化接口）"""
        result = self.run(url)
        return result["save_path"]

# 兼容旧代码的辅助函数
def test_douyin_download():
    """测试函数"""
    v = Vibrato()

    # 测试URL
    test_url = "https://v.douyin.com/nMuYtN/"

    try:
        print(f"测试URL: {test_url}")

        # 获取视频信息
        print("获取视频信息...")
        info = v.get_video_by_url(test_url)
        print(f"标题: {info['title']}")
        print(f"作者: {info['author']}")
        print(f"点赞: {info['likes']}")

        # 下载视频
        print("下载视频...")
        result = v.run(test_url)
        print(f"下载结果: {result}")

    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_douyin_download()