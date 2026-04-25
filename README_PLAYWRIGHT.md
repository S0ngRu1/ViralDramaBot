# 抖音视频搜索功能 - Playwright版

基于Playwright拦截API响应的抖音视频搜索功能，解决了签名验证问题，提供了最稳定的搜索体验。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 运行安装脚本
python install_playwright.py

# 或手动安装
pip install playwright requests beautifulsoup4
playwright install chromium
```

### 2. 基本使用

```bash
# 使用Playwright搜索（推荐）
python example_search.py 短剧 --method playwright

# 带筛选条件
python example_search.py 美食 --method playwright -n 10 --min-likes 1000 --min-duration 10

# 导出结果
python example_search.py 旅行 --method playwright --export both

# 下载视频
python example_search.py 宠物 --method playwright --download --download-dir ./videos
```

### 3. 交互式界面

```bash
python run_search.py
```

## 🔧 搜索方法对比

| 方法 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **Playwright** | ✅ 最稳定<br>✅ 绕过签名验证<br>✅ 获取完整数据 | ⚠️ 需要安装浏览器<br>⚠️ 速度较慢 | ⭐⭐⭐⭐⭐ |
| **API** | ⚠️ 速度快 | ❌ 签名易失效<br>❌ 需要维护参数 | ⭐⭐ |
| **DOM解析** | ⚠️ 不需要签名 | ❌ 不稳定<br>❌ 数据不完整 | ⭐ |
| **自动选择** | ✅ 自动选择最佳方法 | ⚠️ 依赖可用性 | ⭐⭐⭐ |

## 📋 命令行选项

```bash
python example_search.py <关键词> [选项]

必需参数:
  keyword               搜索关键词

主要选项:
  -n, --max-results N   最大结果数量 (默认: 10)
  -l, --min-likes N     最小点赞数 (默认: 0)
  --min-duration SEC    最小时长(秒) (默认: 0)
  --max-duration SEC    最大时长(秒) (默认: 0, 表示不限制)
  --method {playwright,api,dom,auto}
                        搜索方法 (默认: auto)
  --export {json,csv,both}
                        导出格式 (默认: json)
  --download            下载视频
  --download-dir DIR    下载目录 (默认: ./downloads)

Playwright特有选项:
  --headless            使用无头模式
  --scroll-times N      滚动次数 (默认: 5)
  --scroll-delay SEC    滚动延迟(秒) (默认: 2.0)

其他选项:
  --proxy URL           代理URL
  --verbose             显示详细信息
  -h, --help            显示帮助信息
```

## 🎬 Playwright搜索原理

### 工作原理
1. **启动真实浏览器** - 使用Chromium浏览器模拟用户行为
2. **拦截API响应** - 监听抖音搜索API的响应
3. **解析JSON数据** - 从响应中提取结构化视频信息
4. **智能滚动** - 自动滚动页面加载更多内容

### 数据提取
基于抓取的真实API响应结构，可以获取：
- ✅ 视频ID、标题、描述
- ✅ 作者信息（昵称、ID、头像）
- ✅ 统计信息（点赞、评论、分享、收藏）
- ✅ 视频信息（时长、分辨率、播放地址）
- ✅ 封面图、音乐信息
- ✅ 标签、创建时间

### 反反爬虫策略
- 🛡️ 随机延迟和滚动行为
- 🛡️ 禁用自动化特征检测
- 🛡️ 使用真实User-Agent
- 🛡️ 合理请求频率控制

## 📁 文件结构

```
.
├── dy_video_download/
│   ├── playwright_search.py      # Playwright搜索实现
│   ├── enhanced_search.py        # API搜索实现
│   ├── douyin_search.py          # DOM搜索实现
│   └── app.py                    # Web应用
├── example_search.py             # 命令行工具
├── run_search.py                 # 交互式启动器
├── install_playwright.py         # 依赖安装脚本
├── test_enhanced_search.py       # 增强版测试
├── README_SEARCH.md              # 搜索功能文档
└── README_PLAYWRIGHT.md          # 本文档
```

## 🧪 测试验证

```bash
# 运行所有测试
python run_search.py
# 选择选项3

