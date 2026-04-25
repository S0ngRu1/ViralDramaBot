# 抖音视频解析与下载工具

## 📚 文档目录

1. [项目概览](#项目概览)
2. [技术架构](#技术架构)
3. [核心模块详解](#核心模块详解)
4. [工作流程](#工作流程)
5. [API 参考](#api-参考)
6. [使用示例](#使用示例)
7. [环境配置](#环境配置)
8. [问题排查](#问题排查)

---

## 项目概览

### 项目目标

这是一个专门针对抖音（Douyin）视频的解析和下载工具，提供以下核心功能：

1. **视频链接解析** - 自动识别并解析抖音分享链接
2. **无水印下载** - 获取无水印版本的视频下载链接
3. **视频下载** - 直接下载视频文件到本地
4. **进度显示** - 实时显示下载进度

### 主要特点

- ✅ **零配置使用** - 开箱即用，默认工作目录自动创建
- ✅ **智能重定向** - 自动跟随 HTTP 重定向获取真实 URL
- ✅ **无水印转换** - 自动将有水印链接转换为无水印链接
- ✅ **断点续传支持** - 使用流式下载，支持大文件
- ✅ **错误重试** - 内置重试机制处理网络异常
- ✅ **详细日志** - 完整的操作日志便于调试

### 项目结构

```
douyin-python-implementation/
├── logger.py                    # 日志模块
├── config.py                    # 配置管理
├── douyin_processor.py          # 核心处理器
├── tools.py                     # 工具函数接口
├── main.py                      # 命令行入口
├── requirements.txt             # 依赖列表
└── README.md                    # 项目说明
```

---

## 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户界面层                              │
│  命令行工具 (main.py) | 脚本调用 | 交互式菜单              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   工具函数层 (tools.py)                      │
│  get_douyin_download_link()                                 │
│  download_douyin_video()                                    │
│  parse_douyin_video_info()                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              核心处理器层 (douyin_processor.py)             │
│  DouyinProcessor                                            │
│  ├── parse_share_url()      # 解析分享链接                 │
│  ├── download_video()        # 下载视频                     │
│  └── 内部工具方法            # 重定向、HTML解析、进度      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              基础设施层                                      │
│  配置层 (config.py) | 日志层 (logger.py)                   │
│  环境变量 | 工作目录 | 文件管理                             │
└─────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              外部依赖                                        │
│  requests | urllib3 | 标准库 (re, os, sys, pathlib)        │
└─────────────────────────────────────────────────────────────┘
```

### 分层设计说明

| 层级 | 职责 | 主要组件 |
|------|------|---------|
| **用户界面层** | 提供交互接口 | CLI、交互菜单、脚本调用 |
| **工具函数层** | 提供高级 API | 三个主要工具函数 |
| **核心处理器层** | 业务逻辑实现 | DouyinProcessor 类 |
| **基础设施层** | 公共服务 | 配置、日志、文件管理 |
| **外部依赖** | 第三方库 | requests、urllib3 等 |

---

## 核心模块详解

### 1. logger.py - 日志系统

**功能**: 提供统一的日志输出，支持多个日志级别。

#### 日志级别

```python
DEBUG   # 调试信息（仅在 DEBUG 环境变量设置时输出）
INFO    # 一般信息
WARN    # 警告信息
ERROR   # 错误信息
```

#### 日志格式

```
[2024-01-15T10:30:45.123456] [INFO] 消息内容 [上下文]
 └─ 时间戳                    └─ 级别    └─ 消息    └─ 可选上下文
```

#### Logger 类

```python
class Logger:
    def __init__(self, debug_mode: bool = False)
    def info(self, message: str, context: Optional[Any] = None)
    def warn(self, message: str, context: Optional[Any] = None)
    def error(self, message: str, context: Optional[Any] = None)
    def debug(self, message: str, context: Optional[Any] = None)
```

**使用示例**:

```python
from logger import logger

logger.info("应用启动")
logger.warn("内存不足")
logger.error("连接失败", context={"url": "https://..."})
logger.debug("调试信息", context={"request_id": "123"})
```

---

### 2. config.py - 配置管理

**功能**: 管理全局配置，包括工作目录初始化和文件路径管理。

#### Config 类

```python
class Config:
    DEFAULT_WORK_DIR = '.data'          # 默认工作目录
    
    def __init__(self)
    def validate_environment(self) -> bool
    def initialize_work_dir(self) -> bool
    def get_video_path(self, video_id: str) -> Path
    def get_temp_path(self, filename: str) -> Path
```

#### 工作目录初始化流程

```
1. 读取环境变量 WORK_DIR
   ↓
2. 如果未设置，使用默认值 '.data'
   ↓
3. 创建目录（递归创建）
   ↓
4. 测试写入权限
   ↓
5. 初始化成功 ✅
```

**环境变量配置**:

```bash
# 使用自定义工作目录
export WORK_DIR="/path/to/your/data/directory"

# 启用调试模式
export DEBUG=1
```

**文件路径管理**:

```python
from config import config

# 获取视频文件路径
video_path = config.get_video_path("7374567890123456789")
# 输出: .data/7374567890123456789.mp4

# 获取临时文件路径
temp_path = config.get_temp_path("temp_file.tmp")
# 输出: .data/temp_file.tmp
```

---

### 3. douyin_processor.py - 核心处理器

**功能**: 实现抖音视频解析和下载的核心逻辑。

#### 核心数据结构

**DouyinVideoInfo** - 视频信息

```python
@dataclass
class DouyinVideoInfo:
    url: str                          # 无水印视频下载链接
    title: str                        # 视频标题
    video_id: str                     # 视频 ID
    description: Optional[str] = None # 视频描述（可选）
```

**DownloadProgress** - 下载进度

```python
@dataclass
class DownloadProgress:
    downloaded: int   # 已下载字节数
    total: int        # 总字节数
    percentage: float # 下载百分比
```

#### DouyinProcessor 类

```python
class DouyinProcessor:
    def __init__(self, timeout: int = 10, max_retries: int = 3)
    def parse_share_url(self, share_text: str) -> DouyinVideoInfo
    def download_video(
        self, 
        video_info: DouyinVideoInfo,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None
    ) -> str
```

#### 关键方法详解

##### parse_share_url - 解析分享链接

**功能**: 完整的视频信息解析流程

**工作流程**:

```
输入: 分享文本
  ↓
步骤1: URL 提取 - 使用正则表达式从文本中提取 URL
  ↓
  Pattern: r'https?://[^\s]+'
  Example: "抖音链接: https://v.douyin.com/xxxxx" → "https://v.douyin.com/xxxxx"
  ↓
步骤2: 获取重定向 URL - 跟随 HTTP 重定向
  ↓
  抖音短链接
    ↓ (301/302)
  中间链接
    ↓ (可能还有重定向)
  真实 URL
  ↓
步骤3: 提取视频 ID
  ↓
  Pattern: r'/video/(\d+)'
  URL: "https://www.douyin.com/video/7374567890123456789" 
  Result: "7374567890123456789"
  ↓
步骤4: 获取视频页面
  ↓
  URL: "https://www.iesdouyin.com/share/video/{video_id}"
  Method: GET
  Headers: User-Agent (模拟 iPhone)
  ↓
步骤5: 从 HTML 提取视频信息
  ↓
  5.1 提取视频 URL
      Pattern: r'"play_addr"[^}]*"url_list"[^[]*\[\s*"([^"]+)"'
      转换: playwm → play (有水印 → 无水印)
  ↓
  5.2 提取视频标题
      Pattern: r'"desc"\s*:\s*"([^"]*)"'
      Fallback: <title> 标签
      清理: 移除非法文件名字符
  ↓
输出: DouyinVideoInfo 对象
```

**代码示例**:

```python
from douyin_processor import DouyinProcessor

processor = DouyinProcessor()

# 解析分享链接
video_info = processor.parse_share_url(
    "分享链接: https://v.douyin.com/xxxxx"
)

print(f"视频ID: {video_info.video_id}")
print(f"标题: {video_info.title}")
print(f"下载链接: {video_info.url}")
```

##### download_video - 下载视频

**功能**: 实现流式下载，支持进度回调

**下载流程**:

```
输入: 视频信息 + 进度回调
  ↓
步骤1: 准备
  ├─ 确定输出文件名: {video_id}.mp4
  ├─ 确定输出路径: {WORK_DIR}/{video_id}.mp4
  └─ 日志记录
  ↓
步骤2: 发起 HTTP GET 请求
  ├─ URL: video_info.url
  ├─ Headers: User-Agent (模拟 iPhone)
  ├─ 流模式: stream=True (关键！)
  └─ 超时: 10 秒
  ↓
步骤3: 获取文件大小
  └─ 从 Content-Length 响应头读取
  ↓
步骤4: 流式读取并写入
  ┌─ 循环处理每个数据块
  │
  ├─ 读取 8KB 数据块
  ├─ 写入到本地文件
  ├─ 更新已下载字节数
  ├─ 计算进度百分比
  ├─ 调用进度回调函数
  └─ 显示进度条到控制台
  ↓
步骤5: 完成
  ├─ 关闭文件流
  ├─ 检查文件完整性
  └─ 返回文件路径

异常处理:
  如果下载失败 → 删除不完整的文件
```

**代码示例**:

```python
from douyin_processor import DouyinProcessor, DownloadProgress

processor = DouyinProcessor()
video_info = processor.parse_share_url("https://v.douyin.com/xxxxx")

def progress_callback(progress: DownloadProgress) -> None:
    """进度回调函数"""
    percentage = progress.percentage
    downloaded_mb = progress.downloaded / (1024 * 1024)
    total_mb = progress.total / (1024 * 1024)
    print(f"下载进度: {percentage:.1f}% ({downloaded_mb:.1f}MB/{total_mb:.1f}MB)")

# 下载视频
file_path = processor.download_video(
    video_info,
    on_progress=progress_callback
)

print(f"文件已保存: {file_path}")
```

#### 内部工具方法

**_extract_url_from_text** - URL 提取

```python
def _extract_url_from_text(self, text: str) -> Optional[str]:
    """从文本中提取 URL"""
    # 使用正则表达式: https?://[^\s]+
    # 返回第一个匹配的 URL
```

**_get_redirect_url** - 获取重定向后的 URL

```python
def _get_redirect_url(self, share_url: str) -> str:
    """跟随重定向获取真实 URL"""
    # 自动跟随 HTTP 重定向
    # 最多跟随 5 次
    # 返回最终 URL
```

**_extract_video_id_from_url** - 提取视频 ID

```python
def _extract_video_id_from_url(self, url: str) -> Optional[str]:
    """从 URL 中提取视频 ID"""
    # 正则表达式: /video/(\d+)
    # 返回纯数字的视频 ID
```

**_fetch_video_page** - 获取视频页面

```python
def _fetch_video_page(self, video_id: str) -> str:
    """获取视频页面 HTML"""
    # 访问 iesdouyin.com
    # 模拟 iPhone 用户代理
    # 返回 HTML 内容
```

**_extract_video_info_from_html** - 从 HTML 提取信息

```python
def _extract_video_info_from_html(
    self, 
    html: str, 
    video_id: str
) -> DouyinVideoInfo:
    """从 HTML 提取视频信息"""
    # 1. 使用正则表达式提取视频 URL
    # 2. 转换为无水印 URL (playwm → play)
    # 3. 提取视频标题
    # 4. 清理文件名非法字符
    # 5. 返回视频信息对象
```

**_format_bytes** - 格式化字节大小

```python
@staticmethod
def _format_bytes(bytes_size: int) -> str:
    """格式化字节大小为可读字符串"""
    # 1024 B → 1.0 KB
    # 1048576 B → 1.0 MB
    # 1073741824 B → 1.0 GB
```

**_create_progress_bar** - 创建进度条

```python
@staticmethod
def _create_progress_bar(percentage: float, length: int = 20) -> str:
    """创建简单的进度条"""
    # 0% → "▯▯▯▯▯▯▯▯▯▯"
    # 50% → "█████▯▯▯▯▯"
    # 100% → "██████████"
```

**_generate_video_id** - 生成随机 ID

```python
@staticmethod
def _generate_video_id() -> str:
    """生成随机视频 ID"""
    # 格式: douyin_{timestamp}_{random}
    # 示例: douyin_1705324245123_45678
```

---

### 4. tools.py - 工具函数

**功能**: 提供高级工具函数接口，包装 DouyinProcessor。

#### DouyinTools 类

```python
class DouyinTools:
    def __init__(self)
    def get_douyin_download_link(self, share_link: str) -> Dict[str, Any]
    def download_douyin_video(
        self, 
        share_link: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]
    def parse_douyin_video_info(self, share_link: str) -> Dict[str, Any]
```

#### 返回结果格式

所有函数返回统一的字典格式：

```python
{
    "status": "success" | "error",      # 状态
    "message": "相关信息",               # 消息
    "video_id": "视频ID",               # 视频ID (成功时)
    "title": "视频标题",                 # 标题 (成功时)
    "download_url": "下载链接",         # 下载链接 (成功时)
    "file_path": "文件路径",            # 文件路径 (下载成功时)
}
```

#### 公共函数接口

```python
def get_douyin_download_link(share_link: str) -> Dict[str, Any]
def download_douyin_video(
    share_link: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]
def parse_douyin_video_info(share_link: str) -> Dict[str, Any]
```

**使用示例**:

```python
from tools import get_douyin_download_link, download_douyin_video

# 获取下载链接
result = get_douyin_download_link("https://v.douyin.com/xxxxx")
if result['status'] == 'success':
    print(f"下载链接: {result['download_url']}")

# 下载视频
def on_progress(progress):
    print(f"进度: {progress['percentage']:.1f}%")

result = download_douyin_video(
    "https://v.douyin.com/xxxxx",
    on_progress=on_progress
)
if result['status'] == 'success':
    print(f"文件已保存: {result['file_path']}")
```

---

### 5. main.py - 命令行入口

**功能**: 提供命令行接口和交互式菜单。

#### 支持的命令

```bash
# 获取下载链接
python main.py get-link "https://v.douyin.com/xxxxx"

# 下载视频
python main.py download "https://v.douyin.com/xxxxx"

# 解析视频信息
python main.py parse "https://v.douyin.com/xxxxx"

# 交互式菜单
python main.py interactive

# 显示帮助
python main.py -h
```

#### 交互式菜单

启动交互式菜单后，您可以选择以下操作：

```
1. 获取无水印下载链接
2. 下载视频文件
3. 解析视频信息
4. 退出
```

---

## 工作流程

### 完整解析流程

```
用户输入分享链接
    ↓
┌────────────────────────────────────────────────┐
│ 1. URL 提取                                     │
│    - 正则表达式: r'https?://[^\s]+'           │
│    - 提取第一个 URL                            │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 2. 跟随重定向                                   │
│    - 短链接 (v.douyin.com)                     │
│      ↓ 301/302 重定向                          │
│    - 真实 URL (www.douyin.com/video/...)      │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 3. 提取视频 ID                                  │
│    - 从 URL 中正则提取: /video/(\d+)          │
│    - 或生成随机 ID                             │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 4. 获取视频页面                                 │
│    - URL: iesdouyin.com/share/video/{id}      │
│    - Headers: User-Agent (模拟 iPhone)        │
│    - 获取 HTML 内容                            │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 5. 解析 HTML 提取视频信息                       │
│    - 视频 URL (在 play_addr.url_list)        │
│    - 视频标题 (在 desc 字段)                   │
│    - 清理文件名非法字符                        │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 6. 无水印转换                                   │
│    - playwm → play                            │
│    - 获取无水印下载链接                        │
└────────────────────────────────────────────────┘
    ↓
返回 DouyinVideoInfo 对象
{
  url: "无水印下载链接",
  title: "视频标题",
  video_id: "视频ID"
}
```

### 完整下载流程

```
用户调用下载函数
    ↓
┌────────────────────────────────────────────────┐
│ 1. 解析分享链接 (见上面的解析流程)              │
│    → 获得 DouyinVideoInfo 对象                │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 2. 发起 HTTP GET 请求                          │
│    - URL: video_info.url                      │
│    - 流模式: stream=True                      │
│    - Headers: User-Agent                      │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 3. 获取文件大小                                 │
│    - Content-Length 响应头                    │
│    - 用于计算进度百分比                        │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 4. 流式下载 (循环处理)                          │
│    每个数据块:                                  │
│    ├─ 读取 8KB 数据                            │
│    ├─ 写入本地文件                             │
│    ├─ 更新已下载字节数                         │
│    ├─ 计算进度百分比                           │
│    ├─ 调用进度回调函数                         │
│    └─ 显示进度条                               │
└────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────┐
│ 5. 完成                                        │
│    - 关闭文件流                                 │
│    - 验证文件完整性                            │
│    - 返回文件路径                              │
└────────────────────────────────────────────────┘
    ↓
返回完整文件路径
```

### 错误处理流程

```
执行操作
    ↓
是否发生异常?
    ├─ 否 → 返回成功结果
    │
    └─ 是 → 进入错误处理流程
        ├─ 记录错误日志 (logger.error)
        ├─ 如果是下载失败:
        │   └─ 清理不完整的文件
        ├─ 返回错误结果
        └─ 允许调用者重试
```

---

## API 参考

### tools.py API

#### get_douyin_download_link

获取抖音无水印下载链接

```python
def get_douyin_download_link(share_link: str) -> Dict[str, Any]
```

**参数**:
- `share_link` (str): 抖音分享链接或包含链接的文本

**返回**:
```python
{
    "status": "success" | "error",
    "message": "操作结果消息",
    "video_id": "视频ID",          # 成功时
    "title": "视频标题",            # 成功时
    "download_url": "下载链接",    # 成功时
}
```

**异常**:
- ValueError: 未找到有效的分享链接
- requests.RequestException: 网络请求失败

**示例**:

```python
from tools import get_douyin_download_link

result = get_douyin_download_link("分享链接: https://v.douyin.com/xxxxx")
print(result)
# 输出:
# {
#     'status': 'success',
#     'message': '✅ 成功获取视频下载链接',
#     'video_id': '7374567890123456789',
#     'title': '视频标题',
#     'download_url': 'https://...',
#     ...
# }
```

---

#### download_douyin_video

下载抖音视频文件

```python
def download_douyin_video(
    share_link: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]
```

**参数**:
- `share_link` (str): 抖音分享链接或包含链接的文本
- `on_progress` (Callable, optional): 进度回调函数

**进度回调格式**:
```python
{
    "downloaded": 1048576,          # 已下载字节数
    "total": 10485760,              # 总字节数
    "percentage": 10.0              # 百分比
}
```

**返回**:
```python
{
    "status": "success" | "error",
    "message": "操作结果消息",
    "video_id": "视频ID",          # 成功时
    "title": "视频标题",            # 成功时
    "file_path": "保存路径",        # 成功时
}
```

**示例**:

```python
from tools import download_douyin_video

def progress_callback(progress):
    percentage = progress['percentage']
    print(f"下载进度: {percentage:.1f}%")

result = download_douyin_video(
    "https://v.douyin.com/xxxxx",
    on_progress=progress_callback
)

if result['status'] == 'success':
    print(f"文件已保存: {result['file_path']}")
```

---

#### parse_douyin_video_info

解析抖音视频信息

```python
def parse_douyin_video_info(share_link: str) -> Dict[str, Any]
```

**参数**:
- `share_link` (str): 抖音分享链接或包含链接的文本

**返回**:
```python
{
    "status": "success" | "error",
    "message": "操作结果消息",
    "video_id": "视频ID",          # 成功时
    "title": "视频标题",            # 成功时
    "download_url": "下载链接",    # 成功时
}
```

**示例**:

```python
from tools import parse_douyin_video_info

result = parse_douyin_video_info("https://v.douyin.com/xxxxx")
print(f"视频ID: {result['video_id']}")
print(f"标题: {result['title']}")
print(f"下载链接: {result['download_url']}")
```

---

### DouyinProcessor API

#### parse_share_url

```python
def parse_share_url(self, share_text: str) -> DouyinVideoInfo
```

**参数**:
- `share_text` (str): 分享文本（可包含链接）

**返回**:
- `DouyinVideoInfo`: 包含 url、title、video_id 的数据类对象

**异常**:
- ValueError: 未找到有效链接或解析失败

---

#### download_video

```python
def download_video(
    self, 
    video_info: DouyinVideoInfo,
    on_progress: Optional[Callable[[DownloadProgress], None]] = None
) -> str
```

**参数**:
- `video_info` (DouyinVideoInfo): 视频信息对象
- `on_progress` (Callable, optional): 进度回调函数

**进度回调格式**:
```python
DownloadProgress(
    downloaded=1048576,          # 已下载字节数
    total=10485760,              # 总字节数
    percentage=10.0              # 百分比
)
```

**返回**:
- str: 保存的文件完整路径

---

## 使用示例

### 示例 1: 基础使用 - 获取下载链接

```python
from tools import get_douyin_download_link

# 获取下载链接
result = get_douyin_download_link("https://v.douyin.com/xxxxx")

if result['status'] == 'success':
    print(f"✅ 成功")
    print(f"视频ID: {result['video_id']}")
    print(f"标题: {result['title']}")
    print(f"下载链接: {result['download_url']}")
else:
    print(f"❌ 失败: {result['message']}")
```

**输出**:
```
✅ 成功
视频ID: 7374567890123456789
标题: 抖音视频标题
下载链接: https://...
```

---

### 示例 2: 下载视频 - 带进度显示

```python
from tools import download_douyin_video

def show_progress(progress):
    """显示下载进度"""
    percentage = progress['percentage']
    downloaded = progress['downloaded'] / (1024 * 1024)
    total = progress['total'] / (1024 * 1024)
    print(f"\r下载进度: {percentage:.1f}% ({downloaded:.1f}MB/{total:.1f}MB)", end='')

# 下载视频
result = download_douyin_video(
    "https://v.douyin.com/xxxxx",
    on_progress=show_progress
)

print()  # 换行

if result['status'] == 'success':
    print(f"✅ 下载完成: {result['file_path']}")
else:
    print(f"❌ 下载失败: {result['message']}")
```

**输出**:
```
下载进度: 45.3% (4.53MB/10.00MB)
✅ 下载完成: .data/7374567890123456789.mp4
```

---

### 示例 3: 使用 DouyinProcessor 类

```python
from douyin_processor import DouyinProcessor, DownloadProgress

# 创建处理器实例
processor = DouyinProcessor(timeout=15, max_retries=3)

# 解析分享链接
try:
    video_info = processor.parse_share_url("https://v.douyin.com/xxxxx")
    print(f"视频信息: {video_info}")
except Exception as e:
    print(f"解析失败: {e}")
    exit(1)

# 下载视频
def on_progress(progress: DownloadProgress):
    """进度回调"""
    bar_length = 30
    filled = int(bar_length * progress.percentage / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r[{bar}] {progress.percentage:.1f}%", end='')

try:
    file_path = processor.download_video(
        video_info,
        on_progress=on_progress
    )
    print(f"\n✅ 文件已保存: {file_path}")
except Exception as e:
    print(f"\n❌ 下载失败: {e}")
```

---

### 示例 4: 批量下载多个视频

```python
from tools import download_douyin_video

# 分享链接列表
links = [
    "https://v.douyin.com/link1",
    "https://v.douyin.com/link2",
    "https://v.douyin.com/link3",
]

for i, link in enumerate(links, 1):
    print(f"\n[{i}/{len(links)}] 正在下载...")
    
    result = download_douyin_video(link)
    
    if result['status'] == 'success':
        print(f"✅ 成功: {result['title']}")
        print(f"   位置: {result['file_path']}")
    else:
        print(f"❌ 失败: {result['message']}")
```

---

### 示例 5: 命令行使用

```bash
# 获取下载链接
python main.py get-link "https://v.douyin.com/xxxxx"

# 下载视频
python main.py download "https://v.douyin.com/xxxxx"

# 解析视频信息
python main.py parse "https://v.douyin.com/xxxxx"

# 交互式菜单
python main.py interactive

# 设置自定义工作目录
WORK_DIR="/data/videos" python main.py download "https://v.douyin.com/xxxxx"

# 启用调试模式
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx"
```

---

## 环境配置

### 依赖安装

```bash
# 创建 requirements.txt
cat > requirements.txt << EOF
requests>=2.28.0
urllib3>=1.26.0
EOF

# 安装依赖
pip install -r requirements.txt
```

### 环境变量

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `WORK_DIR` | 工作目录路径 | `.data` | `/data/videos` |
| `DEBUG` | 启用调试模式 | 未设置 | `1` |

**配置方式**:

```bash
# 方式1: 直接设置
export WORK_DIR="/data/videos"
export DEBUG=1

# 方式2: 命令前设置
WORK_DIR="/data/videos" python main.py download "..."

# 方式3: .env 文件（需要手动加载）
echo "WORK_DIR=/data/videos" > .env
export $(cat .env | xargs)
```

---

## 问题排查

### 常见问题

#### 1. "未找到有效的分享链接"

**原因**: 输入的文本中不包含有效的 URL

**解决方案**:
- ✅ 确保输入包含完整的链接 (http:// 或 https://)
- ✅ 检查链接是否被截断
- ✅ 尝试复制新的分享链接

```python
# ❌ 错误
result = get_douyin_download_link("抖音视频")

# ✅ 正确
result = get_douyin_download_link("https://v.douyin.com/xxxxx")

# ✅ 也正确（包含链接的文本）
result = get_douyin_download_link("分享链接: https://v.douyin.com/xxxxx")
```

---

#### 2. "解析抖音分享链接失败: 连接超时"

**原因**: 网络连接问题或抖音服务器响应缓慢

**解决方案**:
- ✅ 检查网络连接
- ✅ 增加超时时间
- ✅ 稍后重试

```python
from douyin_processor import DouyinProcessor

# 增加超时时间为 20 秒
processor = DouyinProcessor(timeout=20, max_retries=5)

try:
    video_info = processor.parse_share_url("https://v.douyin.com/xxxxx")
except Exception as e:
    print(f"重试或检查网络连接: {e}")
```

---

#### 3. "下载视频失败: 权限拒绝"

**原因**: 没有工作目录的写入权限

**解决方案**:
- ✅ 检查目录权限
- ✅ 更改工作目录位置
- ✅ 运行时使用 sudo（不推荐）

```bash
# 检查权限
ls -ld .data

# 修改权限
chmod 755 .data

# 或使用其他目录
mkdir -p ~/videos
export WORK_DIR="~/videos"
python main.py download "..."
```

---

#### 4. "无法从 HTML 中提取视频 URL，使用备用方法"

**原因**: 网页结构改变或响应内容不完整

**解决方案**:
- ✅ 通常备用方法可以正常工作
- ✅ 如果备用方法也失败，可能是抖音改变了网页结构
- ✅ 启用调试模式查看详细日志

```bash
# 启用调试模式
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx"
```

---

#### 5. 下载文件后打不开

**原因**: 
- 下载过程中中断
- 文件不完整
- 格式问题

**解决方案**:
- ✅ 检查文件大小，应该是 MB 级别的
- ✅ 重新下载
- ✅ 尝试用其他播放器打开

```bash
# 检查文件
ls -lh .data/*.mp4

# 查看文件类型
file .data/7374567890123456789.mp4

# 如果损坏，删除并重新下载
rm .data/7374567890123456789.mp4
```

---

### 调试技巧

#### 启用调试模式

```bash
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx"
```

**调试输出包括**:
- 所有 HTTP 请求的详细信息
- HTML 解析过程中的正则表达式匹配结果
- 下载过程中的字节数统计

#### 自定义日志

```python
from logger import logger

# 启用调试模式
logger.debug("调试信息", context={"key": "value"})
logger.info("一般信息")
logger.warn("警告信息")
logger.error("错误信息", context={"error_code": 500})
```

#### 保存完整的错误日志

```bash
# 将所有输出保存到文件
python main.py download "https://v.douyin.com/xxxxx" 2>&1 | tee debug.log

# 使用 DEBUG 模式和日志
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx" 2>&1 | tee debug.log
```

---

### 性能优化

#### 1. 调整超时和重试

```python
from douyin_processor import DouyinProcessor

# 快速失败（适合网络良好的环境）
processor = DouyinProcessor(timeout=5, max_retries=1)

# 容错性强（适合网络不稳定的环境）
processor = DouyinProcessor(timeout=30, max_retries=5)
```

#### 2. 并发下载多个视频

```python
from concurrent.futures import ThreadPoolExecutor
from tools import download_douyin_video

links = ["https://v.douyin.com/link1", "https://v.douyin.com/link2", ...]

def download_with_index(item):
    index, link = item
    print(f"[{index}] 下载中...")
    return download_douyin_video(link)

# 使用线程池，最多同时 3 个下载
with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(download_with_index, enumerate(links, 1)))

for i, result in enumerate(results, 1):
    if result['status'] == 'success':
        print(f"[{i}] ✅ {result['title']}")
    else:
        print(f"[{i}] ❌ {result['message']}")
```

---

## 项目总结

### 核心特性

| 功能 | 实现方式 | 优势 |
|------|---------|------|
| 链接解析 | 正则表达式 + HTTP 重定向 | 自动处理短链接 |
| 无水印转换 | playwm → play 替换 | 简单高效 |
| 流式下载 | requests stream + 逐块处理 | 内存占用低 |
| 进度显示 | 回调函数 + 计算百分比 | 用户友好 |
| 错误处理 | try-catch + 日志记录 | 容错性强 |

### 技术亮点

✅ **分层架构** - 清晰的模块划分，易于维护和扩展
✅ **重试机制** - 内置 urllib3 Retry，自动处理网络异常
✅ **流式处理** - 支持大文件下载，内存占用恒定
✅ **灵活的 API** - 支持命令行、脚本调用、交互式使用
✅ **详细的日志** - 调试信息完整，便于问题排查

### 扩展方向

- 🔄 支持其他短视频平台 (TikTok、快手等)
- 💾 支持批量下载和任务队列
- 🔗 支持断点续传
- 📊 添加下载统计和管理功能
- 🔐 支持带 Cookie 的认证下载

---

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

