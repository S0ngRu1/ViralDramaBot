# 抖音解析与下载模块

## 模块定位

`src/ingestion/douyin` 是当前项目里真正已经落地的采集模块，负责：

- 解析抖音分享链接
- 获取无水印下载地址
- 下载视频文件
- 回调下载进度

它通过 [app.py](../../../app.py) 接入 Web 应用，也可以单独被 Python 代码调用。

---

## 文件结构

```text
src/ingestion/douyin/
├── __init__.py
├── processor.py
├── downloader.py
└── README.md
```

---

## 主要模块

### `processor.py`

底层执行器，负责实际解析和下载。

核心数据结构：

```python
@dataclass
class DouyinVideoInfo:
    url: str
    title: str
    video_id: str
    description: Optional[str] = None


@dataclass
class DownloadProgress:
    downloaded: int
    total: int
    percentage: float
```

核心方法：

```python
class DouyinProcessor:
    def __init__(self, timeout: int = 10, max_retries: int = 3)
    def update_settings(
        self,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> None
    def parse_share_url(self, share_text: str) -> DouyinVideoInfo
    def download_video(
        self,
        video_info: DouyinVideoInfo,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        file_name: Optional[str] = None
    ) -> str
```

当前实现特点：

- 下载采用流式写入
- `CHUNK_SIZE = 262144`，即 `256KB`
- 下载超时策略是 `(60, max(timeout, 300))`
- 下载失败时会删除不完整文件
- 自定义文件名会在保存前做统一规范化

### `downloader.py`

对上层暴露更稳定的高层接口。

核心方法：

```python
class DouyinDownloader:
    def configure(
        self,
        download_timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> None
    def get_download_link(self, share_link: str) -> Dict[str, Any]
    def download_video(
        self,
        share_link: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]
    def parse_video_info(self, share_link: str) -> Dict[str, Any]
```

统一返回格式：

```python
{
    "status": "success" | "error",
    "message": "操作结果",
    "video_id": "视频ID",
    "title": "视频标题",
    "download_url": "下载链接",
    "file_path": "保存路径"
}
```

---

## 下载流程

### 1. 解析分享链接

```text
输入分享文本
  ↓
提取 URL
  ↓
跟随短链接重定向
  ↓
提取 video_id
  ↓
请求分享页面 HTML
  ↓
提取 desc 与视频播放地址
  ↓
playwm -> play
  ↓
输出 DouyinVideoInfo
```

### 2. 下载视频

```text
接收 DouyinVideoInfo
  ↓
根据 config.get_video_path(...) 生成落盘路径
  ↓
stream=True 发起 GET 请求
  ↓
按 256KB 分块写入
  ↓
持续回调 downloaded / total / percentage
  ↓
下载完成后返回 file_path
```

---

## 文件名规则

下载时如果传入 `file_name`，或者使用自动识别出的标题，都会按统一规则处理：

- 非中文、英文、数字字符替换为 `_`
- 连续 `_` 折叠
- 按 `_` 切分
- 只保留前两个有效片段
- 将这两个片段直接拼接

示例：

- `你好#world###测试` -> `你好world`
- `“短剧”_第01集!!!完整版` -> `短剧第01集`

---

## 与 Web 层的关系

当前 Web 层通过以下接口使用本模块：

- `POST /api/videos/parse` — 解析单条链接
- `POST /api/videos/download` — 单条或批量下载（`link` / `links` / `tasks[]`，`max_concurrent` 1–10，最多 50 条）
- `GET /api/download-progress` — 轮询进度（批量时为聚合进度）

调用路径：

```text
frontend/app.js
  ↓
app.py
  ↓
get_downloader()
  ↓
DouyinDownloader
  ↓
DouyinProcessor
```

下载完成后，`app.py` 会把返回的文件信息写入 SQLite 视频索引：

```text
.data/metadata/video_index.db
```

注意：

- 本模块只负责解析和下载
- 视频管理页的数据并不是由本模块直接维护
- 索引和列表管理逻辑在 `app.py`

---

## Python 调用示例

### 获取下载链接

```python
from src.ingestion.douyin import get_downloader

downloader = get_downloader()
result = downloader.get_download_link("https://v.douyin.com/xxxxx/")
print(result)
```

### 下载视频并显示进度

```python
from src.core import config
from src.ingestion.douyin import get_downloader

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
    file_name="自定义文件名"
)

print(result)
```

### 直接使用底层处理器

```python
from src.ingestion.douyin import DouyinProcessor

processor = DouyinProcessor(timeout=10, max_retries=3)
processor.update_settings(timeout=1200, max_retries=3)

video_info = processor.parse_share_url("https://v.douyin.com/xxxxx/")
file_path = processor.download_video(video_info, file_name="自定义名称")
print(file_path)
```

---

## 运行参数

关键配置来自 [src/core/config.py](../../core/config.py)：

- `WORK_DIR`
- `DOWNLOAD_TIMEOUT`
- `MAX_RETRIES`

默认值：

- `WORK_DIR`：环境变量未设置时为 `~/.viraldramabot_data`；Web 应用启动后通常使用 `app.py` 的 `DATA_DIR`（开发环境为 `.data`）
- `DOWNLOAD_TIMEOUT = 1200`
- `MAX_RETRIES = 3`

---

## 常见问题

### 1. 下载完成后为什么文件名和原始标题不完全一样

因为文件名会按项目规则做规范化处理，以保证路径安全和命名统一。

### 2. 下载速度受什么影响

主要受这些因素影响：

- 源站网络速度
- 本地网络质量
- 下载超时设置
- 远端响应稳定性

当前代码层面已经做了这些优化：

- 流式下载
- 256KB 分块
- requests 重试
- Web 层 SQLite 索引

### 3. 为什么模块本身不负责视频管理页

因为当前职责分层是：

- `processor.py` / `downloader.py` 只负责采集
- `app.py` 负责索引、列表、删除和本地文件操作

这样可以保持采集层更简单，也更容易扩展到其他平台。
