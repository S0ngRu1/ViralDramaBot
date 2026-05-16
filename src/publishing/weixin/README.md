# 微信视频号发布模块

自动化微信视频号视频发布，支持多账号管理、批量上传、定时发布。

---

## 功能概览

- **多账号管理**：最多 50 个视频号账号，扫码登录，Cookie 持久化
- **批量上传**：多视频入全局串行队列，批内逐个 `upload_video`
- **代理 Profile**：多线路管理、出口 IP 检测、上传时按 Profile 走代理
- **发表位置**：常用地点收藏；支持按代理 IP 反查或手动选点
- **定时发布**：支持 Cron 表达式或间隔分钟
- **剧集关联**：支持关联视频号剧集
- **Cookie 轮询**：每小时检查一次 Cookie 有效性
- **浏览器池**：管理并发浏览器实例，避免资源争抢

---

## 模块结构

```text
src/publishing/weixin/
├── __init__.py
├── config.py                   # 模块配置（浏览器、代理 bypass、冷却时间）
├── schemas.py                  # Pydantic 请求/响应模型
├── dao.py                      # SQLite（账号、任务、计划、代理、常用位置）
├── account_manager.py          # 登录、Cookie、轮询、打开作品列表
├── browser.py                  # DrissionPage 浏览器池
├── uploader.py                 # 上传全流程
├── scheduler.py                # APScheduler 定时计划
├── metadata.py                 # 标题/描述/标签解析
├── proxy.py                    # 代理连通性与出口 IP
├── geocoding.py                # IP 归属地
└── batch_queue.py              # 多批 upload/batch 的全局串行队列
```

---

## 核心流程

### 1. 账号登录流程

```text
创建账号
  ↓
启动浏览器（DrissionPage + Edge）
  ↓
打开视频号登录页
  ↓
显示二维码，等待用户扫码（120 秒超时）
  ↓
检测登录状态（URL 跳转 / Cookie 关键字段）
  ↓
保存 Cookie 到 JSON 文件
  ↓
更新账号状态为 active
```

### 2. 视频上传流程

```text
验证账号状态（必须为 active）
  ↓
验证视频文件（存在性、格式、大小）
  ↓
解析元数据（手动/文件名/AI）
  ↓
获取浏览器实例，加载 Cookie
  ↓
导航到发布页面（/platform/post/create）
  ↓
注入视频文件到 input[type=file]
  ↓
等待视频上传和处理完成（检测描述框出现）
  ↓
填写描述（含标签）→ 填写短标题
  ↓
关联剧集（可选）
  ↓
设置定时发布时间（可选）
  ↓
点击发表按钮（等待按钮可用）
  ↓
确认发表，等待跳转到作品列表页
  ↓
保存更新后的 Cookie
  ↓
更新任务状态为 completed
```

### 3. 定时发布流程

```text
创建定时计划（Cron / 间隔分钟）
  ↓
APScheduler 注册触发器
  ↓
触发时执行：
  ├─ 获取当前索引的视频
  ├─ 创建上传任务
  ├─ 执行上传
  ├─ 成功后索引 +1
  └─ 全部完成后停用计划
```

---

## 配置说明

### 环境变量

```bash
# 浏览器路径（默认 Edge）
set BROWSER_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# 最大并发上传数（默认 1，建议保持串行）
set WEIXIN_MAX_CONCURRENT_UPLOADS="1"

# 连续上传间隔秒数（config.py 环境变量默认 45；全局设置页默认 20，lifespan 会覆盖）
set WEIXIN_INTER_UPLOAD_COOLDOWN_SEC="45"

# 代理（与 src/core/config.py 对齐）
set WEIXIN_PROXY_ENABLED="true"
set WEIXIN_PROXY_SCHEME="http"
set WEIXIN_PROXY_HOST="127.0.0.1"
set WEIXIN_PROXY_PORT="0"
set WEIXIN_LOCATION_MODE="proxy_ip"
```

