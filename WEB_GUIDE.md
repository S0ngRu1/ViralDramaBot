# ViralDramaBot Web 使用指南

## 功能概览

主应用为单页应用（`frontend/index.html` + `app.js`），侧栏包含：

1. `📊 概览` — 运营工作台（素材 / 账号 / 任务 / 代理指标 + 近 N 小时流量）
2. `📥 素材下载` — 单条或批量下载抖音视频
3. `🎬 素材库` — SQLite 索引中的全部视频
4. `👤 账号管理` — 账号、批量上传、发布记录、流量筛选、定时计划、嵌入式登录
5. `🌐 代理与位置` — 代理 Profile 与常用发表位置
6. `📋 运行日志` — 进程内实时日志
7. `⚙️ 设置` — 保存目录、超时/重试、维护清理

另提供精简独立页：`http://localhost:8000/frontend/weixin.html`。

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

### 打包版（桌面应用）

**推荐：** 运行安装包 `ViralDramaBot-Setup.exe`（由 `build-installer.bat` 生成），按向导安装并勾选「创建桌面快捷方式」，之后从桌面或开始菜单启动。安装到 `C:\Program Files` 等目录需同意 UAC；也可选择「仅为当前用户安装」到用户目录（无需管理员）。

**开发自测：** 直接运行 `dist\ViralDramaBot\ViralDramaBot.exe`（需保持同目录依赖文件完整）。

无论哪种方式，用户数据与日志目录均为 `%APPDATA%\ViralDramaBot`，行为与开发版一致。卸载程序不会删除该目录下的数据。

---

## 页面说明

### 1. 概览

- 展示素材总数、账号状态分布、任务状态、代理启用数、上传队列
- 近 24 小时流量快照：按账号 / 剧集链接汇总播放量
- 「刷新流量数据」触发后台拉取；前端轮询直至完成

### 2. 素材下载

- 输入一条或多条抖音短链接/长链接（批量最多 50 条）
- 可设置并发数（1–10，默认 6）
- 浏览本地目录作为保存路径
- 自动识别标题或手动修改视频名称
- 实时查看聚合下载进度

视频名称保存规则：

- 非中文、英文、数字字符替换为 `_`
- 按 `_` 切分后只取前两个有效片段
- 最终将两段直接拼接为实际保存名

### 3. 素材库

列表来自 SQLite 索引，而非当前保存目录扫描。

支持：全选/取消、批量删除、打开文件、打开所在文件夹、复制完整路径。

启动时会扫描当前工作目录下未索引的 `.mp4` 并补录。

### 4. 账号管理

选中账号后的 Tab 包括：

- **视频上传** — 多选视频、代理 Profile、发表位置、剧集名、入队上传
- **视频号管理** — 应用内嵌入浏览器（登录 / 后台操作）
- **发布记录** — 任务筛选、批量删除、重试
- **视频流量筛选** — 观察期 + 最低播放量扫描，勾选删稿

另支持：创建账号、扫码登录、批量删除账号、定时发布计划。

### 5. 代理与位置

- 代理 Profile CRUD、检测出口 IP
- 常用发表位置收藏（批量上传时可下拉选择）

### 6. 运行日志

轮询 `GET /api/logs`，展示进程内最新日志（最多约 500 条，重启清空）。

### 7. 应用设置

- 视频保存目录、下载超时、最大重试
- 视频号上传超时、连续上传间隔、最大重试
- **维护清理**：清除日志、运行缓存、上传历史（不删账号 Cookie 与已下载视频文件）

