"""
日志系统模块

支持多个日志级别，并维护一个进程内的环形缓冲区（最多 500 条），
可通过 get_log_entries() 读取供前端实时展示。
"""

import collections
import threading
from datetime import datetime
from typing import Optional, Any, List, Dict
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


# ── 全局日志缓冲区 ────────────────────────────────────────────────────────────
_log_buffer: collections.deque = collections.deque(maxlen=500)
_log_lock = threading.Lock()
_log_seq = [0]  # 单调递增序号，用列表以便在内层函数中修改


def get_log_entries(since_id: int = 0, limit: int = 100) -> List[Dict]:
    """返回 id > since_id 的最新 limit 条日志（线程安全）。"""
    with _log_lock:
        entries = [e for e in _log_buffer if e["id"] > since_id]
    return entries[-limit:]


def clear_log_entries() -> int:
    """清空进程内日志缓冲区，返回清空条数。"""
    with _log_lock:
        count = len(_log_buffer)
        _log_buffer.clear()
        _log_seq[0] += 1
    return count


class Logger:
    """日志记录器"""

    def __init__(self, debug_mode: bool = False):
        import os
        self.debug_mode = debug_mode or os.getenv('DEBUG') is not None

    @staticmethod
    def _format_message(level: LogLevel, message: str, context: Optional[Any] = None) -> str:
        timestamp = datetime.now().isoformat()
        context_str = f" [{context}]" if context else ""
        return f"[{timestamp}] [{level.value}] {message}{context_str}"

    def _emit(self, level: LogLevel, message: str, context: Optional[Any] = None) -> None:
        import logging as _logging
        context_str = f" [{context}]" if context else ""
        full_msg = message + context_str
        formatted = f"[{datetime.now().isoformat()}] [{level.value}] {full_msg}"
        print(formatted)
        # 同时写入标准 logging，确保打包版（stdout→devnull）也能在 app.log 里看到上传日志
        _std_level = {
            LogLevel.DEBUG: _logging.DEBUG,
            LogLevel.INFO:  _logging.INFO,
            LogLevel.WARN:  _logging.WARNING,
            LogLevel.ERROR: _logging.ERROR,
        }.get(level, _logging.INFO)
        _logging.getLogger("ViralDramaBot.app").log(_std_level, full_msg)
        # 写入环形缓冲区
        ts = datetime.now().strftime("%H:%M:%S")
        with _log_lock:
            _log_seq[0] += 1
            _log_buffer.append({
                "id": _log_seq[0],
                "level": level.value,
                "msg": full_msg,
                "ts": ts,
            })

    def info(self, message: str, *args, context: Optional[Any] = None) -> None:
        if args:
            try:
                message = message % args
            except Exception:
                pass
        self._emit(LogLevel.INFO, message, context)

    def warn(self, message: str, *args, context: Optional[Any] = None) -> None:
        if args:
            try:
                message = message % args
            except Exception:
                pass
        self._emit(LogLevel.WARN, message, context)

    warning = warn

    def error(self, message: str, *args, context: Optional[Any] = None) -> None:
        if args:
            try:
                message = message % args
            except Exception:
                pass
        self._emit(LogLevel.ERROR, message, context)

    def debug(self, message: str, *args, context: Optional[Any] = None) -> None:
        if not self.debug_mode:
            return
        if args:
            try:
                message = message % args
            except Exception:
                pass
        self._emit(LogLevel.DEBUG, message, context)


# 全局日志实例
logger = Logger()