### 配置项（config.py）

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `BROWSER_PATH` | Edge 路径 | 浏览器可执行文件路径 |
| `MAX_BROWSER_INSTANCES` | 3 | 最大浏览器实例数 |
| `BROWSER_HEADLESS` | False | 是否无头模式（扫码需关闭） |
| `PAGE_LOAD_TIMEOUT` | 30 | 页面加载超时（秒） |
| `UPLOAD_TIMEOUT` | 600 | 上传超时（秒，运行时由全局配置覆盖） |
| `INTER_UPLOAD_COOLDOWN_SEC` | 45 | 批内连续上传间隔（秒） |
| `MAX_CONCURRENT_UPLOADS` | 1 | 最大并发上传数 |
| `MAX_RETRIES` | 3 | 最大重试次数 |
| `MAX_ACCOUNTS` | 50 | 最大账号数 |
| `UPLOAD_BYPASS_HOSTS` | 见源码 | 上传 CDN 不走代理的域名 |
| `PROXY_ENABLED` 等 | 见源码 | 与全局 `weixin_proxy_*` 同步 |
| `SUPPORTED_VIDEO_FORMATS` | mp4, mov, avi, mkv, flv, wmv | 支持的视频格式 |
| `MAX_VIDEO_SIZE_MB` | 2048 | 最大视频大小（MB） |

---

## 数据模型

### 账号状态（AccountStatus）

| 状态 | 说明 |
|---|---|
| `active` | 登录有效 |
| `expired` | 登录过期 |
| `logging_in` | 正在登录（等待扫码） |
| `error` | 异常 |

### 任务状态（TaskStatus）

| 状态 | 说明 |
|---|---|
| `pending` | 等待中 |
| `uploading` | 上传中 |
| `processing` | 视频处理中 |
| `filling` | 填写信息中 |
| `publishing` | 发布中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |

### 元数据来源（MetadataSource）

| 来源 | 说明 |
|---|---|
| `manual` | 手动填写 |
| `filename` | 从文件名读取 |
| `ai` | AI 自动生成 |

---

## API 接口

Web 上传入口仅为 **`POST /api/weixin/upload/batch`**（可只传一个视频路径）。单条上传请直接调用 `Uploader.upload_video()` 或 batch 传长度为 1 的 `video_paths`。

### 代理与常用位置

```
GET    /api/weixin/proxy/test
GET    /api/weixin/proxy-profiles
POST   /api/weixin/proxy-profiles
PUT    /api/weixin/proxy-profiles/{profile_id}
DELETE /api/weixin/proxy-profiles/{profile_id}
POST   /api/weixin/proxy-profiles/{profile_id}/check
POST   /api/weixin/proxy-profiles/check-all
GET    /api/weixin/favorite-locations
POST   /api/weixin/favorite-locations
DELETE /api/weixin/favorite-locations/{location_id}
```

### 账号管理

```
POST   /api/weixin/accounts
GET    /api/weixin/accounts
DELETE /api/weixin/accounts/{account_id}
POST   /api/weixin/accounts/{account_id}/login
POST   /api/weixin/accounts/{account_id}/refresh
POST   /api/weixin/accounts/{account_id}/open-post-list
POST   /api/weixin/accounts/check-cookies
GET    /api/weixin/accounts/refresh-status
POST   /api/weixin/accounts/refresh-all
```

### 上传任务

```
POST   /api/weixin/upload/batch           # 创建任务并入全局队列
GET    /api/weixin/upload/batch/queue     # 队列快照
GET    /api/weixin/tasks                  # 可选 account_id、status
DELETE /api/weixin/tasks/{task_id}
POST   /api/weixin/tasks/batch-delete
POST   /api/weixin/tasks/{task_id}/retry
```

### 定时计划

```
POST   /api/weixin/schedule
GET    /api/weixin/schedule
DELETE /api/weixin/schedule/{schedule_id}
```

---

## 使用示例

### Python 调用

