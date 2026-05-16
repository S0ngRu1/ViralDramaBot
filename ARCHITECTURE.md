# ViralDramaBot 架构说明

## 概览

当前项目包含两大功能模块：

1. **抖音视频采集** - 解析链接、无水印下载、视频管理
2. **微信视频号发布** - 多账号管理、自动上传、定时发布

整体由四层组成：

1. 前端界面层
2. Web API 层
3. 采集层（抖音下载）
4. 发布层（视频号上传）

编辑层、工作流层仍然是预留结构。

---

## 目录结构

```text
ViralDramaBot/
├── app.py                              # FastAPI 服务入口
├── cli.py                              # CLI 命令行入口
├── run_packaged.py                     # PyInstaller 打包入口
├── ViralDramaBot.spec
├── build-exe.bat
├── frontend/
│   ├── index.html                      # 主页面入口
│   ├── weixin.html                     # 视频号管理页面
│   ├── app.js                          # Vue 3 前端逻辑
│   └── style.css                       # 页面样式
├── src/
│   ├── core/
│   │   ├── config.py                   # 全局配置管理
│   │   ├── logger.py                   # 日志系统
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
│   │       ├── account_manager.py      # 账号管理（含 Cookie 轮询）
│   │       ├── browser.py              # 浏览器实例池
│   │       ├── uploader.py             # 视频上传引擎
│   │       ├── scheduler.py            # 定时发布调度
│   │       ├── metadata.py             # 元数据解析
│   │       ├── proxy.py                # 代理检测
│   │       ├── geocoding.py            # IP 归属地
│   │       ├── batch_queue.py          # 批量上传队列
│   │       └── README.md
│   ├── editing/                         # 编辑层（预留）
│   ├── workflow/                        # 工作流层（预留）
│   └── utils/                           # 工具层（预留）
├── ARCHITECTURE.md
├── WEB_GUIDE.md
└── README.md
```

---

## 分层结构

### 抖音采集链路

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

### 视频号发布链路

```text
用户
  ↓
frontend/weixin.html + app.js
  ↓
app.py (FastAPI)
  ↓
src/publishing/weixin/uploader.py
  ↓
src/publishing/weixin/browser.py (DrissionPage)
  ↓
微信视频号创作者中心
```

### 并行支撑模块

```text
app.py
  ├─ src/core/config.py
  ├─ src/core/logger.py
  ├─ {DATA_DIR}/metadata/video_index.db   (抖音视频索引)
  └─ {WORK_DIR}/weixin/weixin.db         (视频号数据)
```

---

## 模块职责

### `frontend/app.js`（SPA，挂载于 `index.html`）

负责四个主页面：

- **视频下载**：单条/批量链接、并发下载、进度轮询
- **视频管理**：索引列表、批量删除、打开文件/文件夹
- **视频号上传**：账号、批量上传、任务列表、定时计划、发布位置管理（代理 Profile + 常用地点）
- **应用设置**：保存目录、下载与视频号超时/重试/间隔

主要行为：

- 浏览本地目录与多选视频文件（`browse-directory` / `browse-files`）
- 自动识别视频标题、名称规范化
- 下载完成后刷新视频列表
- 视频号批量上传入队、轮询账号刷新状态与任务列表

### `frontend/weixin.html`

独立精简版视频号页（无「发布位置管理」Tab），功能子集与 SPA 内视频号页类似，侧栏可跳回 `index.html`。

### `app.py`

负责：

- 提供 Web API
- 维护下载进度状态
- 管理 SQLite 视频索引
- 处理打开文件、打开目录等本地操作
- 启动后台索引修复任务
- 启动视频号模块（账号管理、上传调度、Cookie 轮询）

主要接口包括：

