"""
视频号平台已发视频条目（内存模型）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ChannelPost:
    """创作者中心已发布的一条视频"""

    post_id: str
    title: str
    published_at: datetime
    view_count: int


@dataclass
class TrafficCandidate:
    """流量筛选候选条目"""

    post_id: str
    title: str
    published_at: Optional[datetime] = None
    view_count: Optional[int] = None
    reasons: List[str] = field(default_factory=list)
