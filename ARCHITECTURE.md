# ViralDramaBot 项目架构文档

## 📋 项目概述

**ViralDramaBot** 是一个"一站式短剧自动化流水线"解决方案，涵盖：
- 🎬 **资源采集**：从抖音、视频号等平台下载短剧
- ✂️ **智能剪辑**：基于剪映API的自动化编辑
- 📊 **内容生成**：字幕、封面、标签等自动生成
- 📢 **多平台发布**：一键发布到抖音、快手、视频号等

---

## 🏗️ 项目架构

```
ViralDramaBot/
├── src/                           # 源代码目录
│   ├── core/                      # 核心通用模块
│   │   ├── __init__.py
│   │   ├── config.py              # 全局配置管理
│   │   └── logger.py              # 统一日志系统
│   │
│   ├── ingestion/                 # 资源采集层
│   │   ├── __init__.py
│   │   └── douyin/                # 抖音采集模块（已实现）
│   │       ├── __init__.py
│   │       ├── processor.py       # 核心处理器
│   │       └── downloader.py      # 下载工具
│   │
│   ├── editing/                   # 内容编辑层
│   │   ├── __init__.py
│   │   └── capcut/                # 剪映自动化编辑（待实现）
│   │       └── __init__.py
│   │
│   ├── publishing/                # 内容发布层
│   │   ├── __init__.py            # 多平台发布（待实现）
│   │   ├── douyin/
│   │   ├── wechat_channels/
│   │   └── bilibili/
│   │
│   ├── workflow/                  # 工作流编排层
│   │   └── __init__.py            # DAG/任务编排（待实现）
│   │
│   ├── utils/                     # 通用工具库
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── cli.py                         # 命令行入口
├── README.md                      # 项目说明
├── ARCHITECTURE.md                # 本文件
├── requirements.txt               # Python依赖
├── setup.py                       # 安装配置
│
└── docs/                          # 文档目录
    ├── GETTING_STARTED.md         # 快速开始
    ├── API.md                     # API文档
    └── DEVELOPMENT.md             # 开发指南
```

---

## 📦 模块说明

### 1. **src/core** - 核心模块

**职责**：提供全局配置、日志、异常等基础设施

#### config.py
- 全局配置管理
- 工作目录初始化
- 文件路径管理

```python
from src.core import config, initialize_app

# 初始化应用
initialize_app()

# 获取工作目录
print(config.work_dir)  # '.data'
print(config.get_video_path('video_123'))  # '.data/video_123.mp4'
```

#### logger.py
- 统一日志输出
- 支持DEBUG模式
- 时间戳和级别标记

```python
from src.core import logger

logger.info("信息消息")
logger.warn("警告消息")
logger.error("错误消息")
logger.debug("调试消息")  # 需要环境变量DEBUG=1
```

---

### 2. **src/ingestion** - 资源采集层

**职责**：从各平台采集视频、音频等原始资源

#### douyin/ - 抖音采集模块（已实现）

**文件说明**：
- `processor.py`: 核心处理器
  - `DouyinProcessor`: 处理链接解析、重定向、HTML提取等底层操作
  - `DouyinVideoInfo`: 视频信息数据类
  - `DownloadProgress`: 下载进度数据类

- `downloader.py`: 高级下载工具
  - `DouyinDownloader`: 提供高级接口（get_download_link、download_video等）
  - `get_downloader()`: 全局单例获取函数

**使用示例**：

```python
from src.ingestion.douyin import get_downloader

# 获取下载器
downloader = get_downloader()

# 获取下载链接
result = downloader.get_download_link("https://v.douyin.com/xxxxx")
if result['status'] == 'success':
    print(f"链接: {result['download_url']}")

# 下载视频
def on_progress(progress):
    print(f"进度: {progress['percentage']:.1f}%")

result = downloader.download_video(
    "https://v.douyin.com/xxxxx",
    on_progress=on_progress
)
if result['status'] == 'success':
    print(f"文件: {result['file_path']}")

# 解析视频信息
result = downloader.parse_video_info("https://v.douyin.com/xxxxx")
```

---

### 3. **src/editing** - 内容编辑层

**职责**：实现自动化视频剪辑、编辑功能

#### capcut/ - 剪映编辑模块（待实现）

**规划功能**：
- 视频剪辑（截取、拼接）
- 音频处理（提取、调节、混音）
- 字幕添加（自动生成、样式设置）
- 特效添加（转场、滤镜、贴纸）
- 自适应分辨率处理

**预期接口**：

