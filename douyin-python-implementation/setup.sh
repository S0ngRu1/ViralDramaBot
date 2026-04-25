#!/bin/bash

# 抖音视频下载工具 - 快速开始脚本

echo "================================"
echo "抖音视频下载工具 - 快速开始"
echo "================================"
echo ""

# 检查 Python 版本
echo "✅ 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.7 或以上版本"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "   Python 版本: $PYTHON_VERSION"
echo ""

# 检查是否已安装依赖
echo "✅ 检查依赖..."
if python3 -c "import requests; import urllib3" 2>/dev/null; then
    echo "   依赖已安装"
else
    echo "   需要安装依赖..."
    pip3 install -r requirements.txt
fi
echo ""

# 创建工作目录
echo "✅ 创建工作目录..."
mkdir -p .data
echo "   工作目录: .data"
echo ""

# 显示使用信息
echo "================================"
echo "🚀 可以开始使用了！"
echo "================================"
echo ""
echo "快速命令:"
echo ""
echo "  # 交互式菜单（推荐新手使用）"
echo "  python main.py interactive"
echo ""
echo "  # 获取下载链接"
echo "  python main.py get-link 'https://v.douyin.com/xxxxx'"
echo ""
echo "  # 下载视频"
echo "  python main.py download 'https://v.douyin.com/xxxxx'"
echo ""
echo "  # 解析视频信息"
echo "  python main.py parse 'https://v.douyin.com/xxxxx'"
echo ""
echo "  # 查看所有选项"
echo "  python main.py -h"
echo ""
echo "Python 脚本使用:"
echo ""
echo "  from tools import download_douyin_video"
echo "  result = download_douyin_video('https://v.douyin.com/xxxxx')"
echo "  print(result['file_path'])"
echo ""
echo "查看更多示例:"
echo "  python examples.py 1"
echo ""
echo "查看详细文档:"
echo "  README.md                       (快速开始)"
echo "  TECHNICAL_DOCUMENTATION.md      (完整技术文档)"
echo "  PROJECT_SUMMARY.md              (项目总结)"
echo ""
