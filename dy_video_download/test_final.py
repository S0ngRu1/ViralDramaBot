#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Vibrato import Vibrato

def test_vibrato_class():
    """测试Vibrato类的基本功能"""
    print("=== 测试Vibrato类基本功能 ===")
    v = Vibrato()

    # 测试1: 搜索功能
    print("\n1. 测试搜索功能:")
    try:
        keyword = "美食"
        min_likes = 1000
        print(f"  搜索关键词: {keyword}")
        print(f"  最小点赞数: {min_likes}")

        results = v.search_videos(keyword, min_likes=min_likes)
        print(f"  找到 {len(results)} 个结果")

        for i, video in enumerate(results):
            print(f"  结果{i+1}: {video['title']}")
            print(f"      点赞: {video['likes']}")
            print(f"      链接: {video['url']}")
            print()

    except Exception as e:
        print(f"  搜索测试失败: {e}")

    # 测试2: 获取视频信息
    print("\n2. 测试获取视频信息:")
    try:
        # 使用示例URL
        test_url = "https://www.douyin.com/video/7316983198304111891"
        print(f"  测试URL: {test_url}")

        video_info = v.get_video_info_by_url(test_url)
        print(f"  标题: {video_info['title']}")
        print(f"  作者: {video_info['author']}")
        print(f"  点赞: {video_info['likes']}")
        print(f"  视频ID: {video_info['video_id']}")
        print(f"  无水印URL: {video_info['video_url'][:80]}...")

    except Exception as e:
        print(f"  获取视频信息失败: {e}")

    # 测试3: 下载功能（不实际下载）
    print("\n3. 测试下载功能（模拟）:")
    try:
        test_url = "https://www.douyin.com/video/7316983198304111891"
        print(f"  测试URL: {test_url}")
        print("  注意：这只是模拟测试，不实际下载文件")

        # 这里只是演示流程，实际下载需要有效URL
        result = v.run(test_url)
        print(f"  下载结果: {result.get('status', 'unknown')}")
        print(f"  消息: {result.get('message', '')}")

    except Exception as e:
        print(f"  下载测试失败: {e}")

def test_environment():
    """测试环境依赖"""
    print("\n=== 测试环境依赖 ===")

    # 检查必要的包
    try:
        import requests
        print("✓ requests 已安装")
    except ImportError:
        print("✗ requests 未安装")

    try:
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5 已安装")
    except ImportError:
        print("✗ PyQt5 未安装")

    # 检查下载目录
    download_dir = "downloads"
    if os.path.exists(download_dir):
        print(f"✓ 下载目录存在: {download_dir}")
    else:
        print(f"✗ 下载目录不存在: {download_dir}")

def main():
    """主测试函数"""
    print("抖音无水印下载器 - 功能测试")
    print("=" * 60)

    test_environment()
    test_vibrato_class()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("\n使用说明:")
    print("1. 运行 Main.py 启动图形界面")
    print("2. 在界面中可选择搜索模式或下载模式")
    print("3. 搜索模式: 输入关键词，设置最小点赞数，点击搜索")
    print("4. 下载模式: 输入视频链接，点击下载")
    print("5. 使用左右箭头键在搜索结果中导航")

if __name__ == '__main__':
    main()