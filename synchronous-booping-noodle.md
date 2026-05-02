# 微信视频号自动上传工具 — 技术方案

## Context

当前项目 ViralDramaBot 是一个抖音视频下载 Web 工具，已有 FastAPI + 前端的架构，以及空壳的 `src/publishing/` 模块。用户需要新增一个**微信视频号自动上传**功能，支持多账号管理、批量上传、定时发布。

## 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 浏览器自动化 | **DrissionPage** | 国产库，自带反检测，无需单独下载驱动，中文文档完善，社区中已有视频号自动化实践（用户确认） |
| 数据存储 | **SQLite** | 与现有项目一致，轻量级，存储账号信息、上传任务、定时计划 |
| Web 框架 | **FastAPI** | 复用现有 `app.py`，新增 API 路由 |
| 前端 | **现有 Vue 3 前端** | 新增上传管理页面 |

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Vue 3)                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ 账号管理  │ │ 上传任务  │ │ 定时发布  │ │ 任务日志   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (app.py)                                       │
│  /api/accounts  /api/upload  /api/schedule  /api/logs   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  src/publishing/weixin/                                 │
│  ┌───────────┐ ┌───────────┐ ┌────────────┐            │
│  │ AccountMgr│ │ Uploader  │ │ Scheduler  │            │
│  │ 账号管理   │ │ 上传引擎   │ │ 定时调度    │            │
│  └───────────┘ └───────────┘ └────────────┘            │
│  ┌───────────┐ ┌───────────┐                            │
│  │ Browser   │ │ VideoDAO  │                            │
│  │ 浏览器池   │ │ 数据持久化 │                            │
│  └───────────┘ └───────────┘                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  .data/weixin/                                          │
│  ├─ accounts.db      (账号数据库)                        │
│  ├─ cookies/         (各账号Cookie)                      │
│  ├─ upload_tasks.db  (上传任务队列)                       │
│  └─ logs/            (操作日志)                          │
└─────────────────────────────────────────────────────────┘
```

## 核心模块设计

### 1. 账号管理 (`src/publishing/weixin/account_manager.py`)

- **首次登录**：启动 DrissionPage 浏览器 → 打开视频号创作者中心 → 弹出二维码 → 用户扫码 → 保存 Cookie 和 localStorage 到 `.data/weixin/cookies/{account_id}.json`
- **自动登录**：读取 Cookie → 注入到浏览器 → 验证登录状态 → 若失效则提示重新扫码
- **多账号**：每个账号独立的 Cookie 文件和浏览器配置文件，最多支持 50 个账号
- **数据库表**：`accounts(id, name, wechat_id, status, cookie_path, created_at, last_login_at)`

### 2. 上传引擎 (`src/publishing/weixin/uploader.py`)

核心流程：
```
1. 初始化浏览器（加载账号Cookie）
2. 导航到 https://channels.weixin.qq.com/platform/post/create
3. 点击"上传视频"按钮
4. 选择本地视频文件（通过 send_keys 注入文件路径）
5. 等待视频上传和处理完成（轮询进度条）
6. 填写标题、描述、标签
7. 选择发布时间（立即/定时）
8. 点击发布按钮
9. 确认发布成功
```

关键实现细节：
- **文件上传**：通过 `<input type="file">` 元素的 `send_keys` 方式注入文件路径
- **进度监控**：轮询页面上的上传进度元素，设置合理超时
- **反检测**：DrissionPage 自带反检测 + 随机操作间隔 + 模拟人类输入
- **错误重试**：网络超时、页面加载失败等情况自动重试 3 次

### 3. 元数据来源 (`src/publishing/weixin/metadata.py`)

支持三种元数据获取方式，用户可在上传时选择：
- **手动填写**：在界面中直接输入标题、描述、标签
- **文件名/目录读取**：按约定规则自动提取，如 `标题_描述_标签1,标签2.mp4`
- **AI 自动生成**：调用大模型 API 根据视频内容生成标题和描述（可选配置）

### 4. 定时调度 (`src/publishing/weixin/scheduler.py`)

- 使用 APScheduler 库实现定时任务
- 支持：单次定时、每日定时、自定义 Cron 表达式
- 任务队列：视频按顺序上传，前一个完成后再处理下一个
- 失败重试：失败任务自动加入重试队列，最多重试 3 次
- **数据库表**：`upload_tasks(id, account_id, video_path, title, description, tags, status, scheduled_at, created_at, completed_at, error_msg)`

### 4. 浏览器池管理

- 为了避免同时打开过多浏览器导致资源占用过高，使用浏览器池
- 默认同时最多运行 3 个浏览器实例
- 每个浏览器实例对应一个账号
- 上传完成后自动关闭浏览器释放资源

## 目录结构

```
src/publishing/
├── __init__.py
└── weixin/
    ├── __init__.py
    ├── account_manager.py   # 账号登录、Cookie管理
    ├── uploader.py          # 视频上传核心逻辑
    ├── scheduler.py         # 定时调度
    ├── browser.py           # 浏览器池管理
    ├── dao.py               # 数据库操作
    ├── metadata.py          # 元数据获取（手动/文件名/AI）
    ├── config.py            # 视频号模块配置
    └── schemas.py           # Pydantic 数据模型

