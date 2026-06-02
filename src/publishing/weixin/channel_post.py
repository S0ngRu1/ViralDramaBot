"""
视频号平台已发视频条目（内存模型）
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChannelPost:
    """创作者中心已发布的一条视频"""

    post_id: str
    title: str
    published_at: datetime
    view_count: int
