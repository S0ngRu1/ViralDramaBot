@echo off
REM ViralDramaBot Web 应用启动脚本 (Windows)

echo 🚀 启动 ViralDramaBot Web 应用...
echo 📱 前端地址: http://localhost:8000
echo 📝 API 文档: http://localhost:8000/docs
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.8 或更高版本
    pause
    exit /b 1
)

REM 激活虚拟环境（如果存在）
if exist venv (
    echo ✅ 激活虚拟环境...
    call venv\Scripts\activate.bat
)

REM 安装依赖
echo 📦 检查依赖...
python -m pip install -q -r requirements.txt

REM 启动应用
echo.
echo ⚡ 启动 FastAPI 服务器...
python app.py

pause
