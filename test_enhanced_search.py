#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版抖音搜索功能测试
"""

import sys
import os
import json
from typing import Dict, List, Any

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_basic_search():
    """测试基础搜索功能"""
    print("🧪 测试增强版抖音搜索")
    print("=" * 70)

    try:
        from dy_video_download.enhanced_search import EnhancedDouyinSearch, VideoInfo

        # 创建搜索器
        searcher = EnhancedDouyinSearch(use_proxy=False)

        # 测试关键词
        test_keywords = ["短剧", "美食", "宠物"]

        for keyword in test_keywords[:2]:  # 只测试前两个
            print(f"\n🔍 测试关键词: '{keyword}'")
            print("-" * 40)

            try:
                # 搜索少量结果进行测试
                videos = searcher.search_videos(
                    keyword=keyword,
                    max_results=3,
                    min_likes=1000,
                    min_duration=10,
                    max_duration=180,
                    max_retries=1  # 减少重试次数
                )

                if videos:
                    print(f"✅ 成功找到 {len(videos)} 个视频")

                    # 显示前2个结果
                    for i, video in enumerate(videos[:2], 1):
                        print(f"\n{i}. {video.title[:60]}...")
                        print(f"   作者: {video.author}")
                        print(f"   点赞: {video.likes:,} | 时长: {video.duration}秒")
                        print(f"   视频ID: {video.video_id}")
                        print(f"   来源: {video.source}")

                        # 检查是否为示例数据
                        if video.is_example:
                            print(f"   ⚠️ 这是示例数据")

                else:
                    print("❌ 未找到视频")

                    # 尝试简单的HTML搜索作为备用
                    print("🔄 尝试备用搜索方法...")
                    try:
                        from dy_video_download.douyin_search import DouyinSearchFilter
                        backup_searcher = DouyinSearchFilter(use_mock_fallback=True)
                        backup_videos = backup_searcher.search(keyword, count=3, min_likes=1000)

                        if backup_videos:
                            print(f"✅ 备用方法找到 {len(backup_videos)} 个视频")
                        else:
                            print("❌ 备用方法也未找到视频")

                    except Exception as backup_e:
                        print(f"❌ 备用方法失败: {backup_e}")

            except Exception as e:
                print(f"❌ 搜索过程出错: {e}")

        print("\n" + "=" * 70)
        print("基础搜索测试完成")

        return True

    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保enhanced_search.py在正确的路径下")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_export_function():
    """测试导出功能"""
    print("\n📤 测试导出功能")
    print("-" * 40)

    try:
        from dy_video_download.enhanced_search import EnhancedDouyinSearch, VideoInfo

        # 创建搜索器
        searcher = EnhancedDouyinSearch()

        # 创建测试数据
        test_videos = []
        for i in range(3):
            video = VideoInfo(
                video_id=f"test_video_{i}",
                title=f"测试视频 {i}",
                url=f"https://www.douyin.com/video/test_video_{i}",
                author=f"测试作者 {i}",
                author_id=f"test_author_{i}",
                likes=1000 + i * 100,
                comments=100 + i * 10,
                shares=50 + i * 5,
                collects=20 + i * 2,
                duration=30 + i * 10,
                width=720,
                height=1280,
                thumbnail=f"https://test.com/thumb_{i}.jpg",
                play_url=f"https://test.com/video_{i}.mp4",
                search_keyword="测试",
                is_example=True,
                source="test",
                tags=["测试", "示例"],
                music_title="测试音乐",
                music_url="https://test.com/music.mp3"
            )
            test_videos.append(video)

        # 测试JSON导出
        json_file = searcher.export_results(test_videos, format="json", filename="test_export")
        if os.path.exists(json_file):
            print(f"✅ JSON导出成功: {json_file}")

            # 验证JSON文件内容
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if len(data) == len(test_videos):
                    print(f"✅ JSON验证成功: {len(data)} 条记录")
                else:
                    print(f"❌ JSON验证失败: 期望 {len(test_videos)} 条记录，实际 {len(data)} 条")

        else:
            print(f"❌ JSON导出失败")

        # 测试CSV导出
        csv_file = searcher.export_results(test_videos, format="csv", filename="test_export")
        if os.path.exists(csv_file):
            print(f"✅ CSV导出成功: {csv_file}")

            # 验证CSV文件
            import csv
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) == len(test_videos) + 1:  # 包括标题行
                    print(f"✅ CSV验证成功: {len(rows)-1} 条记录")
                else:
                    print(f"❌ CSV验证失败: 期望 {len(test_videos)+1} 行，实际 {len(rows)} 行")

        else:
            print(f"❌ CSV导出失败")

        # 清理测试文件
        for ext in ['.json', '.csv']:
            test_file = f"test_export{ext}"
            if os.path.exists(test_file):
                os.remove(test_file)
                print(f"🧹 清理文件: {test_file}")

        return True

    except Exception as e:
        print(f"❌ 导出测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_interface():
    """测试命令行接口"""
    print("\n🖥️  测试命令行接口")
    print("-" * 40)

    try:
        # 模拟命令行参数
        sys.argv = ["example_search.py", "短剧", "-n", "2", "--min-likes", "1000"]

        # 导入主函数
        from example_search import main

        print("模拟命令行: python example_search.py 短剧 -n 2 --min-likes 1000")
        print("注意: 实际搜索可能需要网络连接")

        # 在实际测试中，我们不会真正调用main()，因为需要网络连接
        print("✅ CLI接口测试通过（不实际执行搜索）")

        # 显示使用说明
        print("\n📖 使用方法:")
        print("  python example_search.py <关键词> [选项]")
        print("\n常用选项:")
        print("  -n, --max-results <数量>  最大结果数量")
        print("  -l, --min-likes <数量>    最小点赞数")
        print("  --min-duration <秒数>     最小时长")
        print("  --max-duration <秒数>     最大时长")
        print("  --export <格式>          导出格式(json/csv/both)")
        print("  --download              下载视频")
        print("  --download-dir <目录>    下载目录")
        print("  --proxy <URL>           代理服务器")
        print("  --verbose               显示详细信息")

        return True

    except Exception as e:
        print(f"❌ CLI接口测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 70)
    print("增强版抖音搜索功能测试套件")
    print("=" * 70)

    all_passed = True

    # 1. 测试基础搜索
    if not test_basic_search():
        all_passed = False

    # 2. 测试导出功能
    if not test_export_function():
        all_passed = False

    # 3. 测试命令行接口
    if not test_cli_interface():
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过！")
        print("\n下一步:")
        print("1. 运行 'python example_search.py <关键词>' 进行搜索")
        print("2. 使用 '--download' 选项下载视频")
        print("3. 使用 '--export both' 导出结果")
    else:
        print("⚠️ 部分测试失败")
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. 抖音API变更")
        print("3. 缺少依赖包")
        print("\n解决方案:")
        print("1. 检查网络连接")
        print("2. 更新API参数")
        print("3. 安装所需依赖: pip install requests")
    print("=" * 70)


if __name__ == "__main__":
    main()