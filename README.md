# ViralDramaBot 🎬

**一站式短剧自动化流水线：从资源采集、智能剪辑 到 多平台矩阵发布的全链路解决方案**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-green.svg)](#)

---

## ✨ 核心特性

### 🎯 采集层（已实现）
- ✅ **抖音视频下载** - 支持短链接解析，自动跟随重定向
- ✅ **无水印转换** - 自动获取无水印版本下载链接
- ✅ **元数据提取** - 自动提取视频标题、ID等信息
- ✅ **URL反转义** - 处理JSON编码的特殊字符
- ✅ **进度显示** - 实时下载进度反馈

### ✂️ 编辑层（规划中）
- 📋 自动化视频剪辑
- 🎵 音频处理和混音
- 📝 字幕自动生成和样式设置
- ✨ 特效和转场添加
- 🎨 自适应分辨率处理

### 📢 发布层（规划中）
- 📱 抖音发布
- 💬 微信视频号发布
- 🎬 B站发布
- 🚀 快手发布
- 📊 发布统计和管理

### 🔄 工作流（规划中）
- 🔗 任务编排和DAG定义
- ⏰ 自动调度和执行
- 🛡️ 错误处理和重试机制
- 📈 任务监控和日志

---

## 🚀 快速开始

### 前置条件
- Python 3.8 或更高版本
- pip 包管理工具

### 安装

```bash
# 克隆项目
git clone <repository_url>
cd ViralDramaBot

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 基础使用

```bash
# 查看帮助
python cli.py --help

# 下载抖音视频
python cli.py douyin download "https://v.douyin.com/xxxxx"

# 获取无水印下载链接（不下载）
python cli.py douyin get-link "https://v.douyin.com/xxxxx"

# 解析视频信息
python cli.py douyin parse "https://v.douyin.com/xxxxx"
```

### Python API 使用

```python
from src.core import initialize_app
from src.ingestion.douyin import get_downloader

# 初始化应用
initialize_app()

# 获取下载器
downloader = get_downloader()

# 下载视频
def on_progress(progress):
    percentage = progress['percentage']
    print(f"下载进度: {percentage:.1f}%")

result = downloader.download_video(
    share_link="https://v.douyin.com/xxxxx",
    on_progress=on_progress
)

if result['status'] == 'success':
    print(f"✅ 下载完成: {result['file_path']}")
else:
    print(f"❌ 下载失败: {result['message']}")
```

---

## 📁 项目结构

```
ViralDramaBot/
├── src/
│   ├── core/                    # 核心模块（配置、日志）
│   ├── ingestion/               # 资源采集层
│   │   └── douyin/              # 抖音采集模块 ✅
│   ├── editing/                 # 内容编辑层（规划中）
│   │   └── capcut/              # 剪映编辑模块
│   ├── publishing/              # 内容发布层（规划中）
│   ├── workflow/                # 工作流层（规划中）
│   └── utils/                   # 工具库
├── cli.py                       # 命令行入口
├── requirements.txt             # Python依赖
├── ARCHITECTURE.md              # 项目架构文档
└── README.md                    # 本文件
```

详细的架构说明请查看 [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 📖 文档

- **[项目架构文档](ARCHITECTURE.md)** - 详细的项目结构和设计说明
- **[抖音采集模块文档](src/ingestion/douyin/README.md)** - 抖音采集API使用说明
- **快速开始指南** - （待补充）
- **完整API文档** - （待补充）
- **开发贡献指南** - （待补充）

---

## 🛠️ 配置

### 环境变量

```bash
# 工作目录（默认: .data）
export WORK_DIR="/path/to/work/dir"

# 启用调试模式
export DEBUG=1

# 示例：下载视频到指定目录
WORK_DIR="/videos" python cli.py douyin download "https://v.douyin.com/xxxxx"
```

### 自定义配置

编辑 `src/core/config.py` 中的 `Config` 类：

```python
class Config:
    DEFAULT_WORK_DIR = '.data'      # 修改默认工作目录
    # ... 其他配置
```

---

## 🔍 抖音采集功能详解

### 支持的链接格式

- ✅ 短链接：`https://v.douyin.com/xxxxx/`
- ✅ 完整链接：`https://www.douyin.com/video/7374567890123456789`
- ✅ 文本包含链接：`分享链接: https://v.douyin.com/xxxxx`

### 工作流程

```
输入分享链接
    ↓
[URL提取] 正则表达式提取链接
    ↓
[重定向跟随] 自动处理301/302重定向
    ↓
[视频ID提取] 从URL中解析视频ID
    ↓
[页面获取] 请求视频页面HTML
    ↓
[信息提取] 从HTML正则提取下载链接和标题
    ↓
[URL反转义] 处理JSON编码的特殊字符
    ↓
[无水印转换] playwm→play替换为无水印版本
    ↓
[流式下载] 分块下载，显示进度
    ↓
完成 ✅
```

### 返回结果格式

```python
{
    "status": "success",          # 状态
    "message": "✅ 视频下载完成",   # 消息
    "video_id": "7374567890123",  # 视频ID
    "title": "视频标题",           # 视频标题
    "file_path": ".data/xxx.mp4"  # 保存路径
}
```

---

## 🐛 故障排查

### 问题1：无法下载，提示"Invalid URL"

**原因**：HTML中提取的URL被JSON编码，包含转义字符如`\u002F`

**解决**：系统已内置JSON反转义机制，自动处理此问题

### 问题2：权限错误 "Permission denied"

**原因**：工作目录没有写入权限

**解决**：
```bash
# 修改权限
chmod 755 .data

# 或更改工作目录
mkdir -p ~/videos
export WORK_DIR="~/videos"
python cli.py douyin download "..."
```

### 问题3：下载超时或连接失败

**原因**：网络问题或抖音服务器响应缓慢

**解决**：
```python
from src.ingestion.douyin import DouyinProcessor

# 增加超时时间和重试次数
processor = DouyinProcessor(timeout=20, max_retries=5)
```

### 更多问题

查看详细的故障排查指南：[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)

---

## 🧪 测试

```bash
# 测试抖音视频下载
python cli.py douyin download "https://v.douyin.com/e72G5usieXI/"

# 验证下载的文件
ls -lh .data/*.mp4
```

---

## 🗺️ 开发路线

### Phase 1: 核心架构与采集（✅ 已完成）
- [x] 项目结构重构
- [x] 模块化设计
- [x] 抖音采集功能完善
- [x] 文档完善

### Phase 2: 编辑功能（📋 规划中）
- [ ] 集成剪映API
- [ ] 实现视频剪辑
- [ ] 字幕自动生成
- [ ] 特效添加

### Phase 3: 多平台发布（📋 规划中）
- [ ] 抖音发布API
- [ ] 微信视频号发布
- [ ] B站发布
- [ ] 快手发布

### Phase 4: 工作流与自动化（📋 规划中）
- [ ] DAG任务编排
- [ ] 自动调度
- [ ] 错误恢复
- [ ] 监控告警

### Phase 5: Web UI & 服务（🔮 未来）
- [ ] Web仪表板
- [ ] REST API服务
- [ ] 队列系统
- [ ] 数据库集成

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

```bash
# Fork 项目
# 创建特性分支
git checkout -b feature/your-feature

# 提交更改
git commit -am 'Add your feature'

# 推送到分支
git push origin feature/your-feature

# 提交 Pull Request
```

---

## 📄 许可证

本项目采用 **MIT License** - 详见 [LICENSE](LICENSE) 文件
