"""
配置管理模块

管理项目的全局配置，包括：
- 工作目录设置
- 环境变量验证
- 文件路径管理
"""

import os
import sys
from pathlib import Path
from .logger import logger


class Config:
    """配置类"""

    # 默认工作目录
    DEFAULT_WORK_DIR = None
    DEFAULT_DOWNLOAD_TIMEOUT = 1200
    DEFAULT_MAX_RETRIES = 3

    # 视频号默认配置
    DEFAULT_WEIXIN_UPLOAD_TIMEOUT = 600
    DEFAULT_WEIXIN_INTER_UPLOAD_COOLDOWN = 20
    DEFAULT_WEIXIN_MAX_RETRIES = 3

    def __init__(self):
        """初始化配置"""
        # 从环境变量读取工作目录，如果未设置则使用默认值
        work_dir = os.getenv('WORK_DIR')
        if not work_dir:
            # 如果没有环境变量，在用户主目录下创建一个隐蔽目录作为最后退路
            work_dir = Path.home() / '.viraldramabot_data'
        self.work_dir = str(work_dir)
        self.download_timeout = int(
            os.getenv('DOWNLOAD_TIMEOUT', str(self.DEFAULT_DOWNLOAD_TIMEOUT))
        )
        self.max_retries = int(
            os.getenv('MAX_RETRIES', str(self.DEFAULT_MAX_RETRIES))
        )

        # 视频号配置
        self.weixin_upload_timeout = int(
            os.getenv('WEIXIN_UPLOAD_TIMEOUT', str(self.DEFAULT_WEIXIN_UPLOAD_TIMEOUT))
        )
        self.weixin_inter_upload_cooldown = int(
            os.getenv('WEIXIN_INTER_UPLOAD_COOLDOWN_SEC', str(self.DEFAULT_WEIXIN_INTER_UPLOAD_COOLDOWN))
        )
        self.weixin_max_retries = int(
            os.getenv('WEIXIN_MAX_RETRIES', str(self.DEFAULT_WEIXIN_MAX_RETRIES))
        )

        # 将工作目录转换为 Path 对象
        self.work_path = Path(self.work_dir)
    
    def validate_environment(self) -> bool:
        """
        验证环境配置
        
        Returns:
            bool: 验证是否成功
        """
        try:
            logger.info(f"📁 工作目录: {self.work_dir}")
            return True
        except Exception as e:
            logger.error(f"❌ 环境验证失败: {str(e)}")
            return False
    
    def initialize_work_dir(self) -> bool:
        """
        初始化工作目录
        
        创建工作目录（如果不存在），确保有写入权限
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            if not self.work_path.exists():
                self.work_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ 工作目录已创建: {self.work_dir}")
            else:
                logger.info(f"✅ 使用工作目录: {self.work_dir}")
            
            # 测试写入权限
            test_file = self.work_path / '.test_write'
            test_file.touch()
            test_file.unlink()
            
            return True
        except PermissionError:
            logger.error(f"❌ 无权限访问工作目录: {self.work_dir}")
            logger.error("请检查路径是否正确且有写入权限")
            return False
        except Exception as e:
            logger.error(f"❌ 无法创建或访问工作目录 {self.work_dir}: {str(e)}")
            return False
    
    def get_video_path(self, video_id: str, file_name: str | None = None) -> Path:
        """
        获取视频文件路径
        
        Args:
            video_id: 视频ID
            file_name: 自定义文件名（不含扩展名）
        
        Returns:
            Path: 视频文件的完整路径
        """
        base_name = file_name or video_id
        return self.work_path / f"{base_name}.mp4"
    
    def get_temp_path(self, filename: str) -> Path:
        """
        获取临时文件路径
        
        Args:
            filename: 文件名
        
        Returns:
            Path: 临时文件的完整路径
        """
        return self.work_path / filename

    def update(
        self,
        work_dir: str | None = None,
        download_timeout: int | None = None,
        max_retries: int | None = None,
        weixin_upload_timeout: int | None = None,
        weixin_inter_upload_cooldown: int | None = None,
        weixin_max_retries: int | None = None
    ) -> dict:
        """
        更新运行时配置

        Args:
            work_dir: 视频保存目录
            download_timeout: 下载超时时间（秒）
            max_retries: 最大重试次数
            weixin_upload_timeout: 视频号上传超时（秒）
            weixin_inter_upload_cooldown: 视频号连续上传间隔（秒）
            weixin_max_retries: 视频号最大重试次数

        Returns:
            dict: 更新后的配置快照
        """
        if work_dir is not None:
            self.work_dir = str(work_dir)
            self.work_path = Path(self.work_dir)

        if download_timeout is not None:
            self.download_timeout = int(download_timeout)

        if max_retries is not None:
            self.max_retries = int(max_retries)

        if weixin_upload_timeout is not None:
            self.weixin_upload_timeout = int(weixin_upload_timeout)

        if weixin_inter_upload_cooldown is not None:
            self.weixin_inter_upload_cooldown = int(weixin_inter_upload_cooldown)

        if weixin_max_retries is not None:
            self.weixin_max_retries = int(weixin_max_retries)

        if not self.initialize_work_dir():
            raise ValueError(f"无法访问工作目录: {self.work_dir}")

        return self.to_dict()

    def to_dict(self) -> dict:
        """返回当前配置快照"""
        return {
            "video_dir": str(self.work_dir),
            "download_timeout": int(self.download_timeout),
            "max_retries": int(self.max_retries),
            "weixin_upload_timeout": int(self.weixin_upload_timeout),
            "weixin_inter_upload_cooldown": int(self.weixin_inter_upload_cooldown),
            "weixin_max_retries": int(self.weixin_max_retries)
        }


# 全局配置实例
config = Config()


def initialize_app() -> bool:
    """
    初始化应用
    
    验证环境并初始化工作目录
    
    Returns:
        bool: 初始化是否成功
    """
    if not config.validate_environment():
        return False
    
    if not config.initialize_work_dir():
        sys.exit(1)
    
    return True
