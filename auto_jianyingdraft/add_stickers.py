#!/usr/bin/env python3
"""
Stickers and Emoji Management Module for CapCut API

提供贴纸、表情符号和装饰元素的管理功能
"""

import os
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import requests
from PIL import Image
import numpy as np
from auto_jianyingdraft.pyJianYingDraft import Draft, Sticker, ImageMaterial
from pyJianYingDraft.utils import generate_uuid, format_duration
import logging

logger = logging.getLogger(__name__)

# 贴纸类型定义
STICKER_TYPES = {
    "emoji": ["smile", "heart", "thumbs_up", "fire", "star", "laugh", "cry", "angry"],
    "decoration": ["border", "frame", "overlay", "light_leak", "bokeh", "glitter"],
    "text_bubble": ["speech", "thought", "shout", "whisper"],
    "animated": ["gif", "lottie", "animated_emoji"],
    "custom": ["upload", "url", "local"]
}

# 贴纸库
STICKER_LIBRARY = {
    "emoji": {
        "smile": {"name": "微笑", "file": "smile.png", "category": "emoji"},
        "heart": {"name": "爱心", "file": "heart.png", "category": "emoji"},
        "thumbs_up": {"name": "点赞", "file": "thumbs_up.png", "category": "emoji"},
        "fire": {"name": "火焰", "file": "fire.png", "category": "emoji"},
        "star": {"name": "星星", "file": "star.png", "category": "emoji"}
    },
    "decoration": {
        "border": {"name": "边框", "file": "border.png", "category": "decoration"},
        "frame": {"name": "相框", "file": "frame.png", "category": "decoration"},
        "overlay": {"name": "叠加层", "file": "overlay.png", "category": "decoration"}
    },
    "text_bubble": {
        "speech": {"name": "对话气泡", "file": "speech_bubble.png", "category": "text_bubble"},
        "thought": {"name": "思考气泡", "file": "thought_bubble.png", "category": "text_bubble"}
    }
}

