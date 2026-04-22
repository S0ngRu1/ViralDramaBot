#!/usr/bin/python
# -*- coding: utf-8 -*-

from Vibrato_new import Vibrato
import sys

def test_search():
    """测试搜索功能"""
    print("=== 测试搜索功能 ===")
    v = Vibrato()

    try:
        keyword = "美食"
        print(f"搜索关键词: {keyword}")
        print("正在搜索...")

        results = v.search_videos(keyword, min_likes=1000, max_results=10)
        print(f"找到 {len(results)} 个视频")

        if results:
            for i, video in enumerate(results[:5]):  # 只显示前5个
                print(f"\n--- 视频 {i+1} ---")
                print(f"标题: {video['title'][:50]}...")
                print(f"作者: {video['author']}")
                print(f"点赞: {video['likes']}")
                print(f"视频ID: {video['video_id']}")
                print(f"分享链接: {video['share_url']}")
                print(f"视频时长: {video['duration']}秒")
        else:
            print("未找到符合条件的视频")

    except Exception as e:
        print(f"搜索测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_download():
    """测试下载功能"""
    print("\n=== 测试下载功能 ===")
    v = Vibrato()

    # 使用一个已知的抖音分享链接进行测试
    test_urls = [
        "https://v.douyin.com/nMuYtN/",
        "https://v.douyin.com/iRgN1jXj/",
        "https://www.douyin.com/video/7316983198304111891",
    ]

    for test_url in test_urls:
        print(f"\n测试URL: {test_url}")
        try:
            print("正在获取视频信息...")
            video_info = v.get_video_by_url(test_url)

            print(f"标题: {video_info['title'][:50]}...")
            print(f"作者: {video_info['author']}")
            print(f"点赞: {video_info['likes']}")
            print(f"无水印视频URL: {video_info['video_url'][:80]}...")

            # 测试下载（可选）
            download_test = input("\n是否下载此视频？(y/n): ").lower()
            if download_test == 'y':
                print("开始下载...")
                result = v.run(test_url)
                print(f"下载结果: {result}")

        except Exception as e:
            print(f"下载测试失败: {e}")
            import traceback
            traceback.print_exc()

def test_min_likes_filter():
    """测试点赞数筛选功能"""
    print("\n=== 测试点赞数筛选功能 ===")
    v = Vibrato()

    try:
        keyword = "旅行"
        min_likes_list = [0, 1000, 5000, 10000]

        for min_likes in min_likes_list:
            print(f"\n搜索 '{keyword}'，最小点赞数: {min_likes}")
            results = v.search_videos(keyword, min_likes=min_likes, max_results=5)
            print(f"找到 {len(results)} 个视频")

            if results:
                for video in results:
                    print(f"  - {video['title'][:30]}... (点赞: {video['likes']})")

    except Exception as e:
        print(f"筛选测试失败: {e}")

def main():
    """主测试函数"""
    print("抖音无水印视频下载器测试")
    print("=" * 50)

    # 选择测试模式
    print("\n请选择测试模式:")
    print("1. 搜索功能测试")
    print("2. 下载功能测试")
    print("3. 点赞筛选测试")
    print("4. 全部测试")
    print("5. 退出")

    try:
        choice = input("\n请输入选择 (1-5): ").strip()

        if choice == '1':
            test_search()
        elif choice == '2':
            test_download()
        elif choice == '3':
            test_min_likes_filter()
        elif choice == '4':
            test_search()
            test_download()
            test_min_likes_filter()
        elif choice == '5':
            print("退出测试")
            return
        else:
            print("无效选择")

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()