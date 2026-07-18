#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ViralDramaBot 打包桌面版入口。"""

import logging
import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional


APP_NAME = "ViralDramaBot 运营工作台"
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
        self._weixin_control = None
        self._weixin_account_id = None
        self._weixin_cookie_path = None
        self._weixin_handlers = []

    def bind(self, window) -> None:
        self._window = window

    @staticmethod
    def _safe_cookie_path(cookie_path: str) -> Path:
        root = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        allowed = (root / "ViralDramaBot" / "weixin" / "cookies").resolve()
        candidate = Path(cookie_path).resolve()
        if candidate.parent != allowed:
            raise ValueError("Cookie 路径不在应用数据目录内")
        return candidate

    def _invoke_form(self, callback) -> None:
        from System import Action

        form = self._window.native
        if form.InvokeRequired:
            form.Invoke(Action(callback))
        else:
            callback()

    def _set_weixin_bounds(self, bounds) -> None:
        if not self._weixin_control or not bounds:
            return
        form = self._window.native
        scale = float(getattr(form, "_scale", 1.0) or 1.0)
        left = max(0, int(float(bounds.get("left", 0)) * scale))
        top = max(0, int(float(bounds.get("top", 0)) * scale))
        width = max(320, int(float(bounds.get("width", 800)) * scale))
        height = max(280, int(float(bounds.get("height", 600)) * scale))
        self._weixin_control.SetBounds(left, top, width, height)
        logging.getLogger(APP_NAME).info(
            "native weixin bounds: css=%s scale=%.2f native=(%s,%s,%s,%s)",
            bounds, scale, left, top, width, height,
        )

    def _save_weixin_cookies(self, core, account_id: int, cookie_path: Path) -> None:
        """把原生 WebView2 登录态同步回现有账号 Cookie 文件。"""
        from System import Action
        from System.Collections.Generic import List
        from System.Threading.Tasks import Task
        from Microsoft.Web.WebView2.Core import CoreWebView2Cookie

        def _completed(task):
            try:
                cookies = [
                    {"name": str(cookie.Name), "value": str(cookie.Value), "domain": str(cookie.Domain)}
                    for cookie in task.Result
                    if "weixin.qq.com" in str(cookie.Domain)
                ]
                cookie_path.parent.mkdir(parents=True, exist_ok=True)
                cookie_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
                from app import weixin_dao
                from src.publishing.weixin.schemas import AccountStatus
                weixin_dao.update_account_status(account_id, AccountStatus.ACTIVE)
            except Exception:
                logging.getLogger(APP_NAME).exception("保存原生视频号浏览器 Cookie 失败")

        handler = Action[Task[List[CoreWebView2Cookie]]](_completed)
        self._weixin_handlers.append(handler)
        core.CookieManager.GetCookiesAsync("https://channels.weixin.qq.com").ContinueWith(handler)

    def showWeixinBrowser(self, payload):
        """在主窗口右侧区域叠加一个真正的 WebView2 浏览器控件。"""
        try:
            account_id = int(payload.get("account_id"))
            status = str(payload.get("status") or "expired")
            cookie_path = self._safe_cookie_path(str(payload.get("cookie_path") or ""))
            bounds = payload.get("bounds") or {}

            def _show():
                from Microsoft.Web.WebView2.WinForms import CoreWebView2CreationProperties, WebView2
                from System.Drawing import Color
                from System.Windows.Forms import DockStyle

                form = self._window.native
                if self._weixin_control is not None:
                    try:
                        form.Controls.Remove(self._weixin_control)
                        self._weixin_control.Dispose()
                    except Exception:
                        pass

                control = WebView2()
                props = CoreWebView2CreationProperties()
                profile_root = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
                profile_dir = profile_root / "ViralDramaBot" / "weixin" / "webview_profiles" / f"account_{account_id}"
                profile_dir.mkdir(parents=True, exist_ok=True)
                props.UserDataFolder = str(profile_dir)
                props.AdditionalBrowserArguments = "--disable-features=ElasticOverscroll"
                control.CreationProperties = props
                control.Dock = getattr(DockStyle, "None")
                control.BackColor = Color.White
                control.DefaultBackgroundColor = Color.White
                self._weixin_control = control
                self._weixin_account_id = account_id
                self._weixin_cookie_path = cookie_path
                self._set_weixin_bounds(bounds)
                form.Controls.Add(control)
                control.BringToFront()

                def _ready(sender, args):
                    if not args.IsSuccess:
                        logging.getLogger(APP_NAME).error("视频号 WebView2 初始化失败: %s", args.InitializationException)
                        return
                    core = sender.CoreWebView2
                    logging.getLogger(APP_NAME).info(
                        "native weixin WebView2 ready: account=%s status=%s", account_id, status
                    )
                    if status == "active" and cookie_path.exists():
                        try:
                            cookie_items = json.loads(cookie_path.read_text(encoding="utf-8"))
                            for item in cookie_items:
                                cookie = core.CookieManager.CreateCookie(
                                    str(item.get("name", "")), str(item.get("value", "")),
                                    str(item.get("domain", ".weixin.qq.com")), "/"
                                )
                                core.CookieManager.AddOrUpdateCookie(cookie)
                            logging.getLogger(APP_NAME).info(
                                "native weixin cookies loaded: %s", len(cookie_items)
                            )
                        except Exception:
                            logging.getLogger(APP_NAME).exception("载入视频号 Cookie 失败")
                        core.Navigate("https://channels.weixin.qq.com/platform")
                    else:
                        core.Navigate("https://channels.weixin.qq.com/login.html?from=assistant")

                def _navigated(sender, _args):
                    url = str(sender.Source or "")
                    logging.getLogger(APP_NAME).info("native weixin navigated: %s", url)
                    if "/platform" in url:
                        self._save_weixin_cookies(sender.CoreWebView2, account_id, cookie_path)
                    elif "login.html" in url and status == "active":
                        try:
                            from app import weixin_dao
                            from src.publishing.weixin.schemas import AccountStatus
                            weixin_dao.update_account_status(account_id, AccountStatus.EXPIRED)
                        except Exception:
                            logging.getLogger(APP_NAME).exception("更新视频号账号过期状态失败")

                self._weixin_handlers.extend([_ready, _navigated])
                control.CoreWebView2InitializationCompleted += _ready
                control.NavigationCompleted += _navigated
                control.EnsureCoreWebView2Async(None)
                logging.getLogger(APP_NAME).info("native weixin WebView2 control created: account=%s", account_id)

            self._invoke_form(_show)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def updateWeixinBrowserBounds(self, bounds):
        try:
            self._invoke_form(lambda: self._set_weixin_bounds(bounds or {}))
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def hideWeixinBrowser(self):
        try:
            def _hide():
                if self._weixin_control is not None:
                    self._weixin_control.Visible = False
            self._invoke_form(_hide)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def reloadWeixinBrowser(self):
        try:
            self._invoke_form(lambda: self._weixin_control.Reload() if self._weixin_control else None)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def backWeixinBrowser(self):
        try:
            def _back():
                if self._weixin_control and self._weixin_control.CanGoBack:
                    self._weixin_control.GoBack()
            self._invoke_form(_back)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def browseFile(self):
        import webview

        try:
            paths = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=VIDEO_FILE_TYPES,
            )
            if not paths:
                return {"status": "cancelled", "message": "未选择文件"}
            return {"status": "success", "path": paths[0]}
        except Exception as exc:
            return {"status": "error", "message": f"打开文件选择器失败: {exc}"}

    def browseFiles(self):
        import webview

        try:
            paths = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=VIDEO_FILE_TYPES,
            )
            if not paths:
                return {"status": "cancelled", "message": "未选择文件"}
            return {"status": "success", "paths": list(paths)}
        except Exception as exc:
            return {"status": "error", "message": f"打开文件选择器失败: {exc}"}

    def browseDirectory(self):
        import webview

        try:
            paths = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not paths:
                return {"status": "cancelled", "message": "未选择目录"}
            return {"status": "success", "path": paths[0]}
        except Exception as exc:
            return {"status": "error", "message": f"打开目录选择器失败: {exc}"}


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
            return Path(appdata) / "ViralDramaBot"
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
