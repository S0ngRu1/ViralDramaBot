@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 先清空 dist，避免覆盖正在使用的 exe 时出现 PermissionError（请先关闭正在运行的 ViralDramaBot.exe）
if exist dist (
    echo 正在删除 dist ...
    rmdir /s /q dist
)

echo 正在执行 PyInstaller ...
python -m PyInstaller ViralDramaBot.spec
if errorlevel 1 (
    echo.
    echo 构建失败。若提示拒绝访问，请关闭正在运行的 dist\ViralDramaBot.exe 或任务管理器中相关进程后重试。
    pause
    exit /b 1
)

echo.
echo 完成: dist\ViralDramaBot.exe
pause