**抖音 / 通用：**
- `GET /` — 重定向至 `/frontend/index.html`
- `GET /api/status`
- `POST /api/videos/download` — 支持 `link` / `links` / `tasks[]`，`max_concurrent`（1–10），最多 50 条
- `POST /api/videos/parse`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `DELETE /api/videos/{video_id}`
- `POST /api/videos/batch-delete`
- `POST /api/videos/{video_id}/open`
- `POST /api/videos/{video_id}/open-folder`
- `GET /api/download-progress`
- `GET /api/browse-directory`
- `GET /api/browse-files`
- `GET /api/settings`
- `PUT /api/settings`

**视频号 — 代理与位置：**
- `GET /api/weixin/proxy/test`
- `GET|POST /api/weixin/proxy-profiles`
- `PUT|DELETE /api/weixin/proxy-profiles/{profile_id}`
- `POST /api/weixin/proxy-profiles/{profile_id}/check`
- `POST /api/weixin/proxy-profiles/check-all`
- `GET|POST /api/weixin/favorite-locations`
- `DELETE /api/weixin/favorite-locations/{location_id}`

**视频号 — 账号：**
- `POST|GET /api/weixin/accounts`
- `DELETE /api/weixin/accounts/{account_id}`
- `POST /api/weixin/accounts/{account_id}/login`
- `POST /api/weixin/accounts/{account_id}/refresh`
- `POST /api/weixin/accounts/{account_id}/open-post-list`
- `POST /api/weixin/accounts/check-cookies`
- `GET /api/weixin/accounts/refresh-status`
- `POST /api/weixin/accounts/refresh-all`

**视频号 — 上传与任务：**
- `POST /api/weixin/upload/batch` — 创建任务并入全局串行队列
- `GET /api/weixin/upload/batch/queue`
- `GET /api/weixin/tasks` — 可选 `account_id`、`status` 筛选
- `DELETE /api/weixin/tasks/{task_id}`
- `POST /api/weixin/tasks/batch-delete`
- `POST /api/weixin/tasks/{task_id}/retry`

**视频号 — 定时计划：**
- `POST /api/weixin/schedule`
- `GET /api/weixin/schedule`
- `DELETE /api/weixin/schedule/{schedule_id}`

### `src/core/config.py`

负责：

- 读取环境变量
- 初始化工作目录
- 提供当前保存目录和超时配置
- 生成视频保存路径

核心配置项：

- `work_dir` / `video_dir`（API 字段名）
- `download_timeout`
- `max_retries`
- `weixin_upload_timeout`
- `weixin_inter_upload_cooldown`
- `weixin_max_retries`
- `weixin_proxy_enabled` / `weixin_proxy_scheme` / `weixin_proxy_host` / `weixin_proxy_port`
- `weixin_location_mode`（`proxy_ip` | `hidden`）

开发环境 `app.py` 将 `DATA_DIR` 设为项目 `.data`；打包 exe 时为 `%APPDATA%\ViralDramaBot`。视频索引库路径为 `{DATA_DIR}/metadata/video_index.db`。

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

### `src/publishing/weixin/config.py`

负责：

- 视频号模块全局配置
- 浏览器配置（路径、超时、实例数）
- 上传配置（并发数、重试、格式限制）
- 数据目录配置

核心配置项：

- `BROWSER_PATH` - Edge 浏览器路径
- `MAX_BROWSER_INSTANCES` - 最大浏览器实例数（默认 3）
- `UPLOAD_TIMEOUT` - 上传超时（默认 600 秒）
- `MAX_CONCURRENT_UPLOADS` - 最大并发上传数（默认 1）
- `INTER_UPLOAD_COOLDOWN_SEC` - 连续上传间隔（环境变量默认 45 秒，lifespan 同步全局设置）
- `MAX_ACCOUNTS` - 最大账号数（默认 50）
- `UPLOAD_BYPASS_HOSTS` - 上传 CDN 不走代理的域名通配符
- `PROXY_ENABLED` / `PROXY_SCHEME` / `PROXY_HOST` / `PROXY_PORT` / `LOCATION_MODE`

