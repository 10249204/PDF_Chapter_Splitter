# PDF Chapter Splitter

PDF Chapter Splitter 是一个帮助用户按章节拆分 PDF 的 Windows 桌面工具。

它会先查找 PDF 中可能的章节，再让你人工确认、修改或忽略，最后按确认后的章节拆分成多个 PDF，并可选择生成 ZIP。

![PDF Chapter Splitter GUI](docs/gui-screenshot.png)

## 下载

| 平台 | 文件 |
| --- | --- |
| Windows x64 | `PDF-Chapter-Splitter-v1.0.0-windows-x64.zip` |

下载 ZIP 后解压，双击：

```text
PDF-Chapter-Splitter.exe
```

普通用户不需要安装 Python、pip、Git 或 PowerShell。

## 三步使用

| 步骤 | 操作 |
| --- | --- |
| 1 | 打开程序，点击“选择 PDF”。 |
| 2 | 等待分析，检查“发现的章节”，勾选正确章节并点击“确认选中章节”。 |
| 3 | 选择输出目录，点击“章节检查完成，进入拆分”，再点击“开始拆分”。 |

如果程序漏掉章节，可以点击“手动添加章节”。如果标题或起始页不对，可以选中章节后点击“编辑章节”。

## 章节识别原理

| 来源 | 说明 |
| --- | --- |
| PDF 书签 / Outline | 优先读取 PDF 自带书签，通常最可靠。 |
| 页面文字与排版 | 如果没有可用书签，程序会根据章节标题样式、页内位置和文字模式推测章节候选。 |
| 用户确认 | 程序只提供候选，最终拆分依据来自用户明确确认的章节。 |

## 支持什么 PDF

| PDF 类型 | 支持情况 |
| --- | --- |
| 有书签 / Outline 的 PDF | 通常效果最好。 |
| 有文本层的电子书 PDF | 可以自动发现章节候选。 |
| 中文文件名 / 中文章节名 | 支持。 |
| 文本质量较低的 PDF | 可以分析，但需要人工仔细检查。 |
| 扫描版 PDF | 当前不支持 OCR，可能需要手动添加章节。 |
| 加密 PDF | 当前不支持密码输入。 |

## 已知限制

| 限制 | 说明 |
| --- | --- |
| 不支持 OCR | 扫描版 PDF 可能识别不到章节。 |
| 不接入 AI | 当前没有 LLM、embedding 或语义识别。 |
| 没有 PDF 页面预览 | 请用 PDF 阅读器核对真实页码。 |
| 不自动确认章节 | 所有章节都需要用户明确确认。 |
| 使用 PDF 物理页码 | 界面页码从 1 开始，可能不同于书本印刷页码。 |
| 不支持取消任务 | 当前分析和拆分任务启动后不能中途取消。 |

## 常见问题

| 问题 | 回答 |
| --- | --- |
| 为什么一个章节都没识别出来？ | 可能是扫描版 PDF、没有文本层，或书签信息不足。你仍可以手动添加章节。 |
| 为什么识别出的章节不完全正确？ | 章节识别是候选检测，不是最终判断。请以人工确认为准。 |
| 为什么目录页里的条目也被识别出来？ | 某些目录排版很像章节标题，程序会尽量标记为需要核对，用户可以忽略。 |
| 为什么页码和书上印刷页码不同？ | 程序使用 PDF 物理页码，也就是 PDF 阅读器里的第几页。 |

## 从源码运行

开发者可以使用 Python 3.12+ 从源码运行：

```powershell
cd D:\PDF_Chapter_Splitter
python -m pip install -e ".[dev]"
python -m pdf_chapter_splitter.gui
```

## 开发构建

Windows 发布包使用 PyInstaller onedir 构建：

```powershell
cd D:\PDF_Chapter_Splitter
python scripts/build_windows.py
```

构建完成后会生成：

```text
release/PDF-Chapter-Splitter-v1.0.0-windows-x64.zip
```

## 开发文档

架构说明和 Phase 1～17 开发历史保留在：

```text
docs/development-history.md
```

核心边界：

```text
GUI
  ↓
WorkflowSession
  ↓
PDFChapterWorkflow
  ↓
PDF / chapters / splitter / archive
```

GUI 不直接调用 PDFReader、Detector、Fusion、ConfirmationService、BoundaryResolver、PDFSplitter 或 ZipCreator。
