@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   甲方后台定时查询工具 - Windows 构建脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

REM 检查 PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller
)

REM 检查 pywebview
python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo 正在安装 pywebview...
    pip install pywebview
)

echo.
echo 开始打包...
echo.

pyinstaller --clean --noconfirm "甲方后台定时查询工具_win.spec"

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo   输出目录: dist\甲方后台定时查询工具.exe
echo ========================================
echo.
echo 使用说明：
echo   1. 将 dist\甲方后台定时查询工具.exe 复制到目标电脑
echo   2. 双击运行即可
echo   3. 数据存储在 用户目录\甲方后台定时查询工具\ 下
echo.
pause
