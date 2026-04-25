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
from logger import logger


class Config:
    """配置类"""
    
    # 默认工作目录
    DEFAULT_WORK_DIR = '.data'
    
    def __init__(self):
        """初始化配置"""
        # 从环境变量读取工作目录，如果未设置则使用默认值
        self.work_dir = os.getenv('WORK_DIR', self.DEFAULT_WORK_DIR)
        
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
    
    def get_video_path(self, video_id: str) -> Path:
        """
        获取视频文件路径
        
        Args:
            video_id: 视频ID
        
        Returns:
            Path: 视频文件的完整路径
        """
        return self.work_path / f"{video_id}.mp4"
    
    def get_temp_path(self, filename: str) -> Path:
        """
        获取临时文件路径
        
        Args:
            filename: 文件名
        
        Returns:
            Path: 临时文件的完整路径
        """
        return self.work_path / filename


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
