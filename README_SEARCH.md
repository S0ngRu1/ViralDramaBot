# 抖音视频爬虫搜索功能

基于抓取的抖音搜索API请求实现的增强版视频搜索功能。

## 功能特点

1. **完整的API参数支持** - 基于真实抓取的API请求参数
2. **多搜索方法** - 支持官方API、移动端API、网页解析等多种搜索方式
3. **智能筛选** - 可按点赞数、视频时长等条件筛选结果
4. **视频下载** - 支持视频下载到本地
5. **数据导出** - 支持JSON和CSV格式导出
6. **命令行工具** - 提供方便的命令行界面

## 文件结构

```
.
├── dy_video_download/
│   ├── enhanced_search.py      # 增强版搜索功能（基于抓取的API）
│   ├── douyin_search.py        # 基础搜索功能
│   └── test_real_search.py     # 测试脚本
├── example_search.py           # 命令行示例
├── test_enhanced_search.py     # 增强版搜索测试
└── README_SEARCH.md           # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 基本使用

```python
from dy_video_download.enhanced_search import EnhancedDouyinSearch

# 创建搜索器
searcher = EnhancedDouyinSearch()

# 搜索视频
videos = searcher.search_videos(
    keyword="短剧",
    max_results=10,
    min_likes=1000,
    min_duration=10,
    max_duration=180
)

# 显示结果
for video in videos:
    print(f"标题: {video.title[:50]}...")
    print(f"作者: {video.author}")
    print(f"点赞: {video.likes:,}")
    print(f"时长: {video.duration}秒")
    print(f"视频ID: {video.video_id}")
    print()
```

### 3. 使用命令行工具

```bash
# 基本搜索
python example_search.py 短剧

# 带筛选条件的搜索
python example_search.py 短剧 -n 10 --min-likes 1000 --min-duration 10

# 导出结果
python example_search.py 短剧 --export both

# 下载视频
python example_search.py 短剧 --download --download-dir ./videos
```

## 命令行选项

```
用法: python example_search.py <关键词> [选项]

选项:
  -h, --help            显示帮助信息
  -n, --max-results N   最大结果数量 (默认: 10)
  -l, --min-likes N     最小点赞数 (默认: 0)
  --min-duration SEC    最小时长(秒) (默认: 0)
  --max-duration SEC    最大时长(秒) (默认: 0, 表示不限制)
  --export FORMAT       导出格式 (json/csv/both) (默认: json)
  --download            下载视频
  --download-dir DIR    下载目录 (默认: ./downloads)
  --proxy URL          代理URL (如: http://127.0.0.1:7890)
  --verbose            显示详细信息
```

## API请求参数解析

基于抓取的请求，我们实现了以下关键参数：

### 必需参数
- `aid`: 应用ID (6383)
- `device_platform`: 设备平台 (webapp)
- `channel`: 渠道 (channel_pc_web)
- `keyword`: 搜索关键词
- `search_channel`: 搜索渠道 (aweme_general)
- `version_code`: 版本号 (190600)
- `version_name`: 版本名称 (19.6.0)

### 设备信息
- `browser_name`: 浏览器名称 (Firefox)
- `browser_version`: 浏览器版本 (147.0)
- `os_name`: 操作系统 (Ubuntu)
- `screen_width`: 屏幕宽度 (1280)
- `screen_height`: 屏幕高度 (720)
- `cpu_core_num`: CPU核心数 (16)

### 动态参数
- `msToken`: 动态生成的令牌
- `a_bogus`: 签名字符串
- `X-Bogus`: 反爬虫签名
- `uifid`: 用户标识符

### Cookies
关键cookies包括：
- `ttwid`: 抖音唯一标识
- `sessionid`: 会话ID
- `sid_guard`: 会话保护
- `uid_tt`: 用户ID

## 高级功能

### 1. 视频下载

```python
# 下载单个视频
video = videos[0]
filepath = searcher.download_video(video, save_dir="./downloads")
if filepath:
    print(f"下载成功: {filepath}")

# 批量下载
for video in videos[:3]:  # 只下载前3个
    searcher.download_video(video)
    import time
    time.sleep(2)  # 避免请求过快
```

### 2. 数据导出

```python
# 导出为JSON
json_file = searcher.export_results(videos, format="json")
print(f"JSON导出: {json_file}")

# 导出为CSV
csv_file = searcher.export_results(videos, format="csv")
print(f"CSV导出: {csv_file}")
```

### 3. 代理设置

```python
# 使用代理
searcher = EnhancedDouyinSearch(
    use_proxy=True,
    proxy_url="http://127.0.0.1:7890"
)
```

### 4. 获取视频详情

```python
# 通过视频ID获取详情
video_info = searcher.get_video_details("视频ID")
if video_info:
    print(f"视频详情: {video_info.title}")
```

## 常见问题

### Q1: API请求返回错误或空数据
A: 抖音API有严格的反爬虫机制，可能的原因：
1. 缺少正确的签名参数（X-Bogus, a_bogus等）
2. Cookies过期或无效
3. 请求频率过高

解决方案：
- 使用备用搜索方法（网页解析）
- 更新cookies
- 添加请求延迟

### Q2: 视频无法下载
A: 抖音视频有防盗链机制，需要使用第三方解析服务。

解决方案：
- 使用内置的第三方解析服务
- 获取`play_url`直接下载
- 使用其他视频下载工具

### Q3: 搜索结果为空
A: 可能的原因：
1. 关键词没有相关视频
2. 筛选条件太严格
3. 网络或API问题

解决方案：
- 放宽筛选条件
- 尝试不同的关键词
- 检查网络连接

## 调试建议

### 1. 保存调试信息

```python
# 在enhanced_search.py中启用调试
import logging
logging.basicConfig(level=logging.DEBUG)

# 保存API响应用于分析
with open("api_response.json", "w", encoding="utf-8") as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=2)
```

### 2. 检查网络请求

使用浏览器开发者工具：
1. 打开抖音搜索页面
2. 按F12打开开发者工具
3. 切换到Network标签
4. 搜索关键词
5. 查看API请求和响应

### 3. 更新API参数

定期更新以下参数：
- 版本号 (`version_code`, `version_name`)
- 设备信息
- 签名算法

## 注意事项

1. **遵守法律法规** - 仅用于学习和研究目的
2. **尊重版权** - 不要下载和传播未经授权的内容
3. **合理使用** - 避免高频请求，尊重服务器资源
4. **数据安全** - 不要泄露个人cookies或敏感信息

## 更新日志

### v1.0 (2026-04-25)
- 基于抓取的API请求实现增强版搜索
- 支持完整的API参数
- 添加视频下载功能
- 支持JSON/CSV导出
- 提供命令行工具

## 相关资源

- [抖音开放平台](https://open.douyin.com/)
- [Python requests文档](https://docs.python-requests.org/)
- [JSON格式规范](https://www.json.org/)

---

**免责声明**: 本工具仅用于技术学习和研究目的，请遵守相关法律法规和平台使用条款。