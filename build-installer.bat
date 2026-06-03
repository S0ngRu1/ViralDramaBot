@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 构建 onedir 应用 + Inno Setup 安装包（需已安装 Inno Setup 6）
if exist dist (
    echo 正在删除 dist ...
    rmdir /s /q dist
)

echo [1/2] 正在执行 PyInstaller ^(onedir^) ...
python -m PyInstaller ViralDramaBot.spec
if errorlevel 1 (
    echo PyInstaller 构建失败。
    exit /b 1
)

if not exist "dist\ViralDramaBot\ViralDramaBot.exe" (
    echo 未找到 dist\ViralDramaBot\ViralDramaBot.exe，请检查 PyInstaller 输出。
    exit /b 1
)

set "ISCC="
where ISCC >nul 2>&1
if not errorlevel 1 (
    set "ISCC=ISCC"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo.
    echo 未找到 Inno Setup 编译器 ISCC.exe。
    echo 请安装 Inno Setup 6: https://jrsoftware.org/isinfo.php
    echo 安装后将 ISCC 加入 PATH，或使用默认安装路径。
    exit /b 1
)

echo [2/2] 正在编译安装包 ...
"%ISCC%" installer\ViralDramaBot.iss
if errorlevel 1 (
    echo Inno Setup 编译失败。
    exit /b 1
)

echo.
echo 完成: dist\installer\ViralDramaBot-Setup.exe
echo 可将该安装包分发给用户；安装时可选择目录并创建桌面快捷方式。
