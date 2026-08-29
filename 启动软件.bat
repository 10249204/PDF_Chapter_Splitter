@echo off
chcp 65001 >nul
echo =====================================
echo   PDF Chapter Splitter 启动器
echo =====================================
echo.

set "PROJECT_DIR=D:\PDF_Chapter_Splitter"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\pythonw.exe"
set "VENV_PYTHON_CONSOLE=%PROJECT_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境，请先安装依赖。
    echo.
    pause
    exit /b 1
)

echo 正在启动 PDF Chapter Splitter ...
echo.

:: 使用 pythonw.exe 启动 GUI（无控制台窗口）
start "PDF Chapter Splitter" "%VENV_PYTHON%" -m pdf_chapter_splitter.gui

echo PDF Chapter Splitter 已启动！
echo.
timeout /t 2 >nul
