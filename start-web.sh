#!/bin/bash
# ViralDramaBot Web 应用启动脚本

echo "🚀 启动 ViralDramaBot Web 应用..."
echo "📱 前端地址: http://localhost:8000"
echo "📝 API 文档: http://localhost:8000/docs"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.8 或更高版本"
    exit 1
fi

# 检查虚拟环境（如果存在）
if [ -d "venv" ]; then
    echo "✅ 激活虚拟环境..."
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

# 安装依赖（如果需要）
echo "📦 检查依赖..."
python3 -m pip install -q -r requirements.txt

# 启动应用
echo ""
echo "⚡ 启动 FastAPI 服务器..."
python3 app.py

# 打开浏览器（可选，仅在支持的系统上）
# if command -v xdg-open &> /dev/null; then
#     xdg-open http://localhost:8000
# elif command -v open &> /dev/null; then
#     open http://localhost:8000
# fi