# 或直接运行测试
python test_enhanced_search.py
```

## 🔍 高级用法

### 1. 批量搜索

```python
# batch_search.py
from dy_video_download.playwright_search import SyncDouyinSearcher

keywords = ["短剧", "美食", "旅行", "宠物", "搞笑"]
searcher = SyncDouyinSearcher(headless=True)

for keyword in keywords:
    print(f"搜索: {keyword}")
    videos = searcher.search_videos(keyword, max_results=5)
    print(f"找到 {len(videos)} 个视频")
```

### 2. 自定义配置

```python
from dy_video_download.playwright_search import SyncDouyinSearcher

# 自定义配置
searcher = SyncDouyinSearcher(
    headless=True,              # 无头模式
    use_proxy=True,             # 使用代理
    proxy_url="http://127.0.0.1:7890"  # 代理地址
)

videos = searcher.search_videos(
    keyword="短剧",
    max_results=20,
    scroll_times=10,           # 增加滚动次数
    scroll_delay=3.0,          # 增加延迟
    min_likes=10000,           # 高点赞筛选
    min_duration=30,           # 长视频筛选
    max_duration=180
)
```

### 3. 数据导出和分析

```python
import json
from datetime import datetime

# 导出为JSON
with open("videos.json", "w", encoding="utf-8") as f:
    json.dump([v.to_dict() for v in videos], f, ensure_ascii=False, indent=2)

# 数据分析
avg_likes = sum(v.likes for v in videos) / len(videos)
avg_duration = sum(v.duration for v in videos) / len(videos)
latest_video = max(videos, key=lambda x: x.create_time)

print(f"平均点赞: {avg_likes:.0f}")
print(f"平均时长: {avg_duration:.0f}秒")
print(f"最新视频: {datetime.fromtimestamp(latest_video.create_time)}")
```

## ⚠️ 注意事项

### 1. 法律与道德
- 📜 仅用于学习和研究目的
- 📜 遵守抖音用户协议和robots.txt
- 📜 不要高频请求，避免对服务器造成压力
- 📜 不要传播或商用他人内容

### 2. 技术限制
- ⚡ Playwright需要安装浏览器，首次运行较慢
- ⚡ 抖音可能更新反爬机制，需要维护代码
- ⚡ 视频下载可能受防盗链限制

### 3. 性能优化
- 🚀 使用无头模式提高速度
- 🚀 调整滚动次数和延迟平衡速度与成功率
- 🚀 合理设置筛选条件减少数据量
- 🚀 使用代理服务器提高稳定性

## 🔄 维护更新

### 常见问题

1. **Q: Playwright启动失败**
   - A: 运行 `playwright install chromium`
   - A: 检查浏览器依赖: `playwright --version`

2. **Q: 搜索无结果**
   - A: 检查网络连接
   - A: 尝试关闭无头模式调试
   - A: 增加滚动次数和延迟

3. **Q: 视频无法下载**
   - A: 抖音防盗链，尝试第三方解析服务
   - A: 检查网络和代理设置

### 代码维护
- 定期检查抖音API变更
- 更新选择器和参数
- 优化反反爬策略
- 添加错误处理和重试

## 📚 学习资源

- [Playwright官方文档](https://playwright.dev/python/)
- [抖音开放平台](https://open.douyin.com/)
- [Python异步编程](https://docs.python.org/3/library/asyncio.html)
- [网络爬虫最佳实践](https://www.scrapehero.com/how-to-prevent-getting-blacklisted-while-scraping/)

## 🤝 贡献与反馈

### 问题报告
1. 描述具体问题
2. 提供复现步骤
3. 包含错误日志
4. 说明环境信息

### 功能建议
1. 描述使用场景
2. 说明预期效果
3. 提供参考实现

---

**免责声明**: 本工具仅用于技术学习和研究，请遵守相关法律法规和平台使用条款。

**最后更新**: 2026-04-25
**版本**: v2.0 (Playwright版)