frontend/
├── index.html               # 现有主页，新增"视频号上传"导航入口
├── app.js                   # 现有JS，新增视频号相关API调用
├── style.css                # 现有样式，新增上传相关样式
└── weixin.html              # 新增：视频号上传管理页面（集成到现有前端）
```

## 新增依赖

```
DrissionPage>=4.0.0
APScheduler>=3.10.0
# 可选：AI 自动生成元数据
# openai>=1.0.0  或其他大模型SDK
```

## API 设计

### 账号管理
- `POST /api/weixin/accounts` — 创建账号（触发扫码登录）
- `GET /api/weixin/accounts` — 获取账号列表
- `DELETE /api/weixin/accounts/{id}` — 删除账号
- `POST /api/weixin/accounts/{id}/refresh` — 刷新登录状态
- `GET /api/weixin/accounts/{id}/qrcode` — 获取二维码图片（WebSocket推送给前端）

### 上传任务
- `POST /api/weixin/upload` — 创建上传任务
- `POST /api/weixin/upload/batch` — 批量创建上传任务
- `GET /api/weixin/tasks` — 获取任务列表
- `DELETE /api/weixin/tasks/{id}` — 取消任务
- `POST /api/weixin/tasks/{id}/retry` — 重试失败任务

### 定时发布
- `POST /api/weixin/schedule` — 创建定时计划
- `GET /api/weixin/schedule` — 获取定时计划列表
- `DELETE /api/weixin/schedule/{id}` — 删除定时计划

## 实施步骤

### 阶段一：基础设施（2天）
1. 创建 `src/publishing/weixin/` 目录结构
2. 实现数据库模型和 DAO 层
3. 配置 DrissionPage 和浏览器池
4. 实现账号管理模块（扫码登录 + Cookie 持久化）

### 阶段二：核心上传（2天）
5. 实现视频号页面自动化操作（上传、填表单、发布）
6. 实现上传进度监控和错误处理
7. 实现批量上传队列

### 阶段三：定时调度（1天）
8. 集成 APScheduler
9. 实现定时发布逻辑

### 阶段四：Web API 和前端（2天）
10. 在 `app.py` 中新增视频号相关 API 路由
11. 开发前端管理页面（账号管理、上传任务、定时计划）

### 阶段五：测试和优化（1天）
12. 端到端测试
13. 反检测优化和稳定性测试

## 验证方式

1. **账号登录**：扫码后 Cookie 保存成功，重启后自动登录无需扫码
2. **单个上传**：视频成功上传到视频号，标题/描述/标签正确填写
3. **批量上传**：多个视频按顺序依次上传，不冲突
4. **定时发布**：视频在指定时间自动发布
5. **多账号**：不同账号的 Cookie 和任务互不干扰
