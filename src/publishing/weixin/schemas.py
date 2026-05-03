"""
Pydantic 数据模型
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class AccountStatus(str, Enum):
    """账号状态"""
    ACTIVE = "active"  # 登录有效
    EXPIRED = "expired"  # 登录过期
    LOGGING_IN = "logging_in"  # 正在登录（等待扫码）
    ERROR = "error"  # 异常


class TaskStatus(str, Enum):
    """上传任务状态"""
    PENDING = "pending"  # 等待中
    UPLOADING = "uploading"  # 上传中
    PROCESSING = "processing"  # 视频处理中
    FILLING = "filling"  # 填写信息中
    PUBLISHING = "publishing"  # 发布中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class MetadataSource(str, Enum):
    """元数据来源"""
    MANUAL = "manual"  # 手动填写
    FILENAME = "filename"  # 从文件名读取
    AI = "ai"  # AI 自动生成


class AccountCreate(BaseModel):
    """创建账号请求"""
    name: str = Field(..., min_length=1, max_length=50, description="账号名称")


class AccountInfo(BaseModel):
    """账号信息"""
    id: int
    name: str
    wechat_id: Optional[str] = None
    status: AccountStatus
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UploadTaskCreate(BaseModel):
    """创建上传任务请求"""
    account_id: int = Field(..., description="账号ID")
    video_path: str = Field(..., description="视频文件路径")
    title: Optional[str] = Field(None, max_length=50, description="标题")
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    tags: Optional[list[str]] = Field(None, description="标签列表")
    metadata_source: MetadataSource = Field(
        MetadataSource.MANUAL, description="元数据来源"
    )
    scheduled_at: Optional[datetime] = Field(None, description="定时发布时间")
    drama_link: Optional[str] = Field(None, description="视频号剧集名称")


class BatchUploadCreate(BaseModel):
    """批量创建上传任务请求"""
    account_id: int = Field(..., description="账号ID")
    video_paths: list[str] = Field(..., min_length=1, max_length=50, description="视频文件路径列表")
    titles: Optional[list[str]] = Field(None, description="标题列表")
    descriptions: Optional[list[str]] = Field(None, description="描述列表")
    tags: Optional[list[str]] = Field(None, description="统一标签")
    metadata_source: MetadataSource = Field(
        MetadataSource.MANUAL, description="元数据来源"
    )
    scheduled_at: Optional[datetime] = Field(None, description="定时发布时间（第一个视频的时间，后续依次递增）")
    drama_link: Optional[str] = Field(None, description="视频号剧集名称")


class TaskInfo(BaseModel):
    """任务信息"""
    id: int
    account_id: int
    video_path: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    status: TaskStatus
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_msg: Optional[str] = None


class ScheduleCreate(BaseModel):
    """创建定时计划请求"""
    account_id: int = Field(..., description="账号ID")
    video_paths: list[str] = Field(..., min_length=1, description="视频文件路径列表")
    cron_expr: Optional[str] = Field(None, description="Cron 表达式")
    interval_minutes: Optional[int] = Field(None, ge=1, description="间隔分钟数")
    titles: Optional[list[str]] = Field(None, description="标题列表")
    descriptions: Optional[list[str]] = Field(None, description="描述列表")
    tags: Optional[list[str]] = Field(None, description="标签列表")
    metadata_source: MetadataSource = Field(
        MetadataSource.MANUAL, description="元数据来源"
    )


class ScheduleInfo(BaseModel):
    """定时计划信息"""
    id: int
    account_id: int
    cron_expr: Optional[str] = None
    interval_minutes: Optional[int] = None
    is_active: bool
    created_at: datetime
    next_run_at: Optional[datetime] = None


class QRCodeResponse(BaseModel):
    """二维码登录响应"""
    account_id: int
    qrcode_base64: Optional[str] = None
    status: str
    message: str