class StickerManager:
    """贴纸管理器类"""
    
    def __init__(self, draft_folder: str):
        self.draft_folder = draft_folder
        self.stickers_path = os.path.join(draft_folder, "stickers")
        os.makedirs(self.stickers_path, exist_ok=True)
        
    def add_sticker(
        self,
        sticker_type: str,
        position: Tuple[float, float] = (0.5, 0.5),
        size: float = 1.0,
        rotation: float = 0.0,
        opacity: float = 1.0,
        start: float = 0,
        duration: Optional[float] = None,
        animation: Optional[str] = None,
        color: Optional[str] = None,
        text: Optional[str] = None,
        font_size: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        添加贴纸
        
        Args:
            sticker_type: 贴纸类型
            position: 位置 (x, y) 0-1 相对位置
            size: 大小倍数
            rotation: 旋转角度
            opacity: 透明度 0-1
            start: 开始时间（秒）
            duration: 持续时间（秒）
            animation: 动画类型
            color: 颜色
            text: 文字内容
            font_size: 字体大小
            **kwargs: 其他参数
            
        Returns:
            操作结果字典
        """
        try:
            if not os.path.exists(self.draft_folder):
                return {"success": False, "error": f"Draft folder does not exist: {self.draft_folder}"}
                
            # 加载草稿
            draft_file = os.path.join(self.draft_folder, "draft.json")
            if os.path.exists(draft_file):
                with open(draft_file, 'r', encoding='utf-8') as f:
                    draft_data = json.load(f)
            else:
                draft_data = {
                    "canvas_config": {
                        "width": 1080,
                        "height": 1920,
                        "fps": 30
                    },
                    "materials": {
                        "videos": [],
                        "audios": [],
                        "images": [],
                        "texts": [],
                        "stickers": []
                    },
                    "tracks": {
                        "video": [],
                        "audio": [],
                        "text": [],
                        "effect": [],
                        "sticker": []
                    }
                }
            
            # 生成唯一ID
            sticker_id = generate_uuid()
            material_id = generate_uuid()
            
            # 创建贴纸配置
            sticker_config = {
                "id": sticker_id,
                "type": sticker_type,
                "material_id": material_id,
                "position": {
                    "x": position[0],
                    "y": position[1]
                },
                "size": size,
                "rotation": rotation,
                "opacity": opacity,
                "start": start,
                "duration": duration or 10,
                "animation": animation or "none",
                "color": color,
                "text": text,
                "font_size": font_size or 24,
                "parameters": kwargs
            }
            
            # 创建贴纸素材
            sticker_material = {
                "id": material_id,
                "type": "sticker",
                "name": sticker_type,
                "category": self._get_category(sticker_type),
                "file_path": self._get_sticker_path(sticker_type),
                "width": 100,
                "height": 100,
                "parameters": {}
            }
            
            # 添加素材到草稿
            draft_data["materials"]["stickers"].append(sticker_material)
            
            # 查找或创建贴纸轨道
            sticker_track = None
            for track in draft_data["tracks"]["sticker"]:
                if track["name"] == "stickers":
                    sticker_track = track
                    break
                    
            if not sticker_track:
                sticker_track = {
                    "id": generate_uuid(),
                    "name": "stickers",
                    "type": "sticker",
                    "segments": []
                }
                draft_data["tracks"]["sticker"].append(sticker_track)
            
            # 添加贴纸到轨道
            sticker_track["segments"].append(sticker_config)
            
            # 保存草稿
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Added sticker: {sticker_type} to draft: {self.draft_folder}")
            
            return {
                "success": True,
                "sticker_id": sticker_id,
                "material_id": material_id,
                "sticker_type": sticker_type,
                "position": position,
                "size": size
            }
            
        except Exception as e:
            logger.error(f"Error adding sticker: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _get_category(self, sticker_type: str) -> str:
        """获取贴纸类别"""
        for category, stickers in STICKER_LIBRARY.items():
            if sticker_type in stickers:
                return category
        return "custom"
    
    def _get_sticker_path(self, sticker_type: str) -> str:
        """获取贴纸文件路径"""
        for category, stickers in STICKER_LIBRARY.items():
            if sticker_type in stickers:
                sticker_info = stickers[sticker_type]
                return os.path.join("stickers", sticker_info["file"])
        
        # 如果是自定义贴纸，返回占位符
        return os.path.join("stickers", f"{sticker_type}.png")
    
    def add_emoji(self, emoji: str, **kwargs) -> Dict[str, Any]:
        """
        添加表情符号
        
        Args:
            emoji: 表情符号
            **kwargs: 其他贴纸参数
            
        Returns:
            操作结果字典
        """
        return self.add_sticker(
            sticker_type="emoji",
            text=emoji,
            **kwargs
        )
    
    def add_text_bubble(
        self,
        text: str,
        bubble_type: str = "speech",
        position: Tuple[float, float] = (0.5, 0.8),
        font_size: int = 24,
        **kwargs
    ) -> Dict[str, Any]:
        """
        添加文字气泡
        
        Args:
            text: 文字内容
            bubble_type: 气泡类型
            position: 位置
            font_size: 字体大小
            **kwargs: 其他贴纸参数
            
        Returns:
            操作结果字典
        """
        return self.add_sticker(
            sticker_type=bubble_type,
            text=text,
            position=position,
            font_size=font_size,
            **kwargs
        )
    
    def add_custom_sticker(
        self,
        file_path: str,
        sticker_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        添加自定义贴纸
        
        Args:
            file_path: 贴纸文件路径
            sticker_name: 贴纸名称
            **kwargs: 其他贴纸参数
            
        Returns:
            操作结果字典
        """
        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": f"Sticker file not found: {file_path}"}
                
            # 复制文件到贴纸目录
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.stickers_path, filename)
            
            if not os.path.exists(dest_path):
                import shutil
                shutil.copy2(file_path, dest_path)
            
            # 创建自定义贴纸
            return self.add_sticker(
                sticker_type=sticker_name,
                **kwargs
            )
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def add_animated_sticker(
        self,
        sticker_type: str,
        animation_type: str = "bounce",
        **kwargs
    ) -> Dict[str, Any]:
        """
        添加动画贴纸
        
        Args:
            sticker_type: 贴纸类型
            animation_type: 动画类型
            **kwargs: 其他贴纸参数
            
        Returns:
            操作结果字典
        """
        animations = {
            "bounce": {"type": "bounce", "duration": 1.0},
            "fade": {"type": "fade", "duration": 2.0},
            "scale": {"type": "scale", "duration": 1.5},
            "rotate": {"type": "rotate", "duration": 3.0}
        }
        
        return self.add_sticker(
            sticker_type=sticker_type,
            animation=animation_type,
            **kwargs
        )
    
    def move_sticker(
        self,
        sticker_id: str,
        new_position: Tuple[float, float]
    ) -> Dict[str, Any]:
        """
        移动贴纸位置
        
        Args:
            sticker_id: 贴纸ID
            new_position: 新位置 (x, y)
            
        Returns:
            操作结果字典
        """
        try:
            draft_file = os.path.join(self.draft_folder, "draft.json")
            if not os.path.exists(draft_file):
                return {"success": False, "error": "Draft file not found"}
                
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)
            
            # 查找并更新贴纸位置
            updated = False
            for track in draft_data["tracks"]["sticker"]:
                for segment in track["segments"]:
                    if segment["id"] == sticker_id:
                        segment["position"]["x"] = new_position[0]
                        segment["position"]["y"] = new_position[1]
                        updated = True
                        break
                if updated:
                    break
            
            if not updated:
                return {"success": False, "error": "Sticker not found"}
            
            # 保存草稿
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "message": f"Moved sticker {sticker_id} to {new_position}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def resize_sticker(
        self,
        sticker_id: str,
        new_size: float
    ) -> Dict[str, Any]:
        """
        调整贴纸大小
        
        Args:
            sticker_id: 贴纸ID
            new_size: 新大小倍数
            
        Returns:
            操作结果字典
        """
        try:
            draft_file = os.path.join(self.draft_folder, "draft.json")
            if not os.path.exists(draft_file):
                return {"success": False, "error": "Draft file not found"}
                
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)
            
            # 查找并更新贴纸大小
            updated = False
            for track in draft_data["tracks"]["sticker"]:
                for segment in track["segments"]:
                    if segment["id"] == sticker_id:
                        segment["size"] = new_size
                        updated = True
                        break
                if updated:
                    break
            
            if not updated:
                return {"success": False, "error": "Sticker not found"}
            
            # 保存草稿
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "message": f"Resized sticker {sticker_id} to {new_size}x"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_sticker(self, sticker_id: str) -> Dict[str, Any]:
        """
        移除贴纸
        
        Args:
            sticker_id: 贴纸ID
            
        Returns:
            操作结果字典
        """
        try:
            draft_file = os.path.join(self.draft_folder, "draft.json")
            if not os.path.exists(draft_file):
                return {"success": False, "error": "Draft file not found"}
                
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)
            
            # 移除对应的贴纸
            draft_data["materials"]["stickers"] = [
                sticker for sticker in draft_data["materials"]["stickers"]
                if sticker["id"] != sticker_id
            ]
            
            # 移除对应的贴纸片段
            for track in draft_data["tracks"]["sticker"]:
                track["segments"] = [
                    segment for segment in track["segments"]
                    if segment["id"] != sticker_id
                ]
            
            # 保存草稿
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "message": f"Removed sticker: {sticker_id}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_stickers(self) -> Dict[str, Any]:
        """
        列出所有贴纸
        
        Returns:
            贴纸列表
        """
        try:
            draft_file = os.path.join(self.draft_folder, "draft.json")
            if not os.path.exists(draft_file):
                return {"success": False, "error": "Draft file not found"}
                
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)
            
            stickers = []
            for track in draft_data["tracks"]["sticker"]:
                for segment in track["segments"]:
                    stickers.append({
                        "id": segment["id"],
                        "type": segment["type"],
                        "position": segment["position"],
                        "size": segment["size"],
                        "duration": segment["duration"]
                    })
            
            return {"success": True, "stickers": stickers}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

