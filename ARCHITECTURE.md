# ViralDramaBot 架构说明

## 概览

当前项目的主线是一套抖音下载 Web 工具，整体由三层组成：

1. 前端界面层
2. Web API 与索引管理层
3. 抖音解析与下载层

目前编辑层、发布层、工作流层仍然是预留结构。

---

## 目录结构

```text
ViralDramaBot/
├── app.py                       # FastAPI 服务入口
├── frontend/
│   ├── index.html              # 页面入口
│   ├── app.js                  # Vue 3 前端逻辑
│   └── style.css               # 页面样式
├── src/
│   ├── core/
│   │   ├── config.py           # 配置管理
│   │   ├── logger.py           # 日志
│   │   └── __init__.py
│   ├── ingestion/
│   │   └── douyin/
│   │       ├── processor.py    # 底层解析与下载
│   │       ├── downloader.py   # 上层统一下载接口
│   │       ├── __init__.py
│   │       └── README.md
│   ├── editing/
│   ├── publishing/
│   ├── workflow/
│   └── utils/
├── WEB_GUIDE.md
├── README.md
└── ARCHITECTURE.md
```

---

## 分层结构

```text
用户
  ↓
frontend/app.js
  ↓
app.py (FastAPI)
  ↓
src/ingestion/douyin/downloader.py
  ↓
src/ingestion/douyin/processor.py
  ↓
抖音页面 / 视频源站
```

并行支撑模块：

```text
app.py
  ├─ src/core/config.py
  ├─ src/core/logger.py
  └─ SQLite 索引: .data/metadata/video_index.db
```

---

## 模块职责

### `frontend/app.js`

负责：

- 下载页交互
- 视频管理页交互
- 设置页交互
- 调用 REST API
- 轮询下载进度

主要行为：

- 浏览本地目录
- 自动识别视频标题
- 视频名称规范化
- 下载完成后刷新视频列表
- 视频管理页批量选择、删除、打开文件和复制路径

### `app.py`

负责：

- 提供 Web API
- 维护下载进度状态
- 管理 SQLite 视频索引
- 处理打开文件、打开目录等本地操作
- 启动后台索引修复任务

主要接口包括：

- `POST /api/videos/download`
- `POST /api/videos/parse`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `POST /api/videos/batch-delete`
- `POST /api/videos/{video_id}/open`
- `POST /api/videos/{video_id}/open-folder`
- `GET /api/download-progress`
- `GET /api/browse-directory`
- `GET /api/settings`
- `PUT /api/settings`
- `GET /api/status`

### `src/core/config.py`

负责：

- 读取环境变量
- 初始化工作目录
- 提供当前保存目录和超时配置
- 生成视频保存路径

核心配置项：

- `work_dir`
- `download_timeout`
- `max_retries`

### `src/ingestion/douyin/downloader.py`

负责：

- 向上层暴露统一接口
- 把底层数据结构转换成字典
- 同步运行时配置到 `DouyinProcessor`

### `src/ingestion/douyin/processor.py`

负责：

- 从分享文本中提取 URL
- 跟随短链接重定向
- 提取视频 ID
- 请求视频 HTML
- 解析标题和无水印下载地址
- 流式下载视频文件

性能参数：

- 文件下载分块大小：`256KB`
- 下载超时：`(60, max(timeout, 300))`
- 默认下载超时：`1200`

---

## 数据流

### 下载流程

```text
用户输入抖音链接
  ↓
前端调用 /api/videos/parse（可选）
  ↓
前端调用 /api/videos/download
  ↓
app.py 更新当前下载状态
  ↓
DouyinDownloader.download_video()
  ↓
DouyinProcessor.parse_share_url()
  ↓
DouyinProcessor.download_video()
  ↓
文件保存到选定目录
  ↓
app.py 写入 SQLite 视频索引
  ↓
前端轮询 /api/download-progress
```

### 视频管理流程

```text
前端打开视频管理页
  ↓
GET /api/videos
  ↓
app.py 查询 SQLite 索引
  ↓
返回全部已索引视频
  ↓
前端展示标题、路径、大小、时间和操作按钮
```

### 删除流程

```text
前端发起单个或批量删除
  ↓
app.py 删除磁盘文件
  ↓
app.py 更新 SQLite 索引
  ↓
前端刷新列表
```

---

## 索引设计

视频管理页的数据来源是 SQLite：

```text
.data/metadata/video_index.db
```

当前索引表：

```sql
CREATE TABLE videos (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    save_dir TEXT
);
```

设计目标：

- 不再依赖当前保存目录扫描
- 能管理不同目录下的历史下载文件
- 提高列表读取和批量删除效率

### 后台修复

应用启动后会创建后台协程，默认每 300 秒执行一次：

- 检查索引中的 `file_path` 是否仍存在
- 删除已失效的索引记录

这样视频列表加载时不需要每次全量检查文件存在性。

---

## 命名规则

用户输入的视频名称，或者自动识别出的标题，会在前后端统一按同一规则处理：

- 非中文、非英文、非数字字符替换为 `_`
- 连续 `_` 折叠
- 按 `_` 切分
- 只保留前两个有效片段
- 将这两个片段直接拼接

最终这个名称会作为实际保存文件名。

---

## 本地能力边界

当前项目具备一些“仅适合本机运行”的能力：

- 浏览本地目录
- 打开视频文件
- 打开所在文件夹

这些操作依赖服务端运行机器本身的桌面环境，因此当前架构更适合本机工具型使用，不适合直接当成纯远程无界面服务。

---

## 后续扩展建议

在当前架构上继续扩展时，建议优先保持以下原则：

- 平台解析逻辑继续放在 `src/ingestion/<platform>/processor.py`
- Web 层只处理状态、索引和接口，不直接承载复杂平台逻辑
- 所有历史资产统一进入数据库索引
- 大批量任务逐步迁移到任务队列而不是单个后台任务
