#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
抖音搜索机制研究

研究抖音的真实搜索API和网页结构
"""

import requests
import re
import json
import time
from urllib.parse import urlencode

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

def test_search_page():
    """测试抖音搜索页面"""
    print("测试抖音搜索页面...")

    keyword = "美食"
    search_url = "https://www.douyin.com/search/" + keyword

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # 先访问首页获取cookies
        home_response = session.get("https://www.douyin.com/", timeout=10)
        print(f"首页访问状态: {home_response.status_code}")
        print(f"Cookies: {session.cookies.get_dict()}")

        # 访问搜索页面
        response = session.get(search_url, timeout=10)
        print(f"搜索页面状态: {response.status_code}")
        print(f"页面大小: {len(response.text)} 字符")

        # 保存页面内容用于分析
        with open("search_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("页面已保存到 search_page.html")

        # 分析页面内容
        analyze_search_page(response.text)

    except Exception as e:
        print(f"搜索页面测试失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_search_page(html):
    """分析搜索页面HTML"""
    print("\n分析搜索页面HTML...")

    # 查找可能的API调用
    patterns = [
        r'<script[^>]*>([^<]+)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'RENDER_DATA\s*=\s*"([^"]+)"',
        r'<script[^>]*id="RENDER_DATA"[^>]*>([^<]+)</script>',
        r'https://www\.douyin\.com/aweme/[^"]+',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            print(f"找到匹配模式: {pattern[:50]}...")
            for i, match in enumerate(matches[:3]):  # 只显示前3个
                print(f"匹配 {i+1}: {match[:200]}...")
            print()

    # 查找视频相关的内容
    video_patterns = [
        r'href="/video/(\d+)"',
        r'data-video-id="(\d+)"',
        r'抖音号：([^<]+)',
        r'desc[^>]*>([^<]+)</p>',
    ]

    print("查找视频相关信息:")
    for pattern in video_patterns:
        matches = re.findall(pattern, html)
        if matches:
            print(f"模式 '{pattern}': 找到 {len(matches)} 个匹配")
            for match in matches[:5]:
                print(f"  - {match[:100]}")

def test_search_api():
    """测试抖音搜索API"""
    print("\n测试抖音搜索API...")

    # 尝试不同的API端点
    apis = [
        {
            "name": "移动端搜索API",
            "url": "https://www.douyin.com/aweme/v1/web/general/search/single/",
            "params": {
                "device_platform": "webapp",
                "aid": "6383",
                "channel": "channel_pc_web",
                "search_channel": "aweme_video_web",
                "sort_type": "0",
                "publish_time": "0",
                "keyword": "美食",
                "search_source": "normal_search",
                "query_correct_type": "1",
                "is_filter_search": "0",
                "offset": "0",
                "count": "10",
                "pc_client_type": "1",
                "version_code": "170400",
                "version_name": "17.4.0",
            },
            "headers": MOBILE_HEADERS
        },
        {
            "name": "Web搜索API",
            "url": "https://www.douyin.com/aweme/v1/web/search/item/",
            "params": {
                "device_platform": "web",
                "aid": "6383",
                "channel": "channel_pc_web",
                "search_channel": "aweme_video_web",
                "keyword": "美食",
                "search_source": "normal_search",
                "query_correct_type": "1",
                "is_filter_search": "0",
                "offset": "0",
                "count": "10",
            },
            "headers": HEADERS
        }
    ]

    session = requests.Session()

    for api in apis:
        print(f"\n测试API: {api['name']}")
        try:
            # 设置headers
            headers = {**api['headers']}
            headers.update({
                "Referer": "https://www.douyin.com/search/美食",
                "Accept": "application/json, text/plain, */*",
            })

            # 发送请求
            response = session.get(
                api['url'],
                params=api['params'],
                headers=headers,
                timeout=10
            )

            print(f"状态码: {response.status_code}")
            print(f"响应大小: {len(response.text)} 字符")

            # 尝试解析JSON
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"JSON解析成功，结构: {type(data)}")

                    # 保存API响应
                    filename = f"api_response_{api['name']}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"API响应已保存到 {filename}")

                    # 分析数据结构
                    analyze_api_response(data, api['name'])

                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}")
                    print(f"响应前200字符: {response.text[:200]}")

                    # 保存原始响应
                    filename = f"raw_response_{api['name']}.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    print(f"原始响应已保存到 {filename}")

        except Exception as e:
            print(f"API请求失败: {e}")

def analyze_api_response(data, api_name):
    """分析API响应数据结构"""
    print(f"\n分析 {api_name} 的响应结构:")

    def explore_structure(obj, path="", depth=0):
        if depth > 3:  # 限制递归深度
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if isinstance(value, (dict, list)):
                    print("  " * depth + f"{key}: {type(value)}")
                    explore_structure(value, new_path, depth + 1)
                else:
                    print("  " * depth + f"{key}: {value}"[:100])
        elif isinstance(obj, list):
            if obj:
                print("  " * depth + f"列表，长度: {len(obj)}")
                if len(obj) > 0:
                    explore_structure(obj[0], f"{path}[0]", depth + 1)

    explore_structure(data)

    # 特别查找视频数据
    print("\n查找视频数据:")

    def find_video_data(obj, path=""):
        videos = []

        if isinstance(obj, dict):
            # 检查常见的关键词
            video_keys = ["aweme_info", "item_list", "aweme_list", "video", "data"]
            for key in video_keys:
                if key in obj:
                    print(f"找到关键字段: {path}.{key}")

            # 递归搜索
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                videos.extend(find_video_data(value, new_path))

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                videos.extend(find_video_data(item, f"{path}[{i}]"))

        return videos

    find_video_data(data)

def test_real_search():
    """测试真实搜索功能"""
    print("\n测试真实搜索功能...")

    # 使用已知可用的抖音解析服务
    search_services = [
        {
            "name": "抖音解析服务1",
            "url": "https://api.jiexi.la/",
            "params": {"url": "https://www.douyin.com/search/美食"},
        },
        {
            "name": "抖音解析服务2",
            "url": "https://api.52jiexi.top/",
            "params": {"url": "https://www.douyin.com/search/美食"},
        },
    ]

    session = requests.Session()

    for service in search_services:
        print(f"\n测试服务: {service['name']}")
        try:
            response = session.get(
                service['url'],
                params=service['params'],
                headers=HEADERS,
                timeout=10
            )

            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"服务响应成功，保存到文件")

                    filename = f"service_{service['name']}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                except:
                    print(f"响应不是JSON，保存为文本")
                    filename = f"service_{service['name']}.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(response.text)

        except Exception as e:
            print(f"服务请求失败: {e}")

def main():
    """主函数"""
    print("抖音搜索机制研究")
    print("=" * 60)

    # 测试搜索页面
    test_search_page()

    # 测试搜索API
    test_search_api()

    # 测试第三方解析服务
    test_real_search()

    print("\n" + "=" * 60)
    print("研究完成！")
    print("\n生成的文件:")
    print("- search_page.html: 搜索页面HTML")
    print("- api_response_*.json: API响应")
    print("- raw_response_*.txt: 原始API响应")
    print("- service_*.json/txt: 第三方服务响应")

if __name__ == "__main__":
    main()