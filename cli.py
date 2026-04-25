#!/usr/bin/env python3
"""
ViralDramaBot 命令行工具

主要命令：
  douyin download   下载抖音视频
  douyin get-link   获取下载链接
  douyin parse      解析视频信息
"""

import sys
import argparse
from pathlib import Path

# 添加src目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core import initialize_app, config, logger
from src.ingestion.douyin import get_downloader


def print_result(result: dict, detail: bool = False) -> None:
    """美化打印结果"""
    status = result.get('status', 'unknown')
    message = result.get('message', '')
    
    print(f"\n{'='*60}")
    print(f"状态: {status}")
    print(f"消息: {message}")
    
    if detail and status == 'success':
        for key, value in result.items():
            if key not in ['status', 'message']:
                print(f"{key}: {value}")
    
    print(f"{'='*60}\n")


def cmd_douyin_download(args) -> int:
    """下载抖音视频"""
    try:
        logger.info(f"下载视频: {args.link}")
        
        downloader = get_downloader()
        
        def progress_callback(progress):
            """进度回调函数"""
            percentage = progress.get('percentage', 0)
            downloaded = progress.get('downloaded', 0)
            total = progress.get('total', 0)
            
            if total > 0:
                bar_length = 30
                filled = int(bar_length * percentage / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                def format_bytes(b):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if b < 1024:
                            return f"{b:.1f}{unit}"
                        b /= 1024
                    return f"{b:.1f}TB"
                
                print(f"\r进度: [{bar}] {percentage:.1f}% "
                      f"({format_bytes(downloaded)}/{format_bytes(total)})", 
                      end='', flush=True)
        
        result = downloader.download_video(args.link, on_progress=progress_callback)
        print()  # 换行
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def cmd_douyin_get_link(args) -> int:
    """获取抖音下载链接"""
    try:
        logger.info(f"获取下载链接: {args.link}")
        downloader = get_downloader()
        result = downloader.get_download_link(args.link)
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def cmd_douyin_parse(args) -> int:
    """解析抖音视频信息"""
    try:
        logger.info(f"解析视频: {args.link}")
        downloader = get_downloader()
        result = downloader.parse_video_info(args.link)
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def main():
    """主程序入口"""
    # 初始化应用
    if not initialize_app():
        return 1
    
    # 创建主解析器
    parser = argparse.ArgumentParser(
        description='ViralDramaBot - 短剧自动化流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python cli.py douyin download "https://v.douyin.com/xxxxx"
  python cli.py douyin get-link "https://v.douyin.com/xxxxx"
  python cli.py douyin parse "https://v.douyin.com/xxxxx"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 抖音子命令
    douyin_parser = subparsers.add_parser('douyin', help='抖音相关功能')
    douyin_subparsers = douyin_parser.add_subparsers(dest='subcommand')
    
    # douyin download
    download_parser = douyin_subparsers.add_parser('download', help='下载视频')
    download_parser.add_argument('link', help='抖音分享链接')
    download_parser.set_defaults(func=cmd_douyin_download)
    
    # douyin get-link
    getlink_parser = douyin_subparsers.add_parser('get-link', help='获取下载链接')
    getlink_parser.add_argument('link', help='抖音分享链接')
    getlink_parser.set_defaults(func=cmd_douyin_get_link)
    
    # douyin parse
    parse_parser = douyin_subparsers.add_parser('parse', help='解析视频信息')
    parse_parser.add_argument('link', help='抖音分享链接')
    parse_parser.set_defaults(func=cmd_douyin_parse)
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果没有指定命令，显示帮助
    if not hasattr(args, 'func'):
        parser.print_help()
        return 0
    
    # 执行命令
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
