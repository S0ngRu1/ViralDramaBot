#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simple_search():
    """测试简单的抖音搜索"""
    print("=== 测试简单抖音搜索 ===")

    # 使用直接的方法搜索
    import requests
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 方法1: 直接访问抖音搜索页面
    print("\n方法1: 直接访问抖音搜索页面")
    try:
        keyword = "美食"
        search_url = f"https://www.douyin.com/search/{keyword}"

        session = requests.Session()
        session.headers.update(headers)

        # 访问首页获取cookies
        home_response = session.get("https://www.douyin.com/", timeout=10)
        print(f"首页访问状态: {home_response.status_code}")

        # 访问搜索页面
        search_response = session.get(search_url, timeout=10)
        print(f"搜索页面状态: {search_response.status_code}")
        print(f"页面大小: {len(search_response.text)} 字符")

        # 保存页面内容
        with open("real_search_page.html", "w", encoding="utf-8") as f:
            f.write(search_response.text)

        # 分析页面内容
        analyze_real_search_page(search_response.text)

        return True

    except Exception as e:
        print(f"方法1失败: {e}")
        return False

def analyze_real_search_page(html):
    """分析真实搜索页面"""
    print("\n分析搜索页面内容:")

    # 查找视频相关信息
    patterns = {
        "视频ID": r'href="/video/(\d+)"',
        "抖音号": r'抖音号：([^<]+)',
        "视频描述": r'desc[^>]*>([^<]+)</p>',
        "点赞数": r'点赞数[^>]*>([^<]+)</span>',
        "分享链接": r'https://v\.douyin\.com/[^"\']+',
    }

    for name, pattern in patterns.items():
        matches = re.findall(pattern, html)
        if matches:
            print(f"{name}: 找到 {len(matches)} 个匹配")
            for i, match in enumerate(matches[:3]):  # 显示前3个
                print(f"  {i+1}. {match[:100]}")
        else:
            print(f"{name}: 未找到匹配")

    # 查找JSON数据
    print("\n查找JSON数据:")
    json_patterns = [
        r'<script[^>]*id="RENDER_DATA"[^>]*>([^<]+)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'{"status_code":.+?}',
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            print(f"找到JSON数据 (模式: {pattern[:30]}...)")
            for i, match in enumerate(matches[:2]):
                print(f"JSON {i+1} 长度: {len(match)} 字符")
                print(f"前200字符: {match[:200]}...")

                # 尝试解析
                try:
                    import json
                    import urllib.parse

                    # 如果是URL编码的，先解码
                    if '%' in match:
                        decoded = urllib.parse.unquote(match)
                        data = json.loads(decoded)
                    else:
                        data = json.loads(match)

                    print(f"JSON解析成功，类型: {type(data)}")

                    # 保存解析后的数据
                    with open("parsed_data.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    print("解析后的数据已保存到 parsed_data.json")

                except Exception as e:
                    print(f"JSON解析失败: {e}")

def test_video_download():
    """测试视频下载功能"""
    print("\n=== 测试视频下载功能 ===")

    # 使用已知的视频ID测试
    test_video_ids = [
        "7316983198304111891",  # 示例视频ID
    ]

    for video_id in test_video_ids:
        print(f"\n测试视频ID: {video_id}")

        try:
            # 尝试获取视频信息
            from Vibrato import Vibrato
            v = Vibrato()

            # 构造URL
            video_url = f"https://www.douyin.com/video/{video_id}"
            print(f"视频URL: {video_url}")

            # 获取视频信息
            print("获取视频信息...")
            video_info = v.get_video_info_by_url(video_url)

            print(f"标题: {video_info['title']}")
            print(f"作者: {video_info['author']}")
            print(f"点赞: {video_info['likes']}")

            if video_info.get('video_url'):
                print(f"无水印URL: {video_info['video_url'][:100]}...")

                # 测试下载（可选）
                print("测试下载...")
                # result = v.run(video_url)
                # print(f"下载结果: {result}")
            else:
                print("无法获取无水印URL")

        except Exception as e:
            print(f"视频测试失败: {e}")

def main():
    """主测试函数"""
    print("抖音真实搜索功能测试")
    print("=" * 60)

    # 测试简单搜索
    test_simple_search()

    # 测试视频下载
    test_video_download()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("\n生成的文件:")
    print("- real_search_page.html: 真实搜索页面")
    print("- parsed_data.json: 解析后的数据（如果有）")

    print("\n建议:")
    print("1. 查看 real_search_page.html 分析页面结构")
    print("2. 检查 parsed_data.json 查看抖音的数据格式")
    print("3. 根据实际页面结构调整搜索解析逻辑")

if __name__ == "__main__":
    main()