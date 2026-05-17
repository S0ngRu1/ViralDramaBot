#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ViralDramaBot 打包桌面版入口。"""

import logging
import multiprocessing
import os
import socket
import sys
import threading
import time
from pathlib import Path


APP_NAME = "ViralDramaBot"
HOST = "127.0.0.1"
PREFERRED_PORT = 8000
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_MIN_SIZE = (1024, 700)
VIDEO_FILE_TYPES = (
    "Video files (*.mp4;*.avi;*.mov;*.mkv;*.flv;*.wmv)",
    "All files (*.*)",
)


class DesktopApi:
    def __init__(self) -> None:
        self.window = None

    def bind(self, window) -> None:
        self.window = window

    def browseFile(self):
        import webview

        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=VIDEO_FILE_TYPES,
        )
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "path": paths[0]}

    def browseFiles(self):
        import webview

        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=VIDEO_FILE_TYPES,
        )
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "paths": list(paths)}

    def browseDirectory(self):
        import webview

        paths = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not paths:
            return {"status": "cancelled", "message": "未选择目录"}
        return {"status": "success", "path": paths[0]}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_bundle_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", os.path.abspath(".")))
    return Path(__file__).resolve().parent


def get_app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    if is_frozen():
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
    return get_app_dir() / ".data"


def setup_env() -> Path:
    bundle_dir = get_bundle_dir()
    sys.path.insert(0, str(bundle_dir))

    if is_frozen():
        os.chdir(get_app_dir())

    return bundle_dir


def setup_logging() -> logging.Logger:
    data_dir = get_data_dir()
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if not is_frozen() and sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )
    return logging.getLogger(APP_NAME)


def find_available_port(preferred_port: int = PREFERRED_PORT) -> int:
    for port in [preferred_port, 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return int(sock.getsockname()[1])
    raise RuntimeError("没有可用的本地端口")


def wait_for_server(url: str, timeout_seconds: float = 20.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/status", timeout=1) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"服务启动超时: {last_error}")


def start_server(app, port: int, logger: logging.Logger):
    import uvicorn

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_level="info",
        log_config=None,
    )
    server = uvicorn.Server(config)

    def run_server() -> None:
        logger.info("正在启动 FastAPI 服务: http://%s:%s", HOST, port)
        server.run()

    thread = threading.Thread(target=run_server, name="uvicorn-server", daemon=True)
    thread.start()
    return server, thread


def stop_server(server, thread: threading.Thread, logger: logging.Logger) -> None:
    logger.info("正在停止 FastAPI 服务")
    server.should_exit = True
    thread.join(timeout=5)


def main() -> None:
    multiprocessing.freeze_support()
    setup_env()
    packaged_logger = setup_logging()

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    try:
        import webview
        from app import app
    except ImportError:
        packaged_logger.exception("桌面运行时依赖导入失败")
        raise

    port = find_available_port()
    base_url = f"http://{HOST}:{port}"
    server, server_thread = start_server(app, port, packaged_logger)

    try:
        wait_for_server(base_url)
        desktop_api = DesktopApi()
        window = webview.create_window(
            APP_NAME,
            f"{base_url}/frontend/index.html",
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=WINDOW_MIN_SIZE,
            resizable=True,
            text_select=True,
            js_api=desktop_api,
        )
        desktop_api.bind(window)

        window.events.closed += lambda: stop_server(server, server_thread, packaged_logger)
        icon_path = get_bundle_dir() / "frontend" / "logo.ico"
        webview.start(
            debug=not is_frozen(),
            private_mode=False,
            storage_path=str(get_data_dir() / "webview"),
            icon=str(icon_path) if icon_path.exists() else None,
        )
    except Exception:
        packaged_logger.exception("桌面应用启动失败")
        stop_server(server, server_thread, packaged_logger)
        raise
    finally:
        if server_thread.is_alive():
            stop_server(server, server_thread, packaged_logger)


if __name__ == "__main__":
    main()
