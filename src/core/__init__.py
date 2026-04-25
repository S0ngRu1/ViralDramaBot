"""
核心模块 - 提供配置、日志等基础设施

模块结构：
- config.py: 配置管理
- logger.py: 日志系统
"""

from .config import Config, config, initialize_app
from .logger import Logger, logger, LogLevel

__all__ = [
    'Config',
    'config',
    'initialize_app',
    'Logger',
    'logger',
    'LogLevel',
]
