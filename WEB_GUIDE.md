# ViralDramaBot Web 使用指南

## 功能概览

主应用为单页应用（`frontend/index.html` + `app.js`），包含四个页面：

1. `📥 视频下载` — 单条或批量下载抖音视频
2. `📺 视频管理` — SQLite 索引中的全部视频
3. `📤 视频号上传` — 账号、批量上传、任务、定时、发布位置管理
4. `⚙️ 应用设置` — 保存目录与超时/重试等

另提供精简独立页：`http://localhost:8000/frontend/weixin.html`（无「发布位置管理」Tab）。

---

## 启动方式

### 通用方式

```bash
pip install -r requirements.txt
python app.py
```

访问：

- `http://localhost:8000` — 自动跳转首页
- `http://localhost:8000/docs` — Swagger API 文档

### 脚本启动

```bash
start-web.bat
```

### 打包版

运行 `dist\ViralDramaBot.exe` 后，数据目录为 `%APPDATA%\ViralDramaBot`，行为与开发版一致。

---

## 页面说明

### 1. 视频下载

- 输入一条或多条抖音短链接/长链接（批量最多 50 条）
- 可设置并发数（1–10，默认 6）
- 浏览本地目录作为保存路径
- 自动识别标题或手动修改视频名称
- 实时查看聚合下载进度

视频名称保存规则：

- 非中文、英文、数字字符替换为 `_`
- 按 `_` 切分后只取前两个有效片段
- 最终将两段直接拼接为实际保存名

### 2. 视频管理

列表来自 SQLite 索引，而非当前保存目录扫描。

支持：全选/取消、批量删除、打开文件、打开所在文件夹、复制完整路径。

### 3. 视频号上传

Tab 包括：

- **账号管理** — 创建、扫码登录、刷新、打开作品列表、删除
- **批量上传** — 多选视频、选账号、代理 Profile、发表位置、剧集名
- **任务列表** — 筛选、批量删除、重试失败任务
- **定时发布** — Cron 或间隔分钟
- **发布位置管理** — 代理 Profile CRUD、检测出口 IP、常用地点

### 4. 应用设置

- 视频保存目录、下载超时、最大重试
- 视频号上传超时、连续上传间隔、最大重试

代理全局开关已迁移至「发布位置管理」；设置页中对应卡片已隐藏，但 API 仍支持 `weixin_proxy_*` 字段。

---

## API 概览

完整参数见 Swagger：`/docs`。以下为常用接口摘要。

### 下载视频（支持批量）

```http
POST /api/videos/download
Content-Type: application/json
```

单条：

```json
{
  "link": "https://v.douyin.com/xxxxx/",
  "save_path": ".data",
  "file_name": "视频标题",
  "max_concurrent": 6
}
```

批量（`tasks` 与 `link`/`links` 二选一）：

```json
{
  "tasks": [
    { "link": "https://v.douyin.com/aaa/", "file_name": "第一集" },
    { "link": "https://v.douyin.com/bbb/", "file_name": "" }
  ],
  "save_path": ".data",
  "max_concurrent": 4
}
```

响应：

```json
{
  "status": "started",
  "message": "批量下载任务已启动，共 2 个，并发 4",
  "total_count": 2,
  "max_concurrent": 4,
  "save_path": "/absolute/path/to/.data"
}
```

### 解析视频信息

```http
POST /api/videos/parse
Content-Type: application/json
```

```json
{ "link": "https://v.douyin.com/xxxxx/" }
```

### 获取下载进度

```http
GET /api/download-progress
```

批量下载时 `percentage` 为各任务字节加权进度；`message` 含已完成/成功/失败计数。

### 浏览本地目录 / 选择视频文件

```http
GET /api/browse-directory
GET /api/browse-files
```

`browse-files` 返回多选视频路径列表，供视频号批量上传使用。

### 视频列表与删除

```http
GET /api/videos
GET /api/videos/{video_id}
DELETE /api/videos/{video_id}
POST /api/videos/batch-delete
POST /api/videos/{video_id}/open
POST /api/videos/{video_id}/open-folder
```

### 应用设置

```http
GET /api/settings
PUT /api/settings
```

请求体示例：

