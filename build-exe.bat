@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 先清空 dist，避免覆盖正在运行的程序时出现 PermissionError
REM 请关闭 dist\ViralDramaBot\ViralDramaBot.exe 及相关进程后再打包
if exist dist (
    echo 正在删除 dist ...
    rmdir /s /q dist
)

echo 正在执行 PyInstaller ^(onedir 目录分发，启动更快^) ...
python -m PyInstaller ViralDramaBot.spec
if errorlevel 1 (
    echo.
    echo 构建失败。若提示拒绝访问，请关闭正在运行的 ViralDramaBot 后重试。
    pause
    exit /b 1
)

echo.
echo 完成: dist\ViralDramaBot\ViralDramaBot.exe
echo 分发时请复制整个 dist\ViralDramaBot 文件夹，不要只拷贝单个 exe。
echo 需要安装向导（选路径、桌面快捷方式）请运行 build-installer.bat
pause
