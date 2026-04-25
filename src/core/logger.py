"""
日志系统模块

提供统一的日志输出功能，支持多个日志级别：
- INFO: 信息级别
- WARN: 警告级别
- ERROR: 错误级别
- DEBUG: 调试级别（仅在 DEBUG 环境变量设置时输出）
"""

import os
from datetime import datetime
from typing import Optional, Any
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Logger:
    """日志记录器类"""
    
    def __init__(self, debug_mode: bool = False):
        """
        初始化日志记录器
        
        Args:
            debug_mode: 是否启用调试模式
        """
        self.debug_mode = debug_mode or os.getenv('DEBUG') is not None
    
    @staticmethod
    def _format_message(level: LogLevel, message: str, context: Optional[Any] = None) -> str:
        """
        格式化日志消息
        
        Args:
            level: 日志级别
            message: 日志消息
            context: 上下文信息（可选）
        
        Returns:
            格式化后的日志消息
        """
        timestamp = datetime.now().isoformat()
        context_str = f" [{context}]" if context else ""
        return f"[{timestamp}] [{level.value}] {message}{context_str}"
    
    def info(self, message: str, context: Optional[Any] = None) -> None:
        """
        输出信息级别日志
        
        Args:
            message: 日志消息
            context: 上下文信息（可选）
        """
        formatted = self._format_message(LogLevel.INFO, message, context)
        print(formatted)
    
    def warn(self, message: str, context: Optional[Any] = None) -> None:
        """
        输出警告级别日志
        
        Args:
            message: 日志消息
            context: 上下文信息（可选）
        """
        formatted = self._format_message(LogLevel.WARN, message, context)
        print(formatted)
    
    def error(self, message: str, context: Optional[Any] = None) -> None:
        """
        输出错误级别日志
        
        Args:
            message: 日志消息
            context: 上下文信息（可选）
        """
        formatted = self._format_message(LogLevel.ERROR, message, context)
        print(formatted)
    
    def debug(self, message: str, context: Optional[Any] = None) -> None:
        """
        输出调试级别日志（仅在调试模式下输出）
        
        Args:
            message: 日志消息
            context: 上下文信息（可选）
        """
        if self.debug_mode:
            formatted = self._format_message(LogLevel.DEBUG, message, context)
            print(formatted)


# 全局日志实例
logger = Logger()