### `src/publishing/weixin/schemas.py`

负责：

- 定义数据模型（Pydantic）
- 账号状态枚举
- 任务状态枚举
- 请求/响应模型

核心模型：

- `AccountStatus` - active / expired / logging_in / error
- `TaskStatus` - pending / uploading / processing / filling / publishing / completed / failed / cancelled
- `AccountCreate` / `AccountInfo`
- `UploadTaskCreate` / `TaskInfo`
- `BatchUploadCreate`
- `ScheduleCreate` / `ScheduleInfo`

### `src/publishing/weixin/dao.py`

负责：

- SQLite 数据访问层
- 账号表 CRUD
- 上传任务表 CRUD
- 定时计划表 CRUD

### `src/publishing/weixin/account_manager.py`

负责：

- 账号创建和删除
- 扫码登录流程
- Cookie 保存和加载
- 自动登录验证
- 批量 Cookie 有效性检查

核心流程：

1. `create_account()` - 创建账号记录
2. `login_with_qrcode()` - 启动浏览器 → 打开登录页 → 等待扫码 → 保存 Cookie
3. `auto_login()` - 无头浏览器加载 Cookie → 验证有效性
4. `check_all_accounts_cookies()` - 批量检查所有活跃账号

### `src/publishing/weixin/browser.py`

负责：

- 浏览器实例池管理
- 为不同场景创建浏览器实例
- 反检测设置

核心函数：

- `get_browser_for_account()` - 为账号创建独立浏览器（扫码/上传）
- `get_browser_for_channels_viewer()` - 为视频管理页创建独立浏览器
- `BrowserPool.acquire()` - 从池中获取浏览器实例

### `src/publishing/weixin/uploader.py`

负责：

- 视频上传全流程自动化
- 文件验证
- 元数据填写
- 定时发布设置
- 剧集链接关联

核心流程：

1. `upload_video()` - 主入口
2. `_navigate_to_create()` - 导航到发布页面
3. `_upload_file()` - 注入文件路径到 input 元素
4. `_wait_for_upload_complete()` - 等待视频处理完成
5. `_fill_metadata()` - 填写描述、标签、短标题
6. `_add_drama_link()` - 关联视频号剧集
7. `_set_schedule_time()` - 设置定时发布时间
8. `_click_publish()` - 点击发表按钮
9. `_confirm_publish()` - 确认发表，等待跳转

### `src/publishing/weixin/scheduler.py`

负责：

- 定时发布调度（APScheduler）
- Cron 表达式触发
- 间隔分钟触发
- 单次定时任务
- 定时计划恢复

### `src/publishing/weixin/metadata.py`

负责：

- 视频元数据解析
- 支持三种来源：手动、文件名、AI
- 文件名格式解析（下划线分隔、井号标签）

### `src/publishing/weixin/proxy.py`

负责：

- 检测当前或指定 Profile 的代理出口 IP
- 缓存检测结果；上传前校验
- 与 `geocoding.py` 配合解析归属地

### `src/publishing/weixin/batch_queue.py`

负责：

- 多个「批量上传」请求的全局 FIFO 串行执行
- `submit()` 入队、`snapshot()` 供 API 查询队列状态

---

## 数据流

### 抖音下载流程

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

### 视频号批量上传流程

```text
用户选择多个视频和账号（可选代理 Profile、发表位置）
  ↓
前端调用 POST /api/weixin/upload/batch
  ↓
app.py 为每个视频 create_task，封装 do_batch_upload
  ↓
batch_upload_queue.submit() 入全局队列（多批串行）
  ↓
队列执行：对每个 task 调用 Uploader.upload_video()
  ├─ 验证账号状态
  ├─ 验证视频文件
  ├─ 解析元数据
  ├─ 获取浏览器实例
  ├─ 加载 Cookie
  ├─ 导航到发布页面
  ├─ 上传视频文件
  ├─ 等待处理完成
  ├─ 填写描述/标签/短标题
  ├─ 关联剧集（可选）
  ├─ 设置定时（可选）
  ├─ 点击发表
  └─ 保存更新后的 Cookie
  ↓
更新任务状态为 completed
  ↓
前端轮询任务状态
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

## 数据库设计

### 视频索引数据库

位置：`{DATA_DIR}/metadata/video_index.db`（开发环境一般为 `.data/metadata/video_index.db`）

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

### 视频号数据库

位置：`.data/weixin/weixin.db`

```sql
-- 账号表
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    wechat_id TEXT,
    status TEXT NOT NULL DEFAULT 'expired',
    cookie_path TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

