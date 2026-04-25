# 抖音视频解析与下载工具

## 🎬 功能

- 🔍 **智能链接解析** - 自动识别和解析抖音分享链接
- 📥 **无水印下载** - 获取并下载无水印视频
- 📊 **实时进度** - 显示下载进度和速度
- 🗁 **自动管理** - 自动创建工作目录，文件管理

## ⚡ 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 命令行使用

```bash
# 获取下载链接
python main.py get-link "https://v.douyin.com/xxxxx"

# 下载视频
python main.py download "https://v.douyin.com/xxxxx"

# 解析视频信息
python main.py parse "https://v.douyin.com/xxxxx"

# 交互式菜单
python main.py interactive
```

### Python 脚本使用

```python
from tools import download_douyin_video

def on_progress(progress):
    print(f"进度: {progress['percentage']:.1f}%")

result = download_douyin_video(
    "https://v.douyin.com/xxxxx",
    on_progress=on_progress
)

if result['status'] == 'success':
    print(f"✅ 文件已保存: {result['file_path']}")
else:
    print(f"❌ 失败: {result['message']}")
```

## ⚙️ 配置

### 环境变量

```bash
# 自定义工作目录
export WORK_DIR="/path/to/videos"

# 启用调试模式
export DEBUG=1
```

### 默认值

- 工作目录: `.data`
- 请求超时: 10 秒
- 最大重试: 3 次
- 块大小: 8 KB

## 📚 完整文档

查看 [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) 获取详细的技术文档，包括：

- 完整的架构设计
- 详细的模块解释
- 完整的工作流程图
- 详细的 API 参考
- 多个使用示例
- 问题排查指南

## 📁 项目结构

```
├── main.py                          # 命令行入口
├── tools.py                         # 高级工具函数
├── douyin_processor.py              # 核心处理器
├── config.py                        # 配置管理
├── logger.py                        # 日志系统
├── requirements.txt                 # 依赖列表
├── README.md                        # 快速指南
└── TECHNICAL_DOCUMENTATION.md       # 完整文档
```

## 🔧 常见问题

### Q: 如何设置自定义下载目录？

```bash
export WORK_DIR="/my/custom/path"
python main.py download "https://v.douyin.com/xxxxx"
```

### Q: 下载速度很慢怎么办？

```bash
# 调整超时时间（增加容错性）
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx"
```

### Q: 如何看到详细的调试信息？

```bash
DEBUG=1 python main.py download "https://v.douyin.com/xxxxx" 2>&1 | tee debug.log
```

## 📝 模块说明

| 模块 | 功能 |
|------|------|
| `logger.py` | 日志系统，支持多级别日志 |
| `config.py` | 配置管理，工作目录初始化 |
| `douyin_processor.py` | 核心处理器，视频解析和下载 |
| `tools.py` | 高级 API，包装 DouyinProcessor |
| `main.py` | 命令行接口和交互式菜单 |

## 📖 使用示例

### 示例 1: 获取下载链接

```python
from tools import get_douyin_download_link

result = get_douyin_download_link("https://v.douyin.com/xxxxx")
print(result['download_url'])
```

### 示例 2: 下载单个视频

```bash
python main.py download "https://v.douyin.com/xxxxx"
```

### 示例 3: 批量下载

```python
from tools import download_douyin_video

links = ["https://v.douyin.com/link1", "https://v.douyin.com/link2"]

for link in links:
    result = download_douyin_video(link)
    if result['status'] == 'success':
        print(f"✅ {result['title']}")
```

## 🚀 性能

- **内存占用**: 恒定（流式处理）
- **支持大文件**: ✅ 支持 GB 级文件
- **断点续传**: ✅ 支持
- **并发下载**: ✅ 支持（使用 ThreadPoolExecutor）

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

遇到问题？
1. 查看 [完整文档](TECHNICAL_DOCUMENTATION.md) 的问题排查部分
2. 启用 DEBUG 模式查看详细日志
3. 检查网络连接和抖音服务器状态
