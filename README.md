# ViralDramaBot

短剧素材下载与管理工具。一站式短剧自动化流水线，支持抖音视频下载、微信视频号自动发布。

---

## 当前状态

### 已实现

**抖音视频采集：**

- 抖音短链接和长链接解析
- 无水印下载（支持单条或批量，最多 50 条，可配置并发 1–10）
- 下载进度轮询（批量时聚合进度）
- 下载页选择保存目录
- 下载页自动识别并自定义视频名称
- 视频名称规范化后保存
- 视频管理页查看所有已索引视频
- 全选、批量删除、打开文件、打开所在文件夹、复制路径
- SQLite 视频索引
- 后台定时修复失效索引记录（每 300 秒）

**微信视频号发布：**

- 多账号管理（最多 50 个账号）
- 扫码登录，Cookie 持久化；启动时与手动触发全量账号刷新
- 批量视频上传（串行队列，支持代理 Profile 与发表位置）
- 代理 Profile 管理、出口 IP 检测、常用发表位置
- 定时发布（Cron 表达式 / 间隔分钟）
- 视频号剧集链接关联
- 任务重试、批量删除；批量上传全局队列
- 后台 Cookie 有效性轮询（每 3600 秒）
- 浏览器实例池管理；上传 CDN 域名 bypass 代理

### 规划中

- 编辑流水线（CapCut/剪映集成）
- 更完整的工作流编排

---

## 快速开始

### 环境要求

- Python 3.8+
- `pip`
- Microsoft Edge 浏览器（视频号功能需要）

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

- 首页（下载 / 管理 / 视频号 / 设置）: `http://localhost:8000`
- 视频号独立页（精简版）: `http://localhost:8000/frontend/weixin.html`
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

### 3. 微信视频号发布

在首页侧栏进入「视频号上传」，或打开独立页 `weixin.html`。详见 [src/publishing/weixin/README.md](./src/publishing/weixin/README.md)。

核心功能：

- **账号管理**：创建账号 → 扫码登录 → Cookie 自动保存 → 可打开作品列表页
- **批量上传**：多选本地视频 → 指定代理 Profile / 发表位置 → 入全局串行队列
- **发布位置管理**：维护多个代理 Profile、检测出口 IP、收藏常用地点
- **定时发布**：支持 Cron 表达式或间隔分钟
- **剧集关联**：支持关联视频号剧集

### 4. 应用设置

支持配置：

- 默认保存目录
- 下载超时时间、最大重试次数
- 视频号上传超时、连续上传间隔、最大重试次数
- （代理全局开关等已迁移至「视频号上传 → 发布位置管理」）

---

## 项目结构

```text
ViralDramaBot/
├── app.py                              # FastAPI 服务入口
├── cli.py                              # CLI 命令行入口
├── run_packaged.py                     # PyInstaller 打包入口
├── ViralDramaBot.spec                  # PyInstaller 配置
├── build-exe.bat                       # Windows 一键打包脚本
├── frontend/
│   ├── index.html                      # SPA 入口（下载/管理/视频号/设置）
│   ├── weixin.html                     # 视频号独立页（精简版）
│   ├── app.js                          # Vue 3 前端逻辑
│   └── style.css                       # 页面样式
├── src/
│   ├── core/
│   │   ├── config.py                   # 全局配置（含视频号代理项）
│   │   ├── logger.py                   # 日志
│   │   └── __init__.py
│   ├── ingestion/
│   │   └── douyin/
│   │       ├── processor.py            # 底层解析与下载
│   │       ├── downloader.py           # 上层统一下载接口
│   │       └── README.md
│   ├── publishing/
│   │   └── weixin/
│   │       ├── config.py               # 视频号模块配置
│   │       ├── schemas.py              # Pydantic 数据模型
│   │       ├── dao.py                  # SQLite 数据访问层
│   │       ├── account_manager.py      # 账号管理（登录/Cookie/轮询）
│   │       ├── browser.py              # 浏览器实例池
│   │       ├── uploader.py             # 视频上传引擎
│   │       ├── scheduler.py            # 定时发布调度
│   │       ├── metadata.py             # 元数据解析
│   │       ├── proxy.py                # 代理检测与出口 IP
│   │       ├── geocoding.py            # IP 归属地
│   │       ├── batch_queue.py          # 批量上传串行队列
│   │       └── README.md
│   ├── editing/                         # 编辑层（预留）
│   ├── workflow/                        # 工作流层（预留）
│   └── utils/                           # 工具层（预留）
├── ARCHITECTURE.md
├── WEB_GUIDE.md
└── requirements.txt
```

---

## 配置

### 环境变量

