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
from typing import Optional


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
        # 必须用下划线前缀的“私有”属性保存 window。
        # pywebview 注入 JS API 时会递归遍历 js_api 的所有公开属性，
        # 若把 window 暴露为公开属性，会顺着 window.native（WinForms Form）
        # 无限递归遍历整个 .NET 对象树，触发 maximum recursion depth exceeded
        # 并刷爆日志、拖垮 UI 线程，导致界面卡死。
        self._window = None

    def bind(self, window) -> None:
        self._window = window

    def browseFile(self):
        import webview

        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=VIDEO_FILE_TYPES,
        )
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "path": paths[0]}

    def browseFiles(self):
        import webview

        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=VIDEO_FILE_TYPES,
        )
        if not paths:
            return {"status": "cancelled", "message": "未选择文件"}
        return {"status": "success", "paths": list(paths)}

    def browseDirectory(self):
        import webview

        paths = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not paths:
            return {"status": "cancelled", "message": "未选择目录"}
        return {"status": "success", "path": paths[0]}


class BackendStartup:
    """在独立线程中启动 FastAPI，避免阻塞 pywebview 界面线程。"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._server_thread: Optional[threading.Thread] = None
        self._app_url: Optional[str] = None
        self._error: Optional[str] = None
        self._status = "pending"

    @property
    def app_url(self) -> Optional[str]:
        with self._lock:
            return self._app_url

    def begin(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._done.clear()
            self._error = None
            self._app_url = None
            self._status = "starting"
        self._thread = threading.Thread(
            target=self._run, name="backend-startup", daemon=True
        )
        self._thread.start()

    def wait(self, timeout_seconds: float) -> bool:
        return self._done.wait(timeout=timeout_seconds)

    def result(self) -> tuple[Optional[str], Optional[str]]:
        with self._lock:
            return self._app_url, self._error

    def stop(self) -> None:
        srv = self._server
        thr = self._server_thread
        if srv is not None and thr is not None:
            stop_server(srv, thr, self._logger)

    def _run(self) -> None:
        try:
            self._logger.info("后台线程：开始加载 app 模块…")
            from app import app

            port = find_available_port()
            base_url = f"http://{HOST}:{port}"
            self._logger.info("后台线程：启动 uvicorn %s", base_url)
            server, server_thread = start_server(app, port, self._logger)
            with self._lock:
                self._server = server
                self._server_thread = server_thread

            wait_for_server(base_url)
            with self._lock:
                self._app_url = f"{base_url}/frontend/index.html"
                self._status = "ready"
            self._logger.info("后台线程：服务已就绪 %s", self._app_url)
        except Exception as exc:
            self._logger.exception("后台线程：启动失败")
            with self._lock:
                self._error = str(exc)
                self._status = "failed"
        finally:
            self._done.set()


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

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["WORK_DIR"] = str(data_dir)

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


def wait_for_server(url: str, timeout_seconds: float | None = None) -> None:
    if timeout_seconds is None:
        timeout_seconds = 120.0 if is_frozen() else 30.0
    import urllib.request

    health_paths = ("/api/health", "/api/status")
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        for path in health_paths:
            try:
                with urllib.request.urlopen(f"{url}{path}", timeout=2) as response:
                    if response.status < 500:
                        return
            except Exception as exc:
                last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"服务启动超时: {last_error}")


def start_server(app, port: int, logger: logging.Logger):
    import uvicorn

    def run_server() -> None:
        logger.info("正在启动 FastAPI 服务: http://%s:%s", HOST, port)
        uvicorn.run(
            app,
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )

    thread = threading.Thread(target=run_server, name="uvicorn-server", daemon=True)
    thread.start()
    return None, thread


def stop_server(server, thread: threading.Thread, logger: logging.Logger) -> None:
    logger.info("正在停止 FastAPI 服务（守护线程将随进程退出）")
    if thread.is_alive():
        thread.join(timeout=3)


def _show_error_dialog(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        pass


def _wait_for_backend(
    backend: BackendStartup, logger: logging.Logger
) -> tuple[Optional[str], Optional[str]]:
    """
    在创建 pywebview 窗口之前等待后端就绪。

    打包版曾用 tkinter 启动画面显示等待状态，但 Windows 崩溃日志显示上传阶段
    偶发 APPCRASH，故障模块为 tcl86t.dll。这里避免在桌面主进程加载 Tk/Tcl，
    只做后台等待，保留 pywebview 作为唯一 UI 运行时。
    """
    timeout = 120.0 if is_frozen() else 45.0
    backend.begin()
    logger.info("等待本地服务启动（最多 %.0f 秒）…", timeout)

    if not backend.wait(timeout):
        return None, f"服务启动超时（{timeout:.0f} 秒）"

    if not backend.wait(0):
        return None, f"服务启动超时（{timeout:.0f} 秒）"
    return backend.result()


def main() -> None:
    multiprocessing.freeze_support()
    setup_env()
    packaged_logger = setup_logging()

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    backend = BackendStartup(packaged_logger)
    app_url, error = _wait_for_backend(backend, packaged_logger)
    if error:
        packaged_logger.error("桌面应用启动失败: %s", error)
        _show_error_dialog(
            f"{error}\n\n日志：%APPDATA%\\ViralDramaBot\\logs\\app.log"
        )
        backend.stop()
        return
    if not app_url:
        msg = "未获取到主界面地址"
        packaged_logger.error(msg)
        _show_error_dialog(msg)
        backend.stop()
        return

    packaged_logger.info("服务已就绪，正在打开主窗口: %s", app_url)

    import webview

    desktop_api = DesktopApi()
    window = webview.create_window(
        APP_NAME,
        url=app_url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        resizable=True,
        text_select=True,
        js_api=desktop_api,
    )
    desktop_api.bind(window)
    window.events.closed += lambda: backend.stop()

    icon_path = get_bundle_dir() / "frontend" / "logo.ico"
    try:
        webview.start(
            debug=False,
            private_mode=False,
            storage_path=str(get_data_dir() / "webview"),
            icon=str(icon_path) if icon_path.exists() else None,
        )
    finally:
        backend.stop()


if __name__ == "__main__":
    main()
