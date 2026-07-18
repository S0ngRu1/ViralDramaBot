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

    def _persist_weixin_cookies(
        self,
        account_id: int,
        cookie_path: Path,
        cookies: list[dict],
        core=None,
    ) -> None:
        """把已采集到的 Cookie 落盘并标记账号 active。"""
        log = logging.getLogger(APP_NAME)
        if not cookies:
            log.warning(
                "原生视频号 Cookie 为空，跳过落盘: account=%s path=%s",
                account_id, cookie_path,
            )
            return
        names = {str(c.get("name") or "") for c in cookies}
        # HAR/前端逻辑均以 sessionid 作为登录门禁；缺它则不算有效登录态
        if "sessionid" not in names:
            log.warning(
                "原生视频号 Cookie 缺少 sessionid，跳过落盘: account=%s names=%s",
                account_id, sorted(names),
            )
            return
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_path.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        from app import weixin_dao, weixin_account_mgr
        from src.publishing.weixin.schemas import AccountStatus

        weixin_dao.update_account_status(account_id, AccountStatus.ACTIVE)
        # 取消排队中的 Cookie 重试，避免成功后又被空结果覆盖
        self._weixin_cookie_sync_token = int(getattr(self, "_weixin_cookie_sync_token", 0)) + 1
        log.info(
            "原生视频号 Cookie 已保存: account=%s count=%s has_wxuin=%s path=%s",
            account_id, len(cookies), "wxuin" in names, cookie_path,
        )
        # 资料提取含 HTTP 重试 / 无头浏览器，绝对不能在 UI 线程跑，否则主窗口卡死。
        # WebView 页内 ExecuteScript 在部分环境下恒返回 null，已改为纯后台提取。
        self._start_background_profile_extract(account_id)

    def _start_background_profile_extract(self, account_id: int) -> None:
        """在后台线程提取昵称/头像，避免阻塞 pywebview / WinForms UI。"""
        log = logging.getLogger(APP_NAME)
        token = int(getattr(self, "_weixin_profile_extract_token", 0)) + 1
        self._weixin_profile_extract_token = token
        self._weixin_profile_extract_account_id = account_id

        def _worker() -> None:
            if token != getattr(self, "_weixin_profile_extract_token", 0):
                return
            if getattr(self, "_weixin_profile_extract_account_id", None) != account_id:
                return
            try:
                from app import weixin_account_mgr
                profile = weixin_account_mgr.extract_and_save_profile(
                    account_id, page=None
                )
                if profile.get("nickname") or profile.get("avatar_url"):
                    log.info(
                        "后台资料提取成功: account=%s nickname=%s",
                        account_id, profile.get("nickname"),
                    )
                else:
                    log.warning("后台资料提取未拿到昵称/头像: account=%s", account_id)
            except Exception:
                log.exception("后台资料提取失败: account=%s", account_id)

        threading.Thread(
            target=_worker,
            name=f"weixin-profile-{account_id}",
            daemon=True,
        ).start()

    @staticmethod
    def _cookie_items_from_webview(raw_cookies, *, log_prefix: str = "") -> list[dict]:
        """从 WebView2 Cookie 列表提取可落盘字段；兼容 qq.com / weixin.qq.com。"""
        log = logging.getLogger(APP_NAME)
        items: list[dict] = []
        seen: set[tuple[str, str]] = set()
        raw_list = list(raw_cookies or [])
        skipped_domains: list[str] = []
        for cookie in raw_list:
            try:
                name = str(getattr(cookie, "Name", "") or "")
                value = str(getattr(cookie, "Value", "") or "")
                domain = str(getattr(cookie, "Domain", "") or "")
            except Exception:
                continue
            if not name:
                continue
            domain_l = domain.lower()
            if not (
                "weixin.qq.com" in domain_l
                or domain_l.endswith(".qq.com")
                or domain_l == "qq.com"
                or "weixin" in domain_l
            ):
                if domain and domain not in skipped_domains and len(skipped_domains) < 8:
                    skipped_domains.append(domain)
                continue
            key = (name, domain)
            if key in seen:
                continue
            seen.add(key)
            items.append({"name": name, "value": value, "domain": domain or ".weixin.qq.com"})
        if log_prefix:
            sample = [
                f"{c.get('name')}@{c.get('domain')}" for c in items[:6]
            ]
            log.info(
                "%s raw=%s kept=%s sample=%s skipped_domains=%s",
                log_prefix, len(raw_list), len(items), sample, skipped_domains,
            )
        return items

    @staticmethod
    def _cookie_items_from_cdp_payload(payload_text: str) -> list[dict]:
        """解析 CDP Network.getAllCookies / getCookies 返回的 JSON。"""
        try:
            data = json.loads(payload_text or "{}")
        except json.JSONDecodeError:
            return []
        raw = data.get("cookies") or []
        items: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for cookie in raw:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "")
            value = str(cookie.get("value") or "")
            domain = str(cookie.get("domain") or "")
            if not name:
                continue
            domain_l = domain.lower()
            if not (
                "weixin.qq.com" in domain_l
                or domain_l.endswith(".qq.com")
                or domain_l == "qq.com"
                or "weixin" in domain_l
            ):
                continue
            key = (name, domain)
            if key in seen:
                continue
            seen.add(key)
            items.append({"name": name, "value": value, "domain": domain or ".weixin.qq.com"})
        return items

    def _weixin_cookie_uris(self, core) -> list[str]:
        """按优先级返回待查询 Cookie 的 URI 列表。"""
        uris: list[str] = []
        try:
            source = str(getattr(core, "Source", "") or "").strip()
        except Exception:
            source = ""
        for candidate in (
            source,
            "https://channels.weixin.qq.com/platform/home",
            "https://channels.weixin.qq.com/platform",
            "https://channels.weixin.qq.com/",
            "https://channels.weixin.qq.com",
            "",
        ):
            if candidate is None:
                continue
            text = str(candidate)
            if text not in uris:
                uris.append(text)
        return uris

    def _save_weixin_cookies(
        self, core, account_id: int, cookie_path: Path, attempt: int = 0
    ) -> None:
        """
        把原生 WebView2 登录态同步回 Cookie 文件。

        策略：
        1. 多 URI GetCookiesAsync 合并（空 URI / 当前页 / channels 路径）
        2. 仍为空则走 CDP Network.getAllCookies 兜底
        3. 失败则延迟重试（登录后 Cookie 可能尚未落盘）
        """
        from System import Action
        from System.Threading.Tasks import Task, TaskScheduler

        # Task.ContinueWith 默认在线程池调度，而不是 UI 线程；
        # CoreWebView2/CookieManager 只能在创建它的 UI 线程访问，
        # 必须显式绑定当前（UI 线程的）SynchronizationContext，
        # 否则第二个及之后的 URI 查询、CDP 兜底都会抛
        # “CoreWebView2 members can only be accessed from the UI thread”。
        ui_scheduler = TaskScheduler.FromCurrentSynchronizationContext()

        log = logging.getLogger(APP_NAME)
        max_attempts = 8
        if attempt >= max_attempts:
            log.error(
                "原生视频号 Cookie 同步重试耗尽: account=%s path=%s",
                account_id, cookie_path,
            )
            return

        uris = self._weixin_cookie_uris(core)
        state = {"uri_index": 0, "merged": []}

        def _finish_with_cookies(cookies: list[dict], source: str) -> None:
            names = {str(c.get("name") or "") for c in (cookies or [])}
            if cookies and "sessionid" in names:
                log.info(
                    "原生视频号 Cookie 采集成功: account=%s attempt=%s source=%s "
                    "count=%s has_wxuin=%s",
                    account_id, attempt, source, len(cookies), "wxuin" in names,
                )
                self._persist_weixin_cookies(
                    account_id, cookie_path, cookies, core=core
                )
                return
            log.warning(
                "原生视频号 Cookie 无效，准备重试: account=%s attempt=%s source=%s "
                "count=%s names=%s",
                account_id, attempt, source, len(cookies or []), sorted(names),
            )
            self._schedule_weixin_cookie_retry(core, account_id, cookie_path, attempt)

        def _try_cdp_fallback() -> None:
            try:
                cdp_task = core.CallDevToolsProtocolMethodAsync(
                    "Network.getAllCookies", "{}"
                )
            except Exception as exc:
                log.warning(
                    "CDP Network.getAllCookies 不可用: account=%s err=%s",
                    account_id, exc,
                )
                _finish_with_cookies(state["merged"], "cookie-manager")
                return

            def _cdp_done(task):
                try:
                    if getattr(task, "IsFaulted", False) or getattr(task, "IsCanceled", False):
                        log.warning(
                            "CDP 取 Cookie 失败: account=%s err=%s",
                            account_id, getattr(task, "Exception", None),
                        )
                        _finish_with_cookies(state["merged"], "cookie-manager")
                        return
                    cdp_cookies = self._cookie_items_from_cdp_payload(str(task.Result or ""))
                    merged = { (c["name"], c["domain"]): c for c in state["merged"] }
                    for item in cdp_cookies:
                        merged[(item["name"], item["domain"])] = item
                    _finish_with_cookies(list(merged.values()), "cdp")
                except Exception:
                    log.exception("解析 CDP Cookie 失败: account=%s", account_id)
                    _finish_with_cookies(state["merged"], "cookie-manager")

            cdp_handler = Action[Task](_cdp_done)
            self._weixin_handlers.append(cdp_handler)
            cdp_task.ContinueWith(cdp_handler, ui_scheduler)

        def _query_next_uri() -> None:
            if state["uri_index"] >= len(uris):
                if state["merged"]:
                    _finish_with_cookies(state["merged"], "cookie-manager")
                else:
                    _try_cdp_fallback()
                return

            uri = uris[state["uri_index"]]
            state["uri_index"] += 1

            def _uri_done(task):
                try:
                    if getattr(task, "IsFaulted", False):
                        log.warning(
                            "GetCookiesAsync 失败: account=%s uri=%r err=%s",
                            account_id, uri, getattr(task, "Exception", None),
                        )
                    elif getattr(task, "IsCanceled", False):
                        log.warning(
                            "GetCookiesAsync 已取消: account=%s uri=%r",
                            account_id, uri,
                        )
                    else:
                        got = self._cookie_items_from_webview(
                            task.Result,
                            log_prefix=f"cookie-uri account={account_id} uri={uri!r}",
                        )
                        merged = { (c["name"], c["domain"]): c for c in state["merged"] }
                        for item in got:
                            merged[(item["name"], item["domain"])] = item
                        state["merged"] = list(merged.values())
                except Exception:
                    log.exception(
                        "处理 GetCookiesAsync 结果失败: account=%s uri=%r",
                        account_id, uri,
                    )
                _query_next_uri()

            handler = Action[Task](_uri_done)
            self._weixin_handlers.append(handler)
            try:
                # 部分 WebView2/Python.NET 对空串不友好，优先用当前页与完整 URL
                task = core.CookieManager.GetCookiesAsync(uri if uri is not None else "")
            except Exception as exc:
                log.warning(
                    "GetCookiesAsync 抛错: account=%s uri=%r err=%s",
                    account_id, uri, exc,
                )
                _query_next_uri()
                return
            task.ContinueWith(handler, ui_scheduler)

        log.info(
            "开始同步原生视频号 Cookie: account=%s attempt=%s uris=%s path=%s",
            account_id, attempt, uris, cookie_path,
        )
        _query_next_uri()

    def _schedule_weixin_cookie_retry(
        self, core, account_id: int, cookie_path: Path, attempt: int,
        *, delay_ms: int = 1500,
    ) -> None:
        """延迟后在 UI 线程重试 Cookie 同步。"""
        log = logging.getLogger(APP_NAME)
        next_attempt = attempt + 1
        if next_attempt >= 8:
            log.error(
                "原生视频号 Cookie 同步重试耗尽: account=%s path=%s",
                account_id, cookie_path,
            )
            return
        if self._weixin_account_id != account_id or self._weixin_control is None:
            log.warning(
                "账号 WebView 已切换，取消 Cookie 重试: account=%s", account_id
            )
            return

        self._weixin_cookie_sync_token = int(getattr(self, "_weixin_cookie_sync_token", 0)) + 1
        token = self._weixin_cookie_sync_token

        def _retry():
            if token != getattr(self, "_weixin_cookie_sync_token", 0):
                return
            if self._weixin_account_id != account_id or self._weixin_control is None:
                return
            try:
                current_core = self._weixin_control.CoreWebView2
            except Exception:
                return
            if current_core is None:
                return
            self._save_weixin_cookies(current_core, account_id, cookie_path, next_attempt)

        def _start_timer():
            from System import EventHandler
            from System.Windows.Forms import Timer

            timer = Timer()
            timer.Interval = max(300, int(delay_ms))

            def _on_tick(sender, _args):
                try:
                    timer.Stop()
                    timer.Dispose()
                except Exception:
                    pass
                _retry()

            tick_handler = EventHandler(_on_tick)
            self._weixin_handlers.append(tick_handler)
            self._weixin_handlers.append(timer)
            timer.Tick += tick_handler
            timer.Start()

        try:
            self._invoke_form(_start_timer)
        except Exception:
            log.exception("调度 Cookie 重试失败: account=%s", account_id)
            threading.Timer(max(0.3, delay_ms / 1000.0), _retry).start()

    def showWeixinBrowser(self, payload):
        """在主窗口右侧区域叠加一个真正的 WebView2 浏览器控件。"""
        try:
            account_id = int(payload.get("account_id"))
            status = str(payload.get("status") or "expired")
            cookie_path = self._safe_cookie_path(str(payload.get("cookie_path") or ""))
            bounds = payload.get("bounds") or {}
            # 扫码登录期间标为 logging_in，启动刷新/Cookie 轮询会跳过，避免与落盘竞态误标过期
            if status != "active":
                try:
                    from app import weixin_dao
                    from src.publishing.weixin.schemas import AccountStatus
                    weixin_dao.update_account_status(account_id, AccountStatus.LOGGING_IN)
                except Exception:
                    logging.getLogger(APP_NAME).exception(
                        "更新视频号账号为扫码中失败: account=%s", account_id
                    )

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

                def _navigated(sender, args):
                    url = str(sender.Source or "")
                    is_success = bool(getattr(args, "IsSuccess", True))
                    logging.getLogger(APP_NAME).info(
                        "native weixin navigated: %s success=%s", url, is_success
                    )
                    if not is_success:
                        return
                    if "/platform" in url:
                        # NavigationCompleted 瞬间 CookieManager 常仍为空；延迟后再采
                        self._schedule_weixin_cookie_retry(
                            sender.CoreWebView2,
                            account_id,
                            cookie_path,
                            -1,
                            delay_ms=1200,
                        )
                    elif "login.html" in url and status == "active":
                        # 仅用 2 条精简 Cookie 注入后，常会短暂落到 login 再跳转；
                        # 这里不再立即标过期，避免「页面已登录 / 状态变过期」。
                        logging.getLogger(APP_NAME).warning(
                            "native weixin 回到登录页（暂不改状态）: account=%s",
                            account_id,
                        )

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
            account_id = self._weixin_account_id
            cookie_path = self._weixin_cookie_path

            def _hide():
                if self._weixin_control is not None:
                    self._weixin_control.Visible = False
            self._invoke_form(_hide)

            # 关闭扫码窗且尚未落盘时，把 logging_in 收回 expired，避免一直停在「扫码中」
            if account_id is not None:
                try:
                    from app import weixin_dao
                    from src.publishing.weixin.schemas import AccountStatus
                    account = weixin_dao.get_account(int(account_id))
                    if account and account.get("status") == AccountStatus.LOGGING_IN.value:
                        path_ok = bool(cookie_path) and Path(str(cookie_path)).exists()
                        if not path_ok:
                            weixin_dao.update_account_status(
                                int(account_id), AccountStatus.EXPIRED
                            )
                except Exception:
                    logging.getLogger(APP_NAME).exception(
                        "关闭视频号浏览器时回写账号状态失败"
                    )
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

    @staticmethod
    def _file_dialog_type(kind: str):
        """兼容新版 FileDialog 枚举与旧版 OPEN_DIALOG / FOLDER_DIALOG 常量。"""
        import webview

        file_dialog = getattr(webview, "FileDialog", None)
        if file_dialog is not None:
            if kind == "open" and hasattr(file_dialog, "OPEN"):
                return file_dialog.OPEN
            if kind == "folder" and hasattr(file_dialog, "FOLDER"):
                return file_dialog.FOLDER
        if kind == "open":
            return webview.OPEN_DIALOG
        return webview.FOLDER_DIALOG

    def browseFile(self):
        try:
            paths = self._window.create_file_dialog(
                self._file_dialog_type("open"),
                allow_multiple=False,
                file_types=VIDEO_FILE_TYPES,
            )
            if not paths:
                return {"status": "cancelled", "message": "未选择文件"}
            return {"status": "success", "path": paths[0]}
        except Exception as exc:
            return {"status": "error", "message": f"打开文件选择器失败: {exc}"}

    def browseFiles(self):
        try:
            paths = self._window.create_file_dialog(
                self._file_dialog_type("open"),
                allow_multiple=True,
                file_types=VIDEO_FILE_TYPES,
            )
            if not paths:
                return {"status": "cancelled", "message": "未选择文件"}
            return {"status": "success", "paths": list(paths)}
        except Exception as exc:
            return {"status": "error", "message": f"打开文件选择器失败: {exc}"}

    def browseDirectory(self):
        try:
            paths = self._window.create_file_dialog(self._file_dialog_type("folder"))
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

    handlers: list[logging.Handler] = [logging.FileHandler(log_file, encoding="utf-8")]
    if not is_frozen() and sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))

    class _UiLogBridgeHandler(logging.Handler):
        """把桌面端 WebView/登录日志同步进前端「运行日志」环形缓冲区。"""

        def emit(self, record: logging.LogRecord) -> None:
            try:
                from src.core.logger import push_log_entry
                push_log_entry(record.levelname, self.format(record))
            except Exception:
                pass

    ui_handler = _UiLogBridgeHandler()
    ui_handler.setLevel(logging.INFO)
    ui_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(ui_handler)

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