```json
{
  "video_dir": ".data",
  "download_timeout": 1200,
  "max_retries": 3,
  "weixin_upload_timeout": 600,
  "weixin_inter_upload_cooldown": 20,
  "weixin_max_retries": 3,
  "weixin_proxy_enabled": true,
  "weixin_proxy_scheme": "http",
  "weixin_proxy_host": "127.0.0.1",
  "weixin_proxy_port": 1080,
  "weixin_location_mode": "proxy_ip"
}
```

### 系统状态

```http
GET /api/status
```

---

## 视频号 API 摘要

### 批量上传

```http
POST /api/weixin/upload/batch
Content-Type: application/json
```

```json
{
  "account_id": 1,
  "video_paths": ["C:\\videos\\ep01.mp4", "C:\\videos\\ep02.mp4"],
  "titles": ["第1集", "第2集"],
  "metadata_source": "manual",
  "drama_link": "我的短剧",
  "proxy_profile_id": 1,
  "location_label": "深圳人民公园"
}
```

响应 `status` 为 `queued`，含 `task_ids` 与队列位置 `queue`。

### 队列状态

```http
GET /api/weixin/upload/batch/queue
```

### 任务

```http
GET /api/weixin/tasks?account_id=1&status=failed
DELETE /api/weixin/tasks/{task_id}
POST /api/weixin/tasks/batch-delete
POST /api/weixin/tasks/{task_id}/retry
```

### 账号

```http
POST /api/weixin/accounts
GET /api/weixin/accounts
POST /api/weixin/accounts/{account_id}/login
POST /api/weixin/accounts/{account_id}/refresh
POST /api/weixin/accounts/{account_id}/open-post-list
POST /api/weixin/accounts/check-cookies
GET /api/weixin/accounts/refresh-status
POST /api/weixin/accounts/refresh-all
DELETE /api/weixin/accounts/{account_id}
```

### 代理与常用位置

```http
GET /api/weixin/proxy/test
GET|POST /api/weixin/proxy-profiles
PUT|DELETE /api/weixin/proxy-profiles/{profile_id}
POST /api/weixin/proxy-profiles/{profile_id}/check
POST /api/weixin/proxy-profiles/check-all
GET|POST /api/weixin/favorite-locations
DELETE /api/weixin/favorite-locations/{location_id}
```

### 定时计划

```http
POST /api/weixin/schedule
GET /api/weixin/schedule
DELETE /api/weixin/schedule/{schedule_id}
```

更多字段说明见 [src/publishing/weixin/README.md](./src/publishing/weixin/README.md) 与 [ARCHITECTURE.md](./ARCHITECTURE.md)。

---

## 存储说明

### 开发环境

默认数据目录：项目根目录 `.data`（由 `app.py` 的 `DATA_DIR` 决定）。

### 视频索引

```text
.data/metadata/video_index.db
```

字段：`video_id`, `title`, `file_path`, `file_size`, `created_at`, `save_dir`。

### 视频号数据

```text
{WORK_DIR}/weixin/weixin.db
{WORK_DIR}/weixin/cookies/
```

`WORK_DIR` 未设置环境变量时，模块使用 `~/.viraldramabot_data`；Web 应用启动后会将工作目录设为 `DATA_DIR`（开发下即 `.data`）。

### 索引修复

后台每 **300** 秒清理索引中已不存在的文件记录。

---

## 使用建议

- 大文件下载建议 `download_timeout` 保持 **1200** 秒左右
- 视频号批量上传间隔：模块环境变量默认 **45** 秒，可在设置中调低；代理不稳定时勿设过小
- 「打开文件/文件夹」、扫码登录依赖本机桌面与 Edge 浏览器
- 视频管理页不扫描磁盘历史文件；仅显示已写入索引的下载记录

---

## 常见问题

### 1. 磁盘里已有 mp4，管理页看不到

当前不会自动补录索引，只有通过本工具下载并成功写入索引的才会显示。

### 2. 下载后如何看保存路径

下载页进度卡片与视频管理页均显示完整路径，支持复制。

### 3. 下载完成为何不自动跳转管理页

设计为留在下载页并刷新列表，不自动切 Tab。

### 4. 为何能看到不同目录下的视频

列表来自全局 SQLite 索引，与当前选择的保存目录无关。

### 5. 没有单独的「单条上传」API

Web 端通过 `POST /api/weixin/upload/batch` 传入单个 `video_paths` 即可；Python 可直接调用 `Uploader.upload_video()`。