代理全局开关已迁移至「代理与位置」；设置页中对应卡片已隐藏，但 API 仍支持 `weixin_proxy_*` 字段。

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
  "save_path": "C:\\Videos",
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
  "save_path": "C:\\Videos",
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
  "save_path": "/absolute/path/to/Videos"
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
GET /api/browse-file
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
POST /api/videos/rescan
```

### 应用设置

```http
GET /api/settings
PUT /api/settings
```

请求体示例：

```json
{
  "video_dir": "C:\\Videos",
  "download_timeout": 1200,
  "max_retries": 3,
  "weixin_upload_timeout": 600,
  "weixin_inter_upload_cooldown": 30,
  "weixin_max_retries": 3,
  "weixin_proxy_enabled": true,
  "weixin_proxy_scheme": "http",
  "weixin_proxy_host": "127.0.0.1",
  "weixin_proxy_port": 1080,
  "weixin_location_mode": "proxy_ip"
}
```

### 系统状态 / 健康 / 日志 / 维护

```http
GET /api/status
GET /api/health
GET /api/logs?since=0&limit=100
POST /api/maintenance/cleanup
```

维护清理请求体示例：

```json
{
  "logs": true,
  "cache": true,
  "upload_history": true
}
```

### 运营概览

```http
GET /api/dashboard
GET /api/dashboard/traffic
POST /api/dashboard/traffic/refresh?hours=24
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
POST /api/weixin/accounts/{account_id}/login-embedded
GET /api/weixin/login-sessions/{session_id}
POST /api/weixin/login-sessions/{session_id}/input
POST /api/weixin/login-sessions/{session_id}/cancel
POST /api/weixin/accounts/{account_id}/refresh
POST /api/weixin/accounts/{account_id}/open-post-list
POST /api/weixin/accounts/check-cookies
GET /api/weixin/accounts/refresh-status
POST /api/weixin/accounts/refresh-all
DELETE /api/weixin/accounts/{account_id}
POST /api/weixin/accounts/batch-delete
```

### 流量筛选

```http
POST /api/weixin/accounts/{account_id}/traffic/scan
GET /api/weixin/accounts/{account_id}/traffic/scan-status
POST /api/weixin/accounts/{account_id}/traffic/delete
```

扫描请求体示例：

```json
{
  "grace_period_hours": 48,
  "min_views": 1000
}
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

### 统一数据目录

开发版与打包版均为：

```text
%APPDATA%\ViralDramaBot\
```

由 `app.py` 在导入微信模块前固定 `WORK_DIR`，不再使用项目 `.data` 或 `~/.viraldramabot_data` 作为运行时根目录。

### 视频索引

```text
%APPDATA%\ViralDramaBot\metadata\video_index.db
```

字段：`video_id`, `title`, `file_path`, `file_size`, `created_at`, `save_dir`。

### 视频号数据

```text
%APPDATA%\ViralDramaBot\weixin\weixin.db
%APPDATA%\ViralDramaBot\weixin\cookies\
%APPDATA%\ViralDramaBot\weixin\traffic_snapshot.json
```

### 索引修复

后台每 **300** 秒清理索引中已不存在的文件记录。

---

## 使用建议

- 大文件下载建议 `download_timeout` 保持 **1200** 秒左右
- 视频号批量上传间隔：默认 **30** 秒，可在设置中调整；代理不稳定时勿设过小
- 「打开文件/文件夹」、扫码 / 嵌入式登录依赖本机桌面与 Edge 浏览器
- 素材库以索引为准；工作目录下的 `.mp4` 会在启动或 `rescan` 时补录

---

## 常见问题

### 1. 磁盘里已有 mp4，素材库看不到

若文件不在当前工作目录，不会自动出现。工作目录内的 `.mp4` 会在启动扫描或调用 `POST /api/videos/rescan` 后补录；其他目录需通过本工具下载写入索引。

### 2. 下载后如何看保存路径

下载页进度卡片与素材库均显示完整路径，支持复制。

### 3. 下载完成为何不自动跳转素材库

设计为留在下载页并刷新列表，不自动切 Tab。

### 4. 为何能看到不同目录下的视频

列表来自全局 SQLite 索引，与当前选择的保存目录无关。

### 5. 没有单独的「单条上传」API

Web 端通过 `POST /api/weixin/upload/batch` 传入单个 `video_paths` 即可；Python 可直接调用 `Uploader.upload_video()`。
