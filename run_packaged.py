#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ViralDramaBot 打包桌面版入口。"""

import logging
import math
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

class StartupSplash:
    """启动等待窗：纯紫色背景 + 简易卡通动画（Tk Canvas）。"""

    WIDTH = 520
    HEIGHT = 380
    BG = "#6366f1"

    def __init__(self, root, bundle_dir: Path) -> None:
        import tkinter as tk

        self._tk = tk
        self.root = root
        self.frame = 0
        self.canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.BG,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self._draw_decorative_clouds()

    def _draw_decorative_clouds(self) -> None:
        clouds = (
            (70, 55, "#ffffff"),
            (430, 70, "#ffffff"),
            (95, 300, "#ffffff"),
            (400, 285, "#ffffff"),
        )
        for x, y, color in clouds:
            self.canvas.create_oval(
                x - 36, y - 18, x + 36, y + 18, fill=color, outline="", tags="bg"
            )
            self.canvas.create_oval(
                x - 18, y - 26, x + 46, y + 10, fill=color, outline="", tags="bg"
            )
            self.canvas.create_oval(
                x - 46, y - 10, x + 10, y + 22, fill=color, outline="", tags="bg"
            )

    def animate(self) -> None:
        self.frame += 1
        self.canvas.delete("anim")

        cx = self.WIDTH // 2
        cy = self.HEIGHT // 2 - 12
        t = self.frame * 0.09

        bounce = int(7 * math.sin(t))
        self._draw_mascot(cx, cy + 58 + bounce)

        orbit_colors = (
            "#f9a8d4",
            "#93c5fd",
            "#fde68a",
            "#a7f3d0",
            "#c4b5fd",
            "#fda4af",
        )
        for i, color in enumerate(orbit_colors):
            angle = t + i * (2 * math.pi / len(orbit_colors))
            rx = 92
            ry = 52
            x = cx + int(rx * math.cos(angle))
            y = cy + int(ry * math.sin(angle))
            r = 6 + (i % 2)
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r, fill=color, outline="", tags="anim"
            )

        title_y = self.HEIGHT - 96
        self.canvas.create_text(
            cx,
            title_y,
            text="正在启动 ViralDramaBot",
            font=("Microsoft YaHei UI", 15, "bold"),
            fill="#ffffff",
            tags="anim",
        )

        dot_y = self.HEIGHT - 58
        for i in range(3):
            hop = -10 if ((self.frame // 7 + i) % 3) == 0 else 0
            dx = cx - 22 + i * 22
            self.canvas.create_oval(
                dx - 5,
                dot_y + hop - 5,
                dx + 5,
                dot_y + hop + 5,
                fill="#c7d2fe",
                outline="",
                tags="anim",
            )

        dots = "." * (1 + (self.frame // 12) % 3)
        self.canvas.create_text(
            cx,
            self.HEIGHT - 30,
            text=f"正在加载服务，请稍候{dots}",
            font=("Microsoft YaHei UI", 10),
            fill="#c7d2fe",
            tags="anim",
        )

    def _draw_mascot(self, cx: int, cy: int) -> None:
        self.canvas.create_oval(
            cx - 30,
            cy - 26,
            cx + 30,
            cy + 30,
            fill="#fff7ed",
            outline="#fdba74",
            width=2,
            tags="anim",
        )
        self.canvas.create_oval(
            cx - 24, cy + 2, cx - 14, cy + 11, fill="#fecdd3", outline="", tags="anim"
        )
        self.canvas.create_oval(
            cx + 14, cy + 2, cx + 24, cy + 11, fill="#fecdd3", outline="", tags="anim"
        )

        if (self.frame // 28) % 14 == 0:
            self.canvas.create_line(
                cx - 13, cy - 5, cx - 7, cy - 5, fill="#334155", width=2, tags="anim"
            )
            self.canvas.create_line(
                cx + 7, cy - 5, cx + 13, cy - 5, fill="#334155", width=2, tags="anim"
            )
        else:
            self.canvas.create_oval(
                cx - 15, cy - 11, cx - 7, cy - 3, fill="#334155", outline="", tags="anim"
            )
            self.canvas.create_oval(
                cx + 7, cy - 11, cx + 15, cy - 3, fill="#334155", outline="", tags="anim"
            )

        self.canvas.create_arc(
            cx - 11,
            cy - 1,
            cx + 11,
            cy + 13,
            start=200,
            extent=140,
            style="arc",
            outline="#334155",
            width=2,
            tags="anim",
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

    WebView2 要求 load_url 等在 UI 线程执行；若在 webview.start(func) 回调里跳转，
    会触发 “CoreWebView2Controller members can only be accessed from the UI thread”。
    """
    timeout = 120.0 if is_frozen() else 45.0
    backend.begin()
    logger.info("等待本地服务启动（最多 %.0f 秒）…", timeout)

    try:
        import tkinter as tk

        root = tk.Tk()
        root.title(APP_NAME)
        root.resizable(False, False)
        splash = StartupSplash(root, get_bundle_dir())
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = max(0, (screen_w - splash.WIDTH) // 2)
        y = max(0, (screen_h - splash.HEIGHT) // 2)
        root.geometry(f"{splash.WIDTH}x{splash.HEIGHT}+{x}+{y}")

        deadline = time.monotonic() + timeout

        def poll() -> None:
            if backend.wait(0) or time.monotonic() >= deadline:
                root.quit()
                return
            splash.animate()
            root.after(50, poll)

        poll()
        root.mainloop()
        root.destroy()
    except Exception as exc:
        logger.warning("Tk 等待窗口不可用，改为后台等待: %s", exc)
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
