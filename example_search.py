#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
抖音视频搜索示例 - 支持多种搜索方法
"""

import sys
import os
import argparse
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="抖音视频搜索工具")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("-n", "--max-results", type=int, default=10, help="最大结果数量 (默认: 10)")
    parser.add_argument("-l", "--min-likes", type=int, default=0, help="最小点赞数 (默认: 0)")
    parser.add_argument("--min-duration", type=int, default=0, help="最小时长(秒) (默认: 0)")
    parser.add_argument("--max-duration", type=int, default=0, help="最大时长(秒) (默认: 0, 表示不限制)")
    parser.add_argument("--export", choices=["json", "csv", "both"], default="json",
                       help="导出格式 (默认: json)")
    parser.add_argument("--download", action="store_true", help="下载视频")
    parser.add_argument("--download-dir", default="./downloads", help="下载目录 (默认: ./downloads)")
    parser.add_argument("--proxy", help="代理URL (如: http://127.0.0.1:7890)")
    parser.add_argument("--method", choices=["playwright", "api", "dom", "auto"], default="auto",
                       help="搜索方法: playwright(推荐), api(直接API), dom(网页解析), auto(自动选择)")
    parser.add_argument("--headless", action="store_true", help="使用无头模式(Playwright)")
    parser.add_argument("--scroll-times", type=int, default=5, help="滚动次数(Playwright) (默认: 5)")
    parser.add_argument("--scroll-delay", type=float, default=2.0, help="滚动延迟(秒) (默认: 2.0)")
    parser.add_argument("--verbose", action="store_true", help="显示详细信息")

    args = parser.parse_args()

    print(f"🚀 抖音视频搜索工具 v2.0")
    print(f"🔍 搜索关键词: {args.keyword}")
    print(f"📊 设置: 最多{args.max_results}个结果, 点赞≥{args.min_likes}")
    print(f"🔧 方法: {args.method}")
    if args.min_duration > 0 or args.max_duration > 0:
        print(f"⏱️  时长: {args.min_duration}-{args.max_duration if args.max_duration > 0 else '∞'}秒")
    print("=" * 80)

    # 导入必要的模块
    try:
        from dy_video_download.enhanced_search import EnhancedDouyinSearch, VideoInfo as APIVideoInfo
        API_SEARCH_AVAILABLE = True
    except ImportError:
        API_SEARCH_AVAILABLE = False
        print("⚠️ 增强版API搜索不可用")

    try:
        from dy_video_download.playwright_search import SyncDouyinSearcher, VideoInfo as PlaywrightVideoInfo
        PLAYWRIGHT_AVAILABLE = True
    except ImportError as e:
        PLAYWRIGHT_AVAILABLE = False
        print(f"⚠️ Playwright搜索不可用: {e}")
        print("请安装: pip install playwright && playwright install chromium")

    try:
        from dy_video_download.douyin_search import DouyinSearchFilter, VideoInfo as DOMVideoInfo
        DOM_SEARCH_AVAILABLE = True
    except ImportError:
        DOM_SEARCH_AVAILABLE = False
        print("⚠️ DOM搜索不可用")

    # 确定搜索方法
    search_method = args.method
    if search_method == "auto":
        if PLAYWRIGHT_AVAILABLE:
            search_method = "playwright"
        elif API_SEARCH_AVAILABLE:
            search_method = "api"
        elif DOM_SEARCH_AVAILABLE:
            search_method = "dom"
        else:
            print("❌ 没有可用的搜索方法")
            return

    print(f"🎯 使用搜索方法: {search_method}")

    try:
        videos = []

        if search_method == "playwright" and PLAYWRIGHT_AVAILABLE:
            print("🎬 使用Playwright方法搜索...")
            use_proxy = bool(args.proxy)
            searcher = SyncDouyinSearcher(
                headless=args.headless,
                use_proxy=use_proxy,
                proxy_url=args.proxy
            )

            videos = searcher.search_videos(
                keyword=args.keyword,
                max_results=args.max_results,
                scroll_times=args.scroll_times,
                scroll_delay=args.scroll_delay,
                min_likes=args.min_likes,
                min_duration=args.min_duration,
                max_duration=args.max_duration
            )

            # 导出函数
            export_func = searcher.searcher.export_results if hasattr(searcher, 'searcher') else None

        elif search_method == "api" and API_SEARCH_AVAILABLE:
            print("🌐 使用API方法搜索...")
            use_proxy = bool(args.proxy)
            searcher = EnhancedDouyinSearch(use_proxy=use_proxy, proxy_url=args.proxy)

            videos = searcher.search_videos(
                keyword=args.keyword,
                max_results=args.max_results,
                min_likes=args.min_likes,
                min_duration=args.min_duration,
                max_duration=args.max_duration
            )

            # 导出函数
            export_func = searcher.export_results

        elif search_method == "dom" and DOM_SEARCH_AVAILABLE:
            print("🕸️  使用DOM方法搜索...")
            searcher = DouyinSearchFilter(use_mock_fallback=True)

            videos = searcher.search(
                keyword=args.keyword,
                count=args.max_results,
                min_likes=args.min_likes,
                min_duration=args.min_duration,
                max_duration=args.max_duration
            )

            # 转换为通用格式
            from dy_video_download.playwright_search import VideoInfo
            converted_videos = []
            for v in videos:
                if hasattr(v, 'to_dict'):
                    video_dict = v.to_dict()
                else:
                    video_dict = v

                converted_videos.append(VideoInfo(
                    video_id=video_dict.get('video_id', ''),
                    title=video_dict.get('title', ''),
                    description=video_dict.get('description', ''),
                    url=video_dict.get('url', ''),
                    author=video_dict.get('author', ''),
                    author_id=video_dict.get('author_id', ''),
                    author_unique_id=video_dict.get('author_unique_id', ''),
                    author_avatar=video_dict.get('author_avatar', ''),
                    likes=video_dict.get('likes', 0),
                    comments=video_dict.get('comments', 0),
                    shares=video_dict.get('shares', 0),
                    collects=video_dict.get('collects', 0),
                    duration=video_dict.get('duration', 0),
                    width=video_dict.get('width', 720),
                    height=video_dict.get('height', 1280),
                    thumbnail=video_dict.get('thumbnail', ''),
                    play_url=video_dict.get('play_url', ''),
                    download_url=video_dict.get('download_url'),
                    create_time=video_dict.get('create_time', 0),
                    search_keyword=args.keyword,
                    source=video_dict.get('source', 'dom'),
                    tags=video_dict.get('tags', []),
                    music_title=video_dict.get('music_title', ''),
                    music_url=video_dict.get('music_url', ''),
                    is_ad=False,
                    aweme_type=0
                ))

            videos = converted_videos
            # DOM搜索没有导出函数，使用Playwright的导出
            from dy_video_download.playwright_search import DouyinPlaywrightSearcher
            temp_searcher = DouyinPlaywrightSearcher()
            export_func = temp_searcher.export_results

        else:
            print(f"❌ 搜索方法 '{search_method}' 不可用")
            return

        if not videos:
            print("❌ 未找到符合条件的视频")
            return

        print(f"✅ 成功找到 {len(videos)} 个视频")
        print("\n" + "=" * 80)

        # 显示结果
        for i, video in enumerate(videos, 1):
            print(f"\n{i:2d}. {video.title[:80]}...")
            print(f"    作者: {video.author} | 点赞: {video.likes:,} | 时长: {video.duration}秒")

            # 显示额外的统计信息（如果可用）
            if hasattr(video, 'comments') and video.comments > 0:
                print(f"    评论: {video.comments:,}", end="")
            if hasattr(video, 'shares') and video.shares > 0:
                print(f" | 分享: {video.shares:,}", end="")
            if hasattr(video, 'collects') and video.collects > 0:
                print(f" | 收藏: {video.collects:,}", end="")
            print()

            print(f"    视频ID: {video.video_id}")
            print(f"    链接: {video.url}")

            # 显示播放地址（如果可用且不为空）
            if hasattr(video, 'play_url') and video.play_url:
                play_url_short = video.play_url[:60] + "..." if len(video.play_url) > 60 else video.play_url
                print(f"    播放地址: {play_url_short}")

            if hasattr(video, 'tags') and video.tags:
                print(f"    标签: {', '.join(video.tags[:5])}")

            if hasattr(video, 'music_title') and video.music_title:
                print(f"    音乐: {video.music_title}")

        print("\n" + "=" * 80)

        # 导出结果
        if args.export in ["json", "both"]:
            try:
                if export_func:
                    json_file = export_func(videos, format="json")
                    print(f"💾 JSON文件已保存: {json_file}")
                else:
                    print("❌ 导出功能不可用")
            except Exception as e:
                print(f"❌ JSON导出失败: {e}")

        if args.export in ["csv", "both"]:
            try:
                if export_func:
                    csv_file = export_func(videos, format="csv")
                    print(f"💾 CSV文件已保存: {csv_file}")
                else:
                    print("❌ 导出功能不可用")
            except Exception as e:
                print(f"❌ CSV导出失败: {e}")

        # 下载视频
        if args.download:
            print(f"\n⬇️  开始下载视频到目录: {args.download_dir}")
            download_count = 0

            # 使用增强版API搜索的下载功能
            if API_SEARCH_AVAILABLE and search_method != "api":
                print("🔄 使用API方法下载视频...")
                use_proxy = bool(args.proxy)
                download_searcher = EnhancedDouyinSearch(use_proxy=use_proxy, proxy_url=args.proxy)
            else:
                download_searcher = searcher

            if hasattr(download_searcher, 'download_video'):
                for i, video in enumerate(videos[:3], 1):  # 只下载前3个
                    print(f"\n[{i}/{min(3, len(videos))}] 正在下载: {video.title[:50]}...")

                    # 确保视频信息有download_url字段
                    if not hasattr(video, 'download_url'):
                        from dy_video_download.playwright_search import VideoInfo
                        video = VideoInfo(
                            video_id=video.video_id,
                            title=video.title,
                            description=getattr(video, 'description', ''),
                            url=video.url,
                            author=video.author,
                            author_id=getattr(video, 'author_id', ''),
                            author_unique_id=getattr(video, 'author_unique_id', ''),
                            author_avatar=getattr(video, 'author_avatar', ''),
                            likes=getattr(video, 'likes', 0),
                            comments=getattr(video, 'comments', 0),
                            shares=getattr(video, 'shares', 0),
                            collects=getattr(video, 'collects', 0),
                            duration=getattr(video, 'duration', 0),
                            width=getattr(video, 'width', 720),
                            height=getattr(video, 'height', 1280),
                            thumbnail=getattr(video, 'thumbnail', ''),
                            play_url=getattr(video, 'play_url', ''),
                            search_keyword=args.keyword,
                            source=getattr(video, 'source', ''),
                            tags=getattr(video, 'tags', []),
                            music_title=getattr(video, 'music_title', ''),
                            music_url=getattr(video, 'music_url', ''),
                            is_ad=getattr(video, 'is_ad', False),
                            aweme_type=getattr(video, 'aweme_type', 0)
                        )

                    filepath = download_searcher.download_video(video, args.download_dir)

                    if filepath:
                        print(f"   ✅ 下载成功: {os.path.basename(filepath)}")
                        download_count += 1
                    else:
                        print(f"   ❌ 下载失败")

                    # 添加延迟，避免请求过快
                    import time
                    time.sleep(2)

                print(f"\n📥 下载完成: {download_count}个视频")
            else:
                print("❌ 当前搜索器不支持视频下载")

        # 显示统计信息
        print("\n📈 统计信息:")
        if videos:
            avg_likes = sum(v.likes for v in videos) // len(videos)
            print(f"   平均点赞数: {avg_likes:,}")

            avg_duration = sum(v.duration for v in videos) // len(videos)
            print(f"   平均时长: {avg_duration}秒")

            # 查找最新视频
            if hasattr(videos[0], 'create_time') and videos[0].create_time > 0:
                from datetime import datetime
                latest = max(videos, key=lambda x: x.create_time)
                latest_time = datetime.fromtimestamp(latest.create_time).strftime("%Y-%m-%d %H:%M:%S")
                print(f"   最新视频: {latest_time}")

            # 统计来源
            sources = {}
            for v in videos:
                source = getattr(v, 'source', 'unknown')
                sources[source] = sources.get(source, 0) + 1

            if sources:
                print(f"   来源分布: {', '.join([f'{k}:{v}' for k, v in sources.items()])}")

    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断操作")
    except ImportError as e:
        print(f"\n❌ 导入模块失败: {e}")
        print("请确保所有依赖都已安装:")
        print("  pip install requests playwright")
        print("  playwright install chromium")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        else:
            print("使用 --verbose 查看详细错误信息")


if __name__ == "__main__":
    main()