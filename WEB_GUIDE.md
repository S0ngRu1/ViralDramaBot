# ViralDramaBot Web 使用指南

## 功能概览

当前 Web 应用包含三个页面：

1. `📥 视频下载`
2. `📺 视频管理`
3. `⚙️ 应用设置`

---

## 启动方式

### 通用方式

```bash
pip install -r requirements.txt
python app.py
```

访问：

- `http://localhost:8000`
- `http://localhost:8000/docs`

### 脚本启动

```bash
start-web.bat
```

---

## 页面说明

### 1. 视频下载

下载页支持：

- 输入抖音短链接或长链接
- 浏览本地目录作为保存路径
- 自动识别视频标题
- 手动修改视频名称
- 实时查看下载进度

视频名称保存规则：

- 非中文、英文、数字字符替换为 `_`
- 按 `_` 切分后只取前两个有效片段
- 最终将两段直接拼接为实际保存名

### 2. 视频管理

视频管理页显示的是 SQLite 索引中的全部视频，而不是当前保存目录下的文件。

支持操作：

- 全选 / 取消全选
- 批量删除
- 单个删除
- 打开视频
- 打开所在文件夹
- 复制完整路径

### 3. 应用设置

支持配置：

- 默认视频保存目录
- 下载超时时间
- 最大重试次数

---

## API 概览

### 下载视频

```http
POST /api/videos/download
Content-Type: application/json
```

请求体：

```json
{
  "link": "https://v.douyin.com/xxxxx/",
  "save_path": ".data",
  "file_name": "视频标题"
}
```

响应：

```json
{
  "status": "started",
  "message": "视频下载任务已启动",
  "link": "https://v.douyin.com/xxxxx/",
  "save_path": "/absolute/path/to/.data",
  "file_name": "视频标题"
}
```

### 解析视频信息

```http
POST /api/videos/parse
Content-Type: application/json
```

请求体：

```json
{
  "link": "https://v.douyin.com/xxxxx/"
}
```

### 获取下载进度

```http
GET /api/download-progress
```

响应示例：

```json
{
  "status": "downloading",
  "percentage": 81.9,
  "downloaded": 10485760,
  "total": 12792627,
  "message": "正在下载视频文件...",
  "file_path": "/absolute/path/to/video.mp4"
}
```

### 浏览本地目录

```http
GET /api/browse-directory
```

### 获取视频列表

```http
GET /api/videos
```

响应示例：

```json
{
  "status": "success",
  "videos": [
    {
      "video_id": "7374567890123456789",
      "title": "视频标题",
      "file_path": "/path/to/video.mp4",
      "file_size": 216000000,
      "created_at": "1234567890",
      "save_dir": "/path/to"
    }
  ],
  "total": 1
}
```

### 获取视频详情

```http
GET /api/videos/{video_id}
```

### 删除单个视频

```http
DELETE /api/videos/{video_id}
```

### 批量删除视频

```http
POST /api/videos/batch-delete
Content-Type: application/json
```

请求体：

```json
{
  "video_ids": ["id1", "id2", "id3"]
}
```

### 打开视频

```http
POST /api/videos/{video_id}/open
```

### 打开视频所在文件夹

```http
POST /api/videos/{video_id}/open-folder
```

### 获取设置

```http
GET /api/settings
```

### 更新设置

```http
PUT /api/settings
Content-Type: application/json
```

请求体：

```json
{
  "video_dir": ".data",
  "download_timeout": 1200,
  "max_retries": 3
}
```

### 获取系统状态

```http
GET /api/status
```

---

## 存储说明

### 视频文件

视频会保存到你在下载页或设置页中选择的目录。

### 视频索引

视频管理页依赖 SQLite 索引：

```text
.data/metadata/video_index.db
```

索引中保存：

- `video_id`
- `title`
- `file_path`
- `file_size`
- `created_at`
- `save_dir`

### 索引修复

后端会在后台定时修复索引，默认每 300 秒清理一次已经不存在的文件记录。

---

## 使用建议

- 下载大文件时，建议保留默认 `download_timeout = 1200`
- “打开文件”与“打开文件夹”依赖本机桌面环境，适合本地运行场景
- 视频管理页只显示已进入 SQLite 索引的内容；当前实现不会主动扫描磁盘历史文件补录

---

## 常见问题

### 1. 视频管理页没有看到某个目录里原来就有的 mp4

当前实现不会自动扫描磁盘已有文件补录索引。视频管理页只显示已经写入 SQLite 索引的视频。

### 2. 下载后怎么看保存位置

下载页进度卡片会显示完整保存路径，视频管理页也会显示完整路径并支持复制。

### 3. 下载完成后为什么不自动跳转到视频管理页

这是当前设计：下载完成后保留在下载页，只刷新视频列表，不自动切页。

### 4. 为什么视频管理页能看到不同目录下的内容

因为列表来自统一的 SQLite 索引，而不是扫描当前保存目录。
