#!/usr/bin/env pwsh
# PDF Chapter Splitter 启动脚本

$PROJECT_DIR = "D:\PDF_Chapter_Splitter"
$PYTHON = Join-Path $PROJECT_DIR ".venv\Scripts\python.exe"

if (-not (Test-Path $PYTHON)) {
    Write-Error "未找到虚拟环境，请先安装依赖。"
    exit 1
}

Write-Host "正在启动 PDF Chapter Splitter GUI ..." -ForegroundColor Cyan
& $PYTHON -m pdf_chapter_splitter.gui
