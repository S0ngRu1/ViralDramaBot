"""
元数据获取模块

支持三种方式获取视频的标题、描述、标签：
1. 手动填写
2. 从文件名/目录名读取
3. AI 自动生成（可选）
"""

import re
from pathlib import Path
from typing import Optional

from src.core.logger import logger


class VideoMetadata:
    """视频元数据"""

    def __init__(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ):
        self.title = title
        self.description = description
        self.tags = tags or []


class MetadataResolver:
    """元数据解析器"""

    @staticmethod
    def from_manual(
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> VideoMetadata:
        """手动填写"""
        return VideoMetadata(title=title, description=description, tags=tags)

    @staticmethod
    def from_filename(video_path: str) -> VideoMetadata:
        """
        从文件名读取元数据

        支持的命名格式：
        - 标题.mp4 → 标题
        - 标题_描述.mp4 → 标题 + 描述
        - 标题_描述_标签1,标签2.mp4 → 标题 + 描述 + 标签
        - 标题#标签1#标签2.mp4 → 标题 + 标签
        """
        path = Path(video_path)
        name = path.stem  # 不含扩展名的文件名

        title = None
        description = None
        tags = []

        # 格式1: 标题_描述_标签1,标签2
        if "_" in name:
            parts = name.split("_", 2)
            title = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                description = parts[1].strip()
            if len(parts) > 2:
                tag_str = parts[2].strip()
                tags = [t.strip() for t in tag_str.split(",") if t.strip()]

        # 格式2: 标题#标签1#标签2
        elif "#" in name:
            parts = name.split("#")
            title = parts[0].strip()
            tags = [p.strip() for p in parts[1:] if p.strip()]

        # 格式3: 仅文件名作为标题
        else:
            title = name.strip()

        return VideoMetadata(title=title, description=description, tags=tags)

    @staticmethod
    def from_directory(video_path: str) -> VideoMetadata:
        """
        从所在目录名读取元数据

        目录名格式: 标题_描述_标签1,标签2
        """
        path = Path(video_path)
        dir_name = path.parent.name

        title = None
        description = None
        tags = []

        if "_" in dir_name:
            parts = dir_name.split("_", 2)
            title = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                description = parts[1].strip()
            if len(parts) > 2:
                tags = [t.strip() for t in parts[2].split(",") if t.strip()]
        else:
            title = dir_name.strip()

        return VideoMetadata(title=title, description=description, tags=tags)

    @staticmethod
    def from_ai(
        video_path: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ) -> VideoMetadata:
        """
        使用 AI 生成元数据

        需要配置 OPENAI_API_KEY 环境变量或传入 api_key
        """
        try:
            import openai

            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            file_name = Path(video_path).stem
            prompt = f"""请根据以下视频文件名，生成适合微信视频号发布的元数据。

文件名: {file_name}

请返回以下 JSON 格式（不要包含其他文字）：
{{
    "title": "标题（不超过50字，吸引人）",
    "description": "描述（100-300字，包含关键信息）",
    "tags": ["标签1", "标签2", "标签3"]
}}"""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            # 解析 JSON
            import json
            # 提取 JSON 部分
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return VideoMetadata(
                    title=data.get("title"),
                    description=data.get("description"),
                    tags=data.get("tags", []),
                )
            else:
                logger.warning("AI 返回格式异常，使用文件名作为标题")
                return MetadataResolver.from_filename(video_path)

        except ImportError:
            logger.warning("未安装 openai 库，无法使用 AI 生成元数据，回退到文件名解析")
            return MetadataResolver.from_filename(video_path)
        except Exception as e:
            logger.warning(f"AI 生成元数据失败: {e}，回退到文件名解析")
            return MetadataResolver.from_filename(video_path)

    @staticmethod
    def resolve(
        video_path: str,
        source: str = "manual",
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        ai_config: Optional[dict] = None,
    ) -> VideoMetadata:
        """
        统一解析入口

        Args:
            video_path: 视频文件路径
            source: 来源类型 (manual/filename/directory/ai)
            title: 手动标题
            description: 手动描述
            tags: 手动标签
            ai_config: AI 配置 (api_key, base_url, model)
        """
        if source == "manual":
            return MetadataResolver.from_manual(title, description, tags)
        elif source == "filename":
            meta = MetadataResolver.from_filename(video_path)
            # 手动值优先
            if title:
                meta.title = title
            if description:
                meta.description = description
            if tags:
                meta.tags = tags
            return meta
        elif source == "directory":
            meta = MetadataResolver.from_directory(video_path)
            if title:
                meta.title = title
            if description:
                meta.description = description
            if tags:
                meta.tags = tags
            return meta
        elif source == "ai":
            ai_config = ai_config or {}
            return MetadataResolver.from_ai(
                video_path,
                api_key=ai_config.get("api_key"),
                base_url=ai_config.get("base_url"),
                model=ai_config.get("model", "gpt-4o-mini"),
            )
        else:
            logger.warning(f"未知的元数据来源: {source}，使用手动模式")
            return MetadataResolver.from_manual(title, description, tags)
