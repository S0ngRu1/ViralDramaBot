#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ViralDramaBot 打包环境专用入口点
用于处理 PyInstaller 打包后的路径定位并启动 FastAPI 服务
"""

import os
import sys
import multiprocessing
import threading
import time
import webbrowser
from pathlib import Path
import logging

def setup_env():
    """配置打包运行时的环境变量和路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 EXE 运行，_MEIPASS 是 PyInstaller 的临时解压目录
        bundle_dir = Path(getattr(sys, '_MEIPASS', os.path.abspath(".")))
        # 将解压后的根目录添加到 sys.path，确保能找到 src 模块
        sys.path.insert(0, str(bundle_dir))
        
        # 切换工作目录到 EXE 所在目录，而不是临时目录
        # 这样生成的数据库和下载的视频会放在 EXE 旁边
        os.chdir(Path(sys.executable).parent)
    else:
        bundle_dir = Path(__file__).parent
        sys.path.insert(0, str(bundle_dir))

def main():
    setup_env()
    
    # ===== 日志输出到控制台 =====
    # 先确保 sys.stdout 正常（控制台已开启）
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

    # 配置根 logger，输出到标准错误流
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True   # 强制覆盖已有配置
    )
    # ============================
    
    # 延迟导入，确保 sys.path 已经处理完毕
    try:
        import uvicorn
        from app import app, logger
    except ImportError as e:
        print(f"核心模块导入失败: {e}")
        input("按回车键退出...")
        sys.exit(1)

    logger.info("正在以打包模式启动 ViralDramaBot...")
    
    # 在 Windows 打包环境下，必须调用此函数以防多进程（如 uvicorn 运行）导致无限循环启动
    multiprocessing.freeze_support()

    def open_browser():
        time.sleep(1.5)
        print("正在打开浏览器...", flush=True)
        try:
            # Windows 上最直接的方式
            os.startfile("http://127.0.0.1:8000")
        except Exception:
            # 备用方案：调用 cmd start
            import subprocess
            subprocess.run(["cmd", "/c", "start", "http://127.0.0.1:8000"], shell=True)

    threading.Thread(target=open_browser, daemon=True).start()

    # 启动服务
    # 注意：在打包版本中，通常直接传入 app 对象而不是字符串 "app:app"
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000, 
        log_level="info",
        log_config=None
    )

if __name__ == "__main__":
    main()