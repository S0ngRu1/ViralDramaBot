"""
ViralDramaBot - 短剧自动化流水线

模块结构：
- src/core/: 核心基础模块（配置、日志等）
- src/ingestion/: 资源采集模块
  - douyin/: 抖音视频采集
- src/editing/: 内容编辑模块
  - capcut/: 剪映自动化编辑
- src/publishing/: 多平台发布模块
- src/workflow/: 工作流编排模块
- src/utils/: 通用工具模块
"""

__version__ = "0.1.0"

from . import core
from . import ingestion
from . import editing
from . import publishing
from . import workflow
from . import utils

__all__ = [
    'core',
    'ingestion',
    'editing',
    'publishing',
    'workflow',
    'utils',
]
