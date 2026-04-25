# ViralDramaBot Web 应用使用指南

## 📱 功能介绍

ViralDramaBot Web 应用提供了一个现代化的用户界面，让你可以轻松管理视频下载和应用设置。

### 主要功能

1. **📥 视频下载**
   - 支持抖音分享链接（短链接和长链接）
   - 一键下载无水印视频
   - 实时显示下载进度
   - 智能重试机制

2. **📺 视频管理**
   - 查看已下载的视频列表
   - 显示视频大小和下载时间
   - 一键删除视频文件

3. **⚙️ 应用设置**
   - 配置视频保存目录
   - 调整下载超时时间
   - 设置重试次数

4. **📊 系统状态**
   - 显示已下载视频统计
   - 应用版本信息

---

## 🚀 快速开始

### Linux / macOS

```bash
# 进入项目目录
cd /home/caisongrui/Workspace/ViralDramaBot

# 安装依赖
pip install -r requirements.txt

# 启动 Web 应用
bash start-web.sh
```

### Windows

```bash
# 进入项目目录
cd C:\Users\YourName\Workspace\ViralDramaBot

# 安装依赖
pip install -r requirements.txt

# 启动 Web 应用
start-web.bat
```

### 手动启动（所有系统）

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python app.py
```

启动后，打开浏览器访问：
- **前端地址**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **API 交互界面**: http://localhost:8000/redoc

---

## 📖 使用教程

### 1️⃣ 下载视频

1. 点击左侧菜单的 **"📥 视频下载"**
2. 在输入框中粘贴抖音分享链接，例如：
   ```
   https://v.douyin.com/7PkMlgCQjjY/
   ```
3. 点击 **"🚀 开始下载"** 按钮
4. 等待下载完成，页面会显示实时进度

### 2️⃣ 管理视频

1. 点击左侧菜单的 **"📺 视频管理"**
2. 查看已下载的视频列表
3. 可以看到每个视频的：
   - 视频 ID
   - 文件标题
   - 文件大小
   - 创建时间
4. 点击 **"🗑️ 删除"** 按钮可以删除视频文件

### 3️⃣ 配置设置

1. 点击左侧菜单的 **"⚙️ 应用设置"**
2. 修改以下配置项：
   - **视频保存目录**: 默认为 `.data`
   - **下载超时时间**: 默认 60 秒（大文件可增加）
   - **最大重试次数**: 默认 3 次
3. 点击 **"💾 保存设置"** 保存配置

---

## ⚙️ API 接口文档

应用提供了完整的 RESTful API，支持多种操作。

### 视频下载

**请求**
```http
POST /api/videos/download
Content-Type: application/json

{
    "link": "https://v.douyin.com/7PkMlgCQjjY/"
}
```

**响应**
```json
{
    "status": "started",
    "message": "视频下载已启动，请稍候...",
    "link": "https://v.douyin.com/7PkMlgCQjjY/"
}
```

### 获取视频列表

**请求**
```http
GET /api/videos
```

**响应**
```json
{
    "status": "success",
    "videos": [
        {
            "video_id": "7374567890123456789",
            "title": "视频标题",
            "file_path": "/path/to/video.mp4",
            "file_size": 216000000,
            "created_at": "1234567890"
        }
    ],
    "total": 1
}
```

### 获取视频详情

**请求**
```http
GET /api/videos/{video_id}
```

### 删除视频

**请求**
```http
DELETE /api/videos/{video_id}
```

### 获取下载进度

**请求**
```http
GET /api/download-progress
```

**响应**
```json
{
    "status": "downloading",
    "percentage": 75.5,
    "downloaded": 163200000,
    "total": 216000000,
    "message": "下载中..."
}
```

### 获取应用设置

**请求**
```http
GET /api/settings
```

### 更新应用设置

**请求**
```http
PUT /api/settings
Content-Type: application/json

{
    "video_dir": ".data",
    "download_timeout": 60,
    "max_retries": 3
}
```

### 获取系统状态

**请求**
```http
GET /api/status
```

**响应**
```json
{
    "status": "success",
    "app_name": "ViralDramaBot",
    "version": "0.1.0",
    "video_count": 5
}
```

---

## 🔧 故障排除

### 问题 1: 无法访问 http://localhost:8000

**原因**：服务器未启动或端口被占用

**解决方案**：
1. 确保应用已成功启动（终端会显示 "Uvicorn running on http://0.0.0.0:8000"）
2. 如果端口被占用，可以修改 `app.py` 中的端口号：
   ```python
   uvicorn.run(
       "app:app",
       host="0.0.0.0",
       port=8001,  # 改为其他端口
       ...
   )
   ```

### 问题 2: 下载时出现超时错误

**原因**：网络不稳定或文件过大

**解决方案**：
1. 进入设置页面
2. 增加 **"下载超时时间"**（例如改为 120 秒）
3. 保存设置后重新下载

### 问题 3: 视频列表为空

**原因**：视频保存目录配置不正确或目录不存在

**解决方案**：
1. 进入设置页面检查 **"视频保存目录"** 是否正确
2. 确保该目录存在且有读写权限
3. 重新下载视频

### 问题 4: 跨域请求错误

**原因**：前端和后端 API 地址不匹配

**解决方案**：
1. 确保在同一个 URL 访问（http://localhost:8000）
2. 不要分别访问 http://localhost:8000 和 API

---

## 🌐 生产环境部署

### 使用 Gunicorn + Nginx

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动应用
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Docker 部署

创建 `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：
```bash
docker build -t viraldramabot .
docker run -p 8000:8000 viraldramabot
```

---

## 📝 常见问题

**Q: 支持同时下载多个视频吗？**
A: 当前版本支持后台下载队列，可以提交多个下载请求。

**Q: 下载的视频在哪里？**
A: 默认保存在项目目录的 `.data` 文件夹中，可以在设置中修改。

**Q: 如何停止应用？**
A: 在终端中按 `Ctrl+C` 即可停止服务。

**Q: 前端可以自定义样式吗？**
A: 可以！修改 `frontend/style.css` 文件即可。

---

## 💡 技术栈

- **后端**: FastAPI + Uvicorn
- **前端**: Vue 3 (CDN 版本)
- **HTTP 客户端**: Axios
- **数据验证**: Pydantic

---

## 📞 获取帮助

遇到问题？查看以下资源：

- FastAPI 文档: https://fastapi.tiangolo.com/
- Vue 3 文档: https://vuejs.org/
- 项目 GitHub: https://github.com/

---

**祝你使用愉快！🎉**