def add_sticker_to_draft(
    draft_folder: str,
    sticker_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    向草稿添加贴纸的快捷函数
    
    Args:
        draft_folder: 草稿文件夹路径
        sticker_type: 贴纸类型
        **kwargs: 贴纸参数
        
    Returns:
        操作结果字典
    """
    manager = StickerManager(draft_folder)
    return manager.add_sticker(sticker_type, **kwargs)

def add_emoji_to_draft(
    draft_folder: str,
    emoji: str,
    **kwargs
) -> Dict[str, Any]:
    """
    向草稿添加表情符号的快捷函数
    
    Args:
        draft_folder: 草稿文件夹路径
        emoji: 表情符号
        **kwargs: 贴纸参数
        
    Returns:
        操作结果字典
    """
    manager = StickerManager(draft_folder)
    return manager.add_emoji(emoji, **kwargs)

def add_text_bubble_to_draft(
    draft_folder: str,
    text: str,
    **kwargs
) -> Dict[str, Any]:
    """
    向草稿添加文字气泡的快捷函数
    
    Args:
        draft_folder: 草稿文件夹路径
        text: 文字内容
        **kwargs: 气泡参数
        
    Returns:
        操作结果字典
    """
    manager = StickerManager(draft_folder)
    return manager.add_text_bubble(text, **kwargs)

if __name__ == "__main__":
    # 测试功能
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试草稿
        draft_id = "test_draft"
        draft_folder = os.path.join(temp_dir, draft_id)
        os.makedirs(draft_folder, exist_ok=True)
        
        # 测试添加贴纸
        manager = StickerManager(draft_folder)
        
        # 添加表情符号
        result = manager.add_emoji("😊", position=(0.2, 0.2), size=2.0)
        print("Emoji result:", result)
        
        # 添加文字气泡
        result = manager.add_text_bubble(
            "Hello World!",
            position=(0.5, 0.8),
            font_size=32
        )
        print("Text bubble result:", result)
        
        # 列出所有贴纸
        result = manager.list_stickers()
        print("Stickers:", result)