```python
from src.publishing.weixin.dao import WeixinDAO
from src.publishing.weixin.account_manager import AccountManager
from src.publishing.weixin.uploader import Uploader

# 初始化
dao = WeixinDAO()
account_manager = AccountManager(dao)
uploader = Uploader(dao)

# 1. 创建账号
account = account_manager.create_account("我的视频号")
account_id = account["id"]

# 2. 扫码登录
result = account_manager.login_with_qrcode(account_id)
print(result)  # {"status": "success", "message": "登录成功"}

# 3. 上传视频
task_id = dao.create_task(
    account_id=account_id,
    video_path=r"C:\videos\test.mp4",
    title="测试视频",
    description="这是一个测试视频",
    tags=["测试", "短剧"]
)

result = uploader.upload_video(
    task_id=task_id,
    account_id=account_id,
    video_path=r"C:\videos\test.mp4",
    title="测试视频",
    description="这是一个测试视频",
    tags=["测试", "短剧"],
    drama_link="我的短剧"  # 可选，关联剧集
)
print(result)  # {"status": "success", "message": "上传成功"}

# 4. 批量上传
task_ids = []
video_paths = [
    r"C:\videos\ep01.mp4",
    r"C:\videos\ep02.mp4",
    r"C:\videos\ep03.mp4",
]
for path in video_paths:
    tid = dao.create_task(
        account_id=account_id,
        video_path=path,
        tags=["短剧", "连载"]
    )
    task_ids.append(tid)

for tid in task_ids:
    task = dao.get_task(tid)
    result = uploader.upload_video(
        task_id=tid,
        account_id=account_id,
        video_path=task["video_path"],
        tags=["短剧", "连载"]
    )
    print(f"任务 #{tid}: {result}")
```

### cURL 调用

```bash
# 创建账号
curl -X POST http://localhost:8000/api/weixin/accounts \
  -H "Content-Type: application/json" \
  -d '{"name": "我的视频号"}'

# 扫码登录
curl -X POST http://localhost:8000/api/weixin/accounts/1/login

# 批量上传（单条时 video_paths 长度为 1）
curl -X POST http://localhost:8000/api/weixin/upload/batch \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 1,
    "video_paths": ["C:\\videos\\test.mp4"],
    "titles": ["测试视频"],
    "metadata_source": "manual",
    "proxy_profile_id": 1,
    "location_label": "深圳人民公园"
  }'
```

---

## 数据存储

### 数据库

位置：`.data/weixin/weixin.db`

- `accounts` — 账号
- `upload_tasks` — 上传任务（含 `proxy_profile_id`、`location_label`、`proxy_ip` 等审计字段）
- `proxy_profiles` — 代理线路
- `favorite_locations` — 常用发表位置名称
- `schedules` — 定时计划

### Cookie 文件

位置：`.data/weixin/cookies/`

- `<账号名>_<时间>.json` - 账号 Cookie
- `profile_<hash>/` - 浏览器用户数据目录
- `viewer/account_<id>/` - 视频管理页浏览器数据

---

## 注意事项

1. **浏览器要求**：需要安装 Microsoft Edge 浏览器
2. **扫码登录**：必须在有桌面环境的机器上运行（需要弹出浏览器窗口）
3. **并发限制**：`MAX_CONCURRENT_UPLOADS` 默认 1；多批请求由 `batch_queue` 串行
4. **风控策略**：批内成功后按 `INTER_UPLOAD_COOLDOWN_SEC` 等待（环境变量默认 45 秒，设置页可改）；模拟人类操作延迟 0.5–2 秒
5. **代理**：页面请求走代理，视频 CDN（`*.video.qq.com`、`*.wxqcloud.qq.com*` 等）bypass，避免拖慢上传
6. **Cookie 有效期**：后台每 3600 秒检查，过期需重新扫码
7. **视频格式**：mp4, mov, avi, mkv, flv, wmv
8. **视频大小**：最大 2048 MB

---

## 故障排查

### 登录失败

- 检查 Edge 浏览器是否安装
- 检查 `BROWSER_PATH` 配置是否正确
- 确认网络可以访问 `channels.weixin.qq.com`

### 上传失败

- 检查账号状态是否为 `active`
- 检查视频文件是否存在
- 检查视频格式是否支持
- 检查视频大小是否超限
- 查看日志文件：`.data/weixin/logs/`

### Cookie 过期

- 重新调用扫码登录接口
- 检查网络连接
- 确认微信账号未被封禁

### 浏览器冲突

- 确保没有其他程序占用调试端口
- 减少 `MAX_BROWSER_INSTANCES` 配置
- 关闭不必要的浏览器窗口