```bash
# 通用配置（未设置 WORK_DIR 时回退到用户目录 ~/.viraldramabot_data）
set WORK_DIR=".data"
set DOWNLOAD_TIMEOUT="1200"
set MAX_RETRIES="3"

# 视频号配置
set BROWSER_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set WEIXIN_MAX_CONCURRENT_UPLOADS="1"
set WEIXIN_INTER_UPLOAD_COOLDOWN_SEC="45"
set WEIXIN_UPLOAD_TIMEOUT="600"
set WEIXIN_PROXY_ENABLED="true"
set WEIXIN_PROXY_SCHEME="http"
set WEIXIN_PROXY_HOST="127.0.0.1"
set WEIXIN_PROXY_PORT="0"
set WEIXIN_LOCATION_MODE="proxy_ip"
```

### 默认配置

全局默认值来自 [src/core/config.py](./src/core/config.py)（Web 设置页可覆盖并同步到 `WeixinConfig`）：

- `DOWNLOAD_TIMEOUT = 1200`
- `MAX_RETRIES = 3`
- `WEIXIN_UPLOAD_TIMEOUT = 600`
- `WEIXIN_INTER_UPLOAD_COOLDOWN_SEC = 20`（写入设置后同步；模块静态默认 45，见下）
- `WEIXIN_PROXY_ENABLED = true`

视频号模块静态配置来自 [src/publishing/weixin/config.py](./src/publishing/weixin/config.py)：

- `MAX_BROWSER_INSTANCES = 3`
- `UPLOAD_TIMEOUT = 600`（运行时由全局配置覆盖）
- `MAX_ACCOUNTS = 50`
- `INTER_UPLOAD_COOLDOWN_SEC = 45`（环境变量默认；lifespan 后以全局设置为准）
- `MAX_CONCURRENT_UPLOADS = 1`

---

## 存储说明

开发环境下数据目录默认为项目根目录下的 `.data`（`app.py` 中 `DATA_DIR`）。打包为 exe 后，数据目录为 `%APPDATA%\ViralDramaBot`。

### 视频文件

视频文件保存到你在下载页或设置页选择的目录中。

### 视频索引

视频管理页的数据来自 SQLite 索引文件：

```text
{DATA_DIR}/metadata/video_index.db
```

### 视频号数据

视频号模块的数据存储在：

```text
{WORK_DIR}/weixin/
├── weixin.db                           # 账号、任务、计划、代理 Profile、常用位置
├── logs/
└── cookies/                            # 账号 Cookie 文件
    ├── <账号名>_<时间>.json
    └── viewer/                         # 浏览器用户数据目录
```

---

## 性能实现

当前下载链路的几个关键点：

- 抖音下载使用流式写入
- 分块大小已调到 `256KB`
- 视频索引使用 SQLite，而不是 JSON
- 视频列表读取不再每次全量检查文件是否存在
- 批量删除时会一次性更新索引

视频号上传的关键点：

- 批量提交经 `batch_queue` 全局串行，避免多批任务并行
- 批内视频串行上传，成功后可按 `INTER_UPLOAD_COOLDOWN_SEC` 等待（默认 45s，可在设置中调小）
- 视频字节流 CDN 域名 bypass 代理，页面接口仍走代理以匹配发表位置
- Cookie 后台轮询，每 3600 秒检查一次有效性
- 模拟人类操作延迟，随机 0.5–2 秒

---

## 打包为 Windows 可执行文件

```bash
build-exe.bat
```

产物为 `dist\ViralDramaBot.exe`。入口为 `run_packaged.py`，会打包 `frontend/` 与 `src/`，启动后自动打开浏览器。数据写入 `%APPDATA%\ViralDramaBot`。

---

## Python 调用示例

### 抖音下载

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

### 视频号上传

```python
from src.publishing.weixin.dao import WeixinDAO
from src.publishing.weixin.account_manager import AccountManager
from src.publishing.weixin.uploader import Uploader

dao = WeixinDAO()
account_manager = AccountManager(dao)
uploader = Uploader(dao)

# 创建账号并扫码登录
account = account_manager.create_account("我的视频号")
account_id = account["id"]
account_manager.login_with_qrcode(account_id)

# 上传视频
task_id = dao.create_task(
    account_id=account_id,
    video_path=r"C:\videos\test.mp4",
    title="测试视频",
    description="这是一个测试",
    tags=["测试", "短剧"]
)

result = uploader.upload_video(
    task_id=task_id,
    account_id=account_id,
    video_path=r"C:\videos\test.mp4",
    title="测试视频"
)
print(result)
```

---

## 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 架构说明
- [WEB_GUIDE.md](./WEB_GUIDE.md) - Web 使用指南
- [src/ingestion/douyin/README.md](./src/ingestion/douyin/README.md) - 抖音下载模块
- [src/publishing/weixin/README.md](./src/publishing/weixin/README.md) - 视频号发布模块

---

## 说明

当前这套代码更偏"本机使用的工具型后台"，适合个人或小规模使用场景。

如果后续要继续扩展，推荐优先方向是：

- 视频管理分页与筛选
- 多目录分组展示
- 更完整的任务队列
- 编辑流水线接入