```python
from src.editing.capcut import CapCutEditor

editor = CapCutEditor()
editor.create_draft(title="视频标题")
editor.add_video_track(video_path)
editor.add_audio_track(audio_path)
editor.add_subtitle(subtitle_text)
editor.add_effects(effect_type="fade")
editor.export(output_path)
```

---

### 4. **src/publishing** - 内容发布层

**职责**：实现多平台内容分发

**规划平台**：
- 抖音 (Douyin)
- 微信视频号 (WeChat Channels)
- B站 (Bilibili)
- 快手 (Kuaishou)

**预期接口**：

```python
from src.publishing.douyin import DouyinPublisher
from src.publishing.wechat_channels import WeChatPublisher

# 发布到抖音
douyin_pub = DouyinPublisher(auth_token="xxx")
douyin_pub.publish(
    video_path="xxx.mp4",
    title="视频标题",
    tags=["短剧", "搞笑"]
)

# 发布到视频号
wechat_pub = WeChatPublisher(auth_token="xxx")
wechat_pub.publish(
    video_path="xxx.mp4",
    title="视频标题"
)
```

---

### 5. **src/workflow** - 工作流编排层

**职责**：编排采集、编辑、发布等任务流

**规划功能**：
- 任务DAG定义
- 自动化流程编排
- 错误恢复和重试
- 任务调度和监控

**预期接口**：

```python
from src.workflow import Pipeline

# 定义流水线
pipeline = Pipeline()
pipeline.add_task('download', download_task)
pipeline.add_task('edit', edit_task)
pipeline.add_task('publish', publish_task)

# 定义依赖关系
pipeline.add_dependency('download', 'edit')
pipeline.add_dependency('edit', 'publish')

# 执行流水线
result = pipeline.run(video_url="https://v.douyin.com/xxxxx")
```

---

### 6. **src/utils** - 工具库

**职责**：提供通用工具函数

**规划内容**：
- 文件操作工具
- 媒体格式转换
- 文本处理（字幕、标签等）
- 第三方API适配

---

## 🔄 数据流向

```
用户输入 URL
    ↓
[采集层] ingestion/douyin
    ├─ 解析链接和元数据
    ├─ 下载原始视频
    └─ 输出: video.mp4, metadata.json
    ↓
[编辑层] editing/capcut
    ├─ 自动剪辑
    ├─ 添加字幕/特效
    └─ 输出: edited_video.mp4
    ↓
[发布层] publishing/*
    ├─ 生成平台适配内容
    └─ 发布到各平台
    ↓
[工作流] workflow
    └─ 管理整个流程，处理错误和重试
```

---

## 📝 API 设计原则

### 1. **统一返回格式**
所有模块的主要函数都返回统一的结果字典：

```python
{
    "status": "success" | "error",
    "message": "操作消息",
    # ... 其他字段取决于具体功能
}
```

### 2. **解耦设计**
- 每个模块独立实现，不依赖其他模块
- 通过明确的接口进行交互
- 支持逐个模块的测试和扩展

### 3. **渐进式实现**
- 优先实现核心功能（采集层已完成）
- 保留插件接口（editing、publishing层预留）
- 支持第三方扩展

---

## 🛠️ 开发快速指南

### 环境设置

```bash
# 克隆项目
git clone <repo_url>
cd ViralDramaBot

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 运行示例

```bash
# 下载视频
python cli.py douyin download "https://v.douyin.com/xxxxx"

# 获取下载链接
python cli.py douyin get-link "https://v.douyin.com/xxxxx"

# 解析视频信息
python cli.py douyin parse "https://v.douyin.com/xxxxx"
```

### 添加新功能

1. **添加采集来源**：在 `src/ingestion/` 中创建新目录
2. **添加编辑功能**：在 `src/editing/capcut/` 中实现接口
3. **添加发布平台**：在 `src/publishing/` 中创建新目录

---

## 📊 项目里程碑

- [x] **Phase 1**：核心架构设计和抖音采集实现
- [ ] **Phase 2**：剪映编辑功能集成
- [ ] **Phase 3**：多平台发布能力
- [ ] **Phase 4**：工作流编排和自动化
- [ ] **Phase 5**：Web UI和API服务

---

## 🔗 相关文档

- [快速开始指南](docs/GETTING_STARTED.md)
- [完整 API 文档](docs/API.md)
- [开发贡献指南](docs/DEVELOPMENT.md)
- [抖音采集模块文档](src/ingestion/douyin/README.md)

---

## 📄 许可证

MIT License
