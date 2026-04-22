#!/usr/bin/python
# -*- coding: utf-8 -*-

from Vibrato_new import Vibrato
import sys

def test_download_by_url():
    """测试通过URL下载"""
    print("=== 测试URL下载功能 ===")
    v = Vibrato()

    # 测试URL列表（需要替换为实际的抖音分享链接）
    test_urls = [
        # 示例URL，实际使用时需要替换
        "https://v.douyin.com/nMuYtN/",
    ]

    for url in test_urls:
        print(f"\n测试URL: {url}")
        try:
            print("1. 获取视频信息...")
            video_info = v.get_video_by_url(url)
            print(f"   标题: {video_info['title']}")
            print(f"   作者: {video_info['author']}")
            print(f"   点赞: {video_info['likes']}")
            print(f"   无水印URL: {video_info['video_url'][:100]}...")

            print("\n2. 下载视频...")
            result = v.run(url)
            print(f"   下载结果: {result}")

            return True

        except Exception as e:
            print(f"   失败: {e}")
            import traceback
            traceback.print_exc()

    return False

def test_search_simple():
    """测试简单搜索"""
    print("\n=== 测试搜索功能 ===")
    v = Vibrato()

    try:
        keyword = "旅行"
        print(f"搜索关键词: {keyword}")

        results = v.search_videos(keyword, min_likes=100, max_results=5)
        print(f"找到 {len(results)} 个视频")

        if results:
            for i, video in enumerate(results):
                print(f"\n{i+1}. {video['title'][:50]}...")
                print(f"   作者: {video['author']}")
                print(f"   点赞: {video['likes']}")
                print(f"   分享链接: {video['share_url']}")

                if video.get('video_url'):
                    print(f"   无水印URL: {video['video_url'][:80]}...")

        return True

    except Exception as e:
        print(f"搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试"""
    print("抖音下载器功能测试")
    print("=" * 50)

    success_count = 0

    # 测试下载功能
    if test_download_by_url():
        success_count += 1

    # 测试搜索功能
    if test_search_simple():
        success_count += 1

    print(f"\n{'='*50}")
    print(f"测试完成。成功: {success_count}/2 项功能")

if __name__ == '__main__':
    main()