# ViralDramaBot

短剧素材下载与管理工具。一站式短剧自动化流水线，支持抖音视频下载、微信视频号自动发布。

---

## 当前状态

### 已实现

**抖音视频采集：**

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

**微信视频号发布：**

- 多账号管理（最多 50 个账号）
- 扫码登录，Cookie 持久化
- 单个/批量视频上传
- 定时发布（Cron 表达式 / 间隔分钟）
- 视频号剧集链接关联
- 后台 Cookie 有效性轮询
- 浏览器实例池管理

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

- 首页: `http://localhost:8000`
- 视频号管理: `http://localhost:8000/frontend/weixin.html`
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

详见 [src/publishing/weixin/README.md](./src/publishing/weixin/README.md)

核心功能：

- **账号管理**：创建账号 → 扫码登录 → Cookie 自动保存
- **单个上传**：选择视频 → 填写信息 → 立即/定时发表
- **批量上传**：选择多个视频 → 统一标签 → 串行上传
- **定时发布**：支持 Cron 表达式或间隔分钟
- **剧集关联**：支持关联视频号剧集

### 4. 应用设置

支持配置：

- 默认保存目录
- 下载超时时间
- 最大重试次数

---

## 项目结构

```text
ViralDramaBot/
├── app.py                              # FastAPI 服务入口
├── cli.py                              # CLI 命令行入口
├── frontend/
│   ├── index.html                      # 主页面（下载/管理/设置）
│   ├── weixin.html                     # 视频号管理页面
│   ├── app.js                          # Vue 3 前端逻辑
│   └── style.css                       # 页面样式
├── src/
│   ├── core/
│   │   ├── config.py                   # 配置管理
│   │   ├── logger.py                   # 日志
│   │   └── __init__.py
│   ├── ingestion/
│   │   └── douyin/
│   │       ├── processor.py            # 底层解析与下载
│   │       ├── downloader.py           # 上层统一下载接口
│   │       ├── __init__.py
│   │       └── README.md
│   ├── publishing/
│   │   └── weixin/
│   │       ├── config.py               # 视频号模块配置
│   │       ├── schemas.py              # Pydantic 数据模型
│   │       ├── dao.py                  # SQLite 数据访问层
│   │       ├── account_manager.py      # 账号管理（登录/Cookie）
│   │       ├── browser.py              # 浏览器实例池
│   │       ├── uploader.py             # 视频上传引擎
│   │       ├── scheduler.py            # 定时发布调度
│   │       ├── metadata.py             # 元数据解析
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
# 通用配置
set WORK_DIR=".data"
set DOWNLOAD_TIMEOUT="1200"
set MAX_RETRIES="3"
set DEBUG="1"

# 视频号配置
set BROWSER_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set WEIXIN_MAX_CONCURRENT_UPLOADS="1"
set WEIXIN_INTER_UPLOAD_COOLDOWN_SEC="20"
```

### 默认配置

当前默认值来自 [src/core/config.py](./src/core/config.py)：

- `WORK_DIR = .data`
- `DOWNLOAD_TIMEOUT = 1200`
- `MAX_RETRIES = 3`

视频号模块配置来自 [src/publishing/weixin/config.py](./src/publishing/weixin/config.py)：

- `MAX_BROWSER_INSTANCES = 3`
- `UPLOAD_TIMEOUT = 600`
- `MAX_ACCOUNTS = 50`
- `INTER_UPLOAD_COOLDOWN_SEC = 20`

---

## 存储说明

### 视频文件

视频文件保存到你在下载页或设置页选择的目录中。

### 视频索引

视频管理页的数据来自 SQLite 索引文件：

```text
.data/metadata/video_index.db
```

### 视频号数据

视频号模块的数据存储在：

```text
.data/weixin/
├── weixin.db                           # 账号、任务、计划数据库
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

- 全局串行上传，避免浏览器实例冲突
- 连续上传间隔 20 秒，降低风控风险
- Cookie 后台轮询，每小时检查一次有效性
- 模拟人类操作延迟，随机 0.5-2 秒

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