-- 上传任务表
CREATE TABLE upload_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    video_path TEXT NOT NULL,
    title TEXT,
    description TEXT,
    tags TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata_source TEXT NOT NULL DEFAULT 'manual',
    scheduled_at TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_msg TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    proxy_ip TEXT,
    proxy_location TEXT,
    proxy_profile_id INTEGER,
    location_label TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- 代理 Profile 表
CREATE TABLE proxy_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scheme TEXT NOT NULL DEFAULT 'http',
    host TEXT NOT NULL DEFAULT '127.0.0.1',
    port INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    last_ip TEXT,
    last_country TEXT,
    last_region TEXT,
    last_city TEXT,
    last_isp TEXT,
    last_check_error TEXT,
    created_at TEXT NOT NULL
);

-- 常用发表位置
CREATE TABLE favorite_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- 定时计划表
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    video_paths TEXT NOT NULL,
    cron_expr TEXT,
    interval_minutes INTEGER,
    titles TEXT,
    descriptions TEXT,
    tags TEXT,
    metadata_source TEXT NOT NULL DEFAULT 'manual',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    next_run_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- 索引
CREATE INDEX idx_tasks_status ON upload_tasks(status);
CREATE INDEX idx_tasks_account ON upload_tasks(account_id);
CREATE INDEX idx_accounts_status ON accounts(status);
```

---

## 后台任务

应用 `lifespan` 启动后会运行：

### 1. 索引修复（`periodic_index_repair`）

- 间隔：`INDEX_REPAIR_INTERVAL_SECONDS = 300`
- 功能：删除索引中磁盘已不存在的视频记录

### 2. Cookie 轮询（`CookieChecker`）

- 间隔：3600 秒（`COOKIE_CHECK_INTERVAL_SECONDS`）
- 功能：检查活跃账号 Cookie，失效则标记 `expired`

### 3. 定时发布调度（`UploadScheduler`）

- 引擎：APScheduler，时区 `Asia/Shanghai`
- 支持：Cron 表达式、间隔分钟
- 功能：按计划创建并执行上传任务

### 4. 批量上传队列（`batch_upload_queue`）

- 全局 FIFO，保证多个 batch 请求不会并行跑浏览器
- 停止应用时 `batch_upload_queue.stop()`

### 5. 启动时全量账号刷新

- `run_refresh_all_accounts()` 在后台线程执行，不阻塞启动
- 前端通过 `GET /api/weixin/accounts/refresh-status` 轮询进度

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

当前项目具备一些"仅适合本机运行"的能力：

- 浏览本地目录
- 打开视频文件
- 打开所在文件夹
- 控制本地浏览器（视频号上传）

这些操作依赖服务端运行机器本身的桌面环境，因此当前架构更适合本机工具型使用，不适合直接当成纯远程无界面服务。

---

## 后续扩展建议

在当前架构上继续扩展时，建议优先保持以下原则：

- 平台解析逻辑继续放在 `src/ingestion/<platform>/processor.py`
- 平台发布逻辑继续放在 `src/publishing/<platform>/`
- Web 层只处理状态、索引和接口，不直接承载复杂平台逻辑
- 所有历史资产统一进入数据库索引
- 大批量任务逐步迁移到任务队列而不是单个后台任务
