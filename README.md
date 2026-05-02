# ViralDramaBot

短剧素材下载与管理工具。当前已实现的是一套可直接使用的抖音下载 Web 应用，支持下载、进度查看、目录选择、视频管理和基础配置。

---

## 当前状态

已实现：

- 抖音短链接和长链接解析
- 无水印下载
- 下载进度轮询
- 下载页选择保存目录
- 下载页自动识别并自定义视频名称
- 视频名称规范化后保存
- 视频管理页查看所有已索引视频
- 全选、批量删除、打开文件、打开所在文件夹、复制路径
- SQLite 视频索引
- 后台定时修复失效索引记录

规划中：

- 编辑流水线
- 多平台发布
- 更完整的工作流编排

---

## 快速开始

### 环境要求

- Python 3.8+
- `pip`

### 安装

```bash
git clone <repository_url>
cd ViralDramaBot

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### 启动 Web 应用

```bash
python app.py
```

启动后访问：

- 首页: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

也可以使用：

```bash
start-web.bat
```

---

## 主要功能

### 1. 视频下载

- 输入抖音分享链接
- 点击浏览按钮选择本地保存目录
- 可自动识别标题，也可手动修改视频名称
- 下载开始后立即显示进度条和保存路径

视频名称保存规则：

- 只保留中文、英文、数字
- 其他字符统一替换成 `_`
- 按 `_` 切分后只保留前两个有效片段
- 最终将这两个片段直接拼接后作为文件名

### 2. 视频管理

视频管理页显示的是 SQLite 索引中的全部视频，而不是当前保存目录下的文件。

支持：

- 查看所有已索引视频
- 显示保存时的最终文件名
- 显示完整路径、文件大小、创建时间
- 全选 / 取消全选
- 批量删除
- 打开文件
- 打开所在文件夹
- 复制完整路径

### 3. 应用设置

支持配置：

- 默认保存目录
- 下载超时时间
- 最大重试次数

---

## 项目结构

```text
ViralDramaBot/
├── app.py
├── cli.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── src/
│   ├── core/
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── __init__.py
│   ├── ingestion/
│   │   └── douyin/
│   │       ├── __init__.py
│   │       ├── processor.py
│   │       ├── downloader.py
│   │       └── README.md
│   ├── editing/
│   ├── publishing/
│   ├── workflow/
│   └── utils/
├── ARCHITECTURE.md
├── WEB_GUIDE.md
└── requirements.txt
```

---

## 配置

### 环境变量

```bash
set WORK_DIR=".data"
set DOWNLOAD_TIMEOUT="1200"
set MAX_RETRIES="3"
set DEBUG="1"
```

### 默认配置

当前默认值来自 [src/core/config.py](./src/core/config.py)：

- `WORK_DIR = .data`
- `DOWNLOAD_TIMEOUT = 1200`
- `MAX_RETRIES = 3`

---

## 存储说明

### 视频文件

视频文件保存到你在下载页或设置页选择的目录中。

### 视频索引

视频管理页的数据来自 SQLite 索引文件：

```text
.data/metadata/video_index.db
```

这份索引只记录通过当前应用成功下载并写入索引的视频。

### 索引修复

应用启动后会启动后台定时任务，默认每 300 秒检查一次 SQLite 索引，把磁盘上已经不存在的文件记录移除。

---

## 性能实现

当前下载链路的几个关键点：

- 抖音下载使用流式写入
- 分块大小已调到 `256KB`
- 视频索引使用 SQLite，而不是 JSON
- 视频列表读取不再每次全量检查文件是否存在
- 批量删除时会一次性更新索引

---

## Python 调用示例

```python
from src.core import initialize_app, config
from src.ingestion.douyin import get_downloader

initialize_app()

config.update(work_dir=".data", download_timeout=1200, max_retries=3)

downloader = get_downloader()
downloader.configure(
    download_timeout=config.download_timeout,
    max_retries=config.max_retries
)

def on_progress(progress):
    print(progress["percentage"])

result = downloader.download_video(
    "https://v.douyin.com/xxxxx/",
    on_progress=on_progress,
    file_name="自定义视频名"
)

print(result)
```

---

## 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [WEB_GUIDE.md](./WEB_GUIDE.md)
- [src/ingestion/douyin/README.md](./src/ingestion/douyin/README.md)

---

## 说明

当前这套代码更偏“本机使用的工具型后台”，适合个人或小规模使用场景。

如果后续要继续扩展，推荐优先方向是：

- 视频管理分页与筛选
- 多目录分组展示
- 更完整的任务队列
- 编辑和发布链路接入
