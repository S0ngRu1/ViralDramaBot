"""
主程序入口

支持三种使用方式：
1. 命令行直接使用
2. 作为模块导入
3. 交互式菜单
"""

import sys
import argparse
from pathlib import Path
from config import initialize_app, config
from tools import get_douyin_download_link, download_douyin_video, parse_douyin_video_info
from logger import logger


def print_result(result: dict, detail: bool = False) -> None:
    """
    美化打印结果
    
    Args:
        result: 结果字典
        detail: 是否打印详细信息
    """
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


def cmd_get_link(args) -> int:
    """
    获取下载链接命令
    
    Args:
        args: 命令行参数
    
    Returns:
        int: 返回码
    """
    try:
        logger.info(f"获取下载链接: {args.link}")
        result = get_douyin_download_link(args.link)
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def cmd_download(args) -> int:
    """
    下载视频命令
    
    Args:
        args: 命令行参数
    
    Returns:
        int: 返回码
    """
    try:
        logger.info(f"下载视频: {args.link}")
        
        def progress_callback(progress):
            """进度回调函数"""
            percentage = progress.get('percentage', 0)
            downloaded = progress.get('downloaded', 0)
            total = progress.get('total', 0)
            
            if total > 0:
                # 计算进度条
                bar_length = 30
                filled = int(bar_length * percentage / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                # 格式化大小
                def format_bytes(b):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if b < 1024:
                            return f"{b:.1f}{unit}"
                        b /= 1024
                    return f"{b:.1f}TB"
                
                print(f"\r进度: [{bar}] {percentage:.1f}% "
                      f"({format_bytes(downloaded)}/{format_bytes(total)})", 
                      end='', flush=True)
        
        result = download_douyin_video(args.link, on_progress=progress_callback)
        print()  # 换行
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def cmd_parse(args) -> int:
    """
    解析视频信息命令
    
    Args:
        args: 命令行参数
    
    Returns:
        int: 返回码
    """
    try:
        logger.info(f"解析视频信息: {args.link}")
        result = parse_douyin_video_info(args.link)
        print_result(result, detail=True)
        return 0 if result['status'] == 'success' else 1
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return 1


def cmd_interactive(args) -> int:
    """
    交互式菜单
    
    Args:
        args: 命令行参数
    
    Returns:
        int: 返回码
    """
    while True:
        print("\n" + "="*60)
        print("抖音视频处理工具 - 交互式菜单")
        print("="*60)
        print("1. 获取无水印下载链接")
        print("2. 下载视频文件")
        print("3. 解析视频信息")
        print("4. 退出")
        print("="*60)
        
        choice = input("请选择操作 (1-4): ").strip()
        
        if choice == '1':
            link = input("请输入抖音分享链接: ").strip()
            if link:
                result = get_douyin_download_link(link)
                print_result(result, detail=True)
        
        elif choice == '2':
            link = input("请输入抖音分享链接: ").strip()
            if link:
                def progress_callback(progress):
                    percentage = progress.get('percentage', 0)
                    sys.stdout.write(f"\r下载进度: {percentage:.1f}%")
                    sys.stdout.flush()
                
                result = download_douyin_video(link, on_progress=progress_callback)
                print()
                print_result(result, detail=True)
        
        elif choice == '3':
            link = input("请输入抖音分享链接: ").strip()
            if link:
                result = parse_douyin_video_info(link)
                print_result(result, detail=True)
        
        elif choice == '4':
            print("退出程序")
            return 0
        
        else:
            print("❌ 无效的选择，请重试")


def main() -> int:
    """
    主函数
    
    Returns:
        int: 程序返回码
    """
    # 初始化应用
    if not initialize_app():
        return 1
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="抖音视频解析与下载工具",
        epilog="示例:\n"
               "  python main.py get-link 'https://v.douyin.com/xxxxx'\n"
               "  python main.py download 'https://v.douyin.com/xxxxx'\n"
               "  python main.py parse 'https://v.douyin.com/xxxxx'\n"
               "  python main.py interactive",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # get-link 命令
    parser_get_link = subparsers.add_parser(
        'get-link',
        help='获取抖音无水印下载链接'
    )
    parser_get_link.add_argument(
        'link',
        help='抖音分享链接或包含链接的文本'
    )
    parser_get_link.set_defaults(func=cmd_get_link)
    
    # download 命令
    parser_download = subparsers.add_parser(
        'download',
        help='下载抖音视频'
    )
    parser_download.add_argument(
        'link',
        help='抖音分享链接或包含链接的文本'
    )
    parser_download.set_defaults(func=cmd_download)
    
    # parse 命令
    parser_parse = subparsers.add_parser(
        'parse',
        help='解析抖音视频信息'
    )
    parser_parse.add_argument(
        'link',
        help='抖音分享链接或包含链接的文本'
    )
    parser_parse.set_defaults(func=cmd_parse)
    
    # interactive 命令
    parser_interactive = subparsers.add_parser(
        'interactive',
        help='交互式菜单'
    )
    parser_interactive.set_defaults(func=cmd_interactive)
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 如果没有指定命令，显示帮助信息
    if not args.command:
        parser.print_help()
        return 0
    
    # 执行对应的命令
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
