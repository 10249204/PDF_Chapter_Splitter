# PDF Chapter Splitter

PDF Chapter Splitter 是一个计划中的 Python 桌面工具，用于按章节将 PDF 拆分为多个文件，并在未来打包导出结果。

## 项目目标

| 目标 | 说明 |
| --- | --- |
| PDF 处理 | 使用 PyMuPDF 作为 PDF 读取、文本提取和后续拆分的核心库。 |
| 桌面界面 | 使用 PySide6 构建未来 GUI。当前阶段不创建完整界面。 |
| 章节工作流 | 未来支持章节识别、人工确认、拆分预览和导出。 |
| 可测试架构 | 使用 pytest，并将 GUI、PDF 核心逻辑、章节识别、ZIP 导出、数据模型解耦。 |

## 架构边界

| 模块 | 职责 | 当前阶段状态 |
| --- | --- | --- |
| `pdf_chapter_splitter.models` | 保存跨模块共享数据模型，例如 `SplitSegment`，并保留 `Chapter` 的兼容导出。内部页码统一使用 0-based index，并提供面向 GUI 的 1-based page number 辅助属性。 | 已建立 |
| `pdf_chapter_splitter.pdf` | 定义 PDF 读取边界、PyMuPDF 具体实现、PDF 结构化文本模型和异常体系。 | 已支持基础读取 |
| `pdf_chapter_splitter.splitter` | 定义 PDF 拆分引擎、拆分结果模型、输出文件名处理和拆分异常体系。 | 已支持基础拆分 |
| `pdf_chapter_splitter.chapters` | 定义章节候选、确认章节、候选证据、人工输入、候选检测、候选融合、用户确认、候选/章节排序和验证，以及已确认章节到拆分区间的确定性边界推导。 | 已支持领域模型、候选生成、多来源融合、确认工作流与边界推导 |
| `pdf_chapter_splitter.application` | 编排 Reader、Candidate Detector、Fusion、Confirmation、Boundary、Splitter 和 ZIP，并提供未来 GUI 可依赖的 Session 状态外壳；不重新实现底层能力。 | 已支持应用层 Workflow 与 Session |
| `pdf_chapter_splitter.archive` | 负责 ZIP 或其他归档导出。 | 已支持 ZIP 导出 |
| `pdf_chapter_splitter.gui` | 负责 PySide6 桌面界面 MVP，只消费 application 层 API，不直接调用 PDF/章节/拆分/ZIP 底层模块。 | 已支持 GUI MVP |

## 页码约定

| 场景 | 约定 |
| --- | --- |
| 内部逻辑 | 始终使用 0-based page index。第一页是 `0`。 |
| GUI 显示 | 未来统一显示 1-based page number。第一页显示为 `1`。 |
| `SplitSegment` 范围 | 使用半开区间：`start_page_index` 包含，`end_page_index` 不包含。 |
| `Chapter` 起点 | 只表示已确认章节起点，使用 0-based `start_page_index`；不包含结束页。 |

## 开发阶段

| 阶段 | 内容 | 当前状态 |
| --- | --- | --- |
| Phase 1 | 项目初始化、模块化结构、基础数据模型、PDF reader 抽象、基础测试。 | 已完成 |
| Phase 2 | 基于 PyMuPDF 实现实际 PDF reader，并补充读取测试。 | 已完成 |
| Phase 3 | 实现独立 PDF Split Engine，基于 `SplitSegment` 输出多个独立 PDF。 | 已完成 |
| Phase 4 | 实现 ZIP 导出和基础 CLI，让项目在无 GUI 阶段也能实际使用。 | 已完成 |
| Phase 5 | 落地章节候选、候选证据、人工输入和确认章节领域模型；支持 outline/manual 到候选的显式适配、候选排序和候选验证。 | 已完成 |
| Phase 6 | 实现基于文本层和布局规则的章节候选识别，只负责产生 `ChapterCandidate`。 | 已完成 |
| Phase 7 | 实现多来源 `ChapterCandidate` 融合，只负责形成融合后的候选。 | 已完成 |
| Phase 8 | 人工确认层与 `Chapter` 生成，只负责 `ChapterCandidate -> Chapter` 的显式用户决策。 | 已完成 |
| Phase 9 | 根据已确认章节起点推导拆分边界，并生成 `SplitSegment`。 | 已完成 |
| Phase 10 | 建立 Application Workflow，编排自动章节路径与手动页码路径，并统一进入拆分和可选 ZIP 导出。 | 已完成 |
| Phase 11 | 使用测试运行时动态生成的真实 PDF，验证 Application Workflow 的端到端冒烟链路。 | 已完成 |
| Phase 12 | 建立应用层进度事件与错误契约，为未来 GUI/CLI 调用提供稳定的状态和错误接口。 | 已完成 |
| Phase 13 | 建立应用层 `WorkflowSession` / GUI Adapter Contract，保存用户工作流状态并委托现有 Workflow。 | 已完成 |
| Phase 14 | 实现 PySide6 GUI MVP，让用户通过桌面窗口完成选择 PDF、候选确认、拆分、ZIP、进度和错误查看。 | 已完成 |
| Phase 15B | 建立 PDF 输入文本质量诊断、TOC 页识别和 Candidate 质量治理，不自动删除候选。 | 已完成 |
| Phase 16 | 建立 Analysis Summary 与 Candidate Presentation Policy，并在 GUI 中展示 PDF quality、candidate quality 和默认候选过滤。 | 已完成 |

## 当前明确不做

| 功能 | 状态 |
| --- | --- |
| 高级完整 GUI | 暂不实现，当前仅有 GUI MVP |
| OCR | 暂不实现 |
| AI 接入 | 暂不实现 |
| Candidate Ranking | 暂不实现 |
| Semantic Ranking | 暂不实现 |
| 基于 confidence 的自动确认 | 暂不实现 |
| 自动章节拆分的 CLI/GUI 集成 | 暂不实现 |
| `Chapter.end_page_index` 字段 | 不实现，边界只存在于 `SplitSegment` |
| 高级语义章节识别 | 暂不实现 |
| async/cancellation/threading/logging framework | 暂不实现 |
| PyInstaller | 暂不实现 |

## Phase 2

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| PDF 打开 | 通过 `PyMuPDFReader(path)` 打开真实 PDF，支持 context manager。 |
| PDF 页数读取 | 通过 `reader.page_count` 获取总页数。 |
| 页面文本读取 | 通过 `reader.get_page_text(page_index)` 按 0-based 页码读取文本。 |
| 全文文本读取 | 通过 `reader.get_all_page_text()` 一次读取所有页面文本，不重新打开 PDF。 |
| 页面 TextBlock 读取 | 通过 `reader.get_page_text_blocks(page_index)` 获取结构化文本块、行、span、bounding box、字体大小和字体名称。 |
| PDF Outline / Bookmark 读取 | 通过 `reader.get_outline()` 获取标题、层级和 0-based 目标页码。 |
| 文本层检测 | 通过 `reader.has_text_layer()` 判断 PDF 是否至少有一页包含非空可提取文本。 |
| PDF 基础异常处理 | 使用项目自己的异常类型包装常见打开、密码、越界、关闭后读取等错误。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| PDF 拆分 | 暂不实现 |
| 自动章节识别 | 暂不实现 |
| OCR | 暂不实现 |
| GUI | 暂不实现 |
| AI | 暂不实现 |

## PDF Reader API

| API | 返回 | 说明 |
| --- | --- | --- |
| `PyMuPDFReader(path)` | `PyMuPDFReader` | 打开 PDF。底层 `fitz.Document` 不向业务层暴露。 |
| `reader.close()` | `None` | 关闭 PDF 资源。可重复调用。 |
| `with PyMuPDFReader(path) as reader:` | `PyMuPDFReader` | 推荐的资源管理方式。 |
| `reader.page_count` | `int` | PDF 总页数。 |
| `reader.get_metadata()` | `dict[str, str]` | PDF metadata 字符串键值。 |
| `reader.get_page_text(page_index)` | `str` | 读取指定 0-based 页面文本。 |
| `reader.get_all_page_text()` | `list[str]` | 读取所有页面文本。 |
| `reader.get_page_text_blocks(page_index)` | `list[TextBlock]` | 读取结构化页面文本信息。 |
| `reader.get_page_size(page_index)` | `PageSize` | 读取页面实际宽高，用于布局比例计算。 |
| `reader.get_outline()` | `list[OutlineItem]` | 读取规范化 outline/bookmark。 |
| `reader.has_text_layer()` | `bool` | 至少存在一个非空文本页面时返回 `True`。 |

## PDF 数据结构

| 模型 | 关键字段 | 说明 |
| --- | --- | --- |
| `PageSize` | `width`, `height` | PDF 页面实际宽高。 |
| `BoundingBox` | `x0`, `y0`, `x1`, `y1` | PDF 页面坐标中的矩形区域。 |
| `TextSpan` | `text`, `bbox`, `font_size`, `font_name`, `block_index`, `line_index`, `span_index` | 字体样式通常一致的一段文本。 |
| `TextLine` | `bbox`, `block_index`, `line_index`, `spans` | 由多个 `TextSpan` 组成的一行文本。 |
| `TextBlock` | `bbox`, `block_index`, `lines` | 由多行文本组成的文本块。 |
| `OutlineItem` | `title`, `level`, `page_index` | 规范化后的 PDF 书签条目，页码为 0-based；没有明确目标页时为 `None`。 |

## PDF 异常体系

| 异常 | 说明 |
| --- | --- |
| `PDFReaderError` | PDF reader 相关异常基类。 |
| `PDFOpenError` | 文件不存在、路径不是文件、PDF 无法打开等打开失败。 |
| `PDFPasswordError` | PDF 需要密码。本阶段不尝试破解，也不实现 GUI 密码输入。 |
| `PDFPageIndexError` | 0-based `page_index` 越界或无效。 |
| `PDFClosedError` | PDF reader 已关闭后继续读取。 |

## Outline / Bookmark 设计决定

PDF Outline / Bookmark 中的页码只作为辅助信息，不能直接视为实际章节起始页。

原因是很多 PDF 或电子书存在封面、版权页、目录页、罗马数字页码、印刷页码与 PDF 内部页码不一致等情况。未来章节识别可以参考 outline，但必须结合文本、布局或用户确认。

## Phase 3

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| PDF 分段验证 | 拆分前验证页码范围、顺序、重叠和 PDF 总页数。 |
| PDF 单段拆分 | 支持把一个范围输出为独立 PDF。 |
| PDF 多段拆分 | 支持多个有序、不重叠的 `SplitSegment`。 |
| 单页拆分 | 通过 1-based 输入 `3-3` 转换为内部半开区间 `2..3`。 |
| 自定义输出文件名 | 使用 `SplitSegment.title` 作为输出 PDF 文件名来源。 |
| 文件名安全处理 | 清理 Windows 非法字符：`\ / : * ? " < > |`，并额外处理常见中文全角 `：` 和 `？`。 |
| 输出文件冲突处理 | 不静默覆盖，自动生成 `Part.pdf`、`Part (2).pdf` 这样的安全文件名。 |
| 原始 PDF 只读保护 | 使用页面复制生成新 PDF，测试验证原始文件 hash 不变。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| 自动章节识别 | 暂不实现 |
| OCR | 暂不实现 |
| GUI | 暂不实现 |
| AI | 暂不实现 |

## PDF Splitter API

| API | 返回 | 说明 |
| --- | --- | --- |
| `PDFSplitter().split(input_path, segments, output_directory)` | `SplitResult` | 将原始 PDF 按多个 `SplitSegment` 拆成独立 PDF。 |
| `SplitSegment.from_page_numbers(title, start_page_number, end_page_number)` | `SplitSegment` | 唯一的用户 1-based 闭区间页码转换入口。 |
| `sanitize_pdf_filename(title)` | `str` | 将标题转换为安全 PDF 文件名。 |

## SplitSegment 页码语义

| 层级 | 语义 |
| --- | --- |
| `SplitSegment` 内部字段 | 继续使用 0-based 半开区间：`start_page_index` 包含，`end_page_index` 不包含。 |
| 用户/CLI/GUI 输入 | 使用 1-based 闭区间：第 1 页到第 5 页写作 `1-5`。 |
| 集中转换入口 | 使用 `SplitSegment.from_page_numbers()` 转换，不在业务代码里分散编写 `page - 1`。 |

## Splitter 数据结构

| 模型 | 字段 | 说明 |
| --- | --- | --- |
| `SplitOutput` | `segment`, `output_path` | 一个输出 PDF 及其对应的 `SplitSegment`。 |
| `SplitResult` | `input_path`, `output_directory`, `outputs` | 一次拆分操作的结果摘要，供未来 GUI 和 ZIP 模块使用。 |

## Splitter 异常体系

| 异常 | 说明 |
| --- | --- |
| `PDFSplitError` | PDF 拆分相关异常基类。 |
| `InvalidSegmentError` | segment 为空、页码越界、无序或范围不合法。 |
| `SegmentOverlapError` | segment 之间出现重叠。 |
| `OutputFileError` | 输出目录或输出文件无法准备。 |

## 输出文件冲突策略

拆分器不会自动删除输出目录中的任何既有文件，也不会静默覆盖已有 PDF。发生文件名冲突时，使用递增后缀生成新文件名，例如：

| 已存在 | 新输出 |
| --- | --- |
| `Part 1.pdf` | `Part 1 (2).pdf` |
| `Part 1.pdf`, `Part 1 (2).pdf` | `Part 1 (3).pdf` |

## Phase 4

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| ZIP 打包 | 可以把 `SplitResult` 的输出 PDF 打成 ZIP。 |
| CLI 手动拆分 | 可以通过命令行手动指定多个 segment。 |
| CLI ZIP | 可选生成 ZIP。 |
| 输出目录默认值 | 没有传 `--output` 时，默认创建 `<input_stem>_split/`。 |
| 输入验证 | 页码、segment 顺序、重叠、缺失 PDF 等都会给出友好错误。 |
| 输出文件冲突保护 | PDF 和 ZIP 都不会静默覆盖已有文件。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| 自动章节识别 | 暂不实现 |
| OCR | 暂不实现 |
| GUI | 暂不实现 |
| AI | 暂不实现 |
| PyInstaller | 暂不实现 |

## CLI

安装后可直接运行：

```powershell
pdf-chapter-splitter split book.pdf --segment "Part 1=1-50" --segment "Part 2=51-100"
```

也可以直接运行：

```powershell
python -m pdf_chapter_splitter.cli split book.pdf --segment "Part 1=1-50"
```

### segment 语法

| 格式 | 说明 |
| --- | --- |
| `Title=1-50` | 1-based 闭区间，标题和页码用 `=` 分隔。 |

### 常用参数

| 参数 | 说明 |
| --- | --- |
| `--output` | 指定输出目录。 |
| `--segment` | 可重复，指定一个拆分段。 |
| `--zip` | 拆分完成后生成 ZIP。 |

### 页码规则

CLI 使用 1-based 闭区间页码，例如 `1-10` 表示第 1 页到第 10 页。内部仍会统一通过 `SplitSegment.from_page_numbers()` 转换为 0-based 半开区间。

### 输出示例

```text
book_split/
├── Part 1.pdf
├── Part 2.pdf
└── book.zip
```

### 退出码

| 场景 | 退出码 |
| --- | --- |
| 正常完成 | `0` |
| 用户输入错误或处理失败 | 非 `0` |

## Phase 5

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| 章节候选模型 | `ChapterCandidate` 表示“可能的章节起点”，保存标题、0-based 起始页、兼容单来源、完整来源集合、原始标题、置信度、层级和证据。 |
| 候选来源枚举 | `ChapterCandidateSource` 预留 `OUTLINE`、`TEXT_LAYOUT`、`OCR`、`MANUAL`、`AI`，当前只实现 outline/manual 输入适配。 |
| 候选证据模型 | `ChapterEvidence` 表示候选背后的证据，不等同于确认章节。 |
| 人工输入模型 | `ManualChapterInput` 保存用户输入的 1-based 页码，并由适配器转换为内部 0-based 候选。 |
| 确认章节模型 | `Chapter` 表示“已经确认的章节起点”，只保存标题、0-based 起始页、层级和来源追溯；不保存结束页。 |
| Outline 候选适配 | `OutlineCandidateDetector` 将 `OutlineItem` 显式转换为 `ChapterCandidate`，不会直接确认章节。 |
| Manual 候选适配 | `ManualCandidateDetector` 将人工输入显式转换为 `ChapterCandidate`。 |
| 候选排序 | `sort_chapter_candidates()` 只按 0-based 起始页排序，不做推理。 |
| 候选验证 | `validate_chapter_candidates()` 检查候选页码是否在 PDF 范围内，以及候选起始页是否重复。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| 基于 confidence 的自动确认 | 暂不实现 |
| `Chapter -> SplitSegment` 边界解析 | 已在 Phase 9 作为独立领域层实现；Phase 5 不负责 |
| Chapter end page 字段 | 不实现，`Chapter` 只表示已确认章节起点 |
| Candidate Ranking | 暂不实现 |
| OCR | 暂不实现 |
| AI | 暂不实现 |
| GUI | 暂不实现 |

### Chapter 流程边界

| 层级 | 语义 | 当前阶段职责 |
| --- | --- | --- |
| `ChapterCandidate` | 可能的章节起点 | 由 outline/manual 显式输入生成，支持验证和排序。 |
| `Chapter` | 用户已经确认的章节起点 | 保存确认后的标题、起始页、层级和候选追溯。 |
| `SplitSegment` | 已经确定的拆分区间 | Phase 9 由 `ChapterBoundaryResolver` 从 `Chapter` 推导。 |

### Chapter API

| API | 返回 | 说明 |
| --- | --- | --- |
| `Chapter(title, start_page_index, level=1, provenance=None)` | `Chapter` | 创建确认章节起点，内部页码为 0-based。 |
| `Chapter.from_page_number(title, start_page_number, level=1, provenance=None)` | `Chapter` | 从用户界面未来使用的 1-based 页码创建章节。 |
| `Chapter.gui_page_number` | `int` | 面向 GUI 的 1-based 起始页码。 |
| `Chapter.validate(page_count=None)` | `None` | 验证章节起点是否在可选 PDF 页数范围内。 |
| `OutlineCandidateDetector().detect(outline_items)` | `tuple[ChapterCandidate, ...]` | 将 PDF outline/bookmark 转成候选。 |
| `ManualCandidateDetector().detect(inputs)` | `tuple[ChapterCandidate, ...]` | 将人工输入转成候选。 |
| `sort_chapter_candidates(candidates)` | `tuple[ChapterCandidate, ...]` | 返回按起始页排序后的候选。 |
| `validate_chapter_candidates(candidates, page_count)` | `None` | 验证候选页码范围和重复起始页。 |

## Phase 6

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| 文本布局候选识别 | `TextLayoutCandidateDetector` 从 `PDFReader.get_page_text_blocks()` 读取结构化文本，产生 `ChapterCandidate`。 |
| 页面尺寸读取 | `PDFReader.get_page_size()` 返回实际页面宽高，用于计算页面顶部位置比例。 |
| 文本长度特征 | `TextLayoutFeatures.text_length` 用于过滤过长正文段落。 |
| 字体大小特征 | `TextLayoutFeatures.font_size` 使用 block 内 span 字符数加权平均，不假设一个 block 只有一个字体。 |
| 正文字体基准 | 从当前检测页的大段文本 span 字体大小分布估计正文常见字号，不依赖固定字号。 |
| 字体比例 | `TextLayoutFeatures.font_size_ratio` 表示候选字号与正文基准字号的比例。 |
| 页面位置 | `TextLayoutFeatures.top_position_ratio` 使用 `block.bbox.y0 / page_height`，页面高度来自 reader。 |
| 基础标题模式 | 支持中文“第 N 章”、英文 `Chapter N`、简单数字标题 `1 Introduction`。 |
| 小节配置 | 默认不把“第 N 节”作为一级候选；设置 `TextLayoutDetectorConfig(include_sections=True)` 后可开启中文“节”。 |
| confidence | 使用集中配置的规则权重计算 `0.0 ~ 1.0` 的置信度。 |
| 候选阈值 | `TextLayoutDetectorConfig.min_confidence` 默认 `0.60`，低于阈值不输出。 |
| 可解释证据 | 输出 `TEXT_PATTERN`、`FONT_SIZE`、`POSITION`、`PAGE_LAYOUT` 等 `ChapterEvidence`，描述保存观察事实。 |
| 候选去重 | 同一页面、同一 block、同一标题不会重复输出。 |
| 指定页检测 | `detect(reader, pages=(...))` 只检测指定 0-based 页面。 |
| 真实 PDF fixture 测试 | 覆盖英文标题、数字标题、普通正文、误报样例、指定页面检测和页面尺寸读取。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| Candidate Fusion | 暂不实现 |
| Candidate Ranking | 暂不实现 |
| 基于 confidence 的自动确认 | 暂不实现 |
| `Chapter -> SplitSegment` 边界解析 | 已在 Phase 9 作为独立领域层实现；Phase 6 不负责 |
| Chapter end page 字段 | 不实现，`Chapter` 只表示已确认章节起点 |
| 跨页标题合并 | 暂不实现 |
| OCR | 暂不实现 |
| AI | 暂不实现 |
| GUI | 暂不实现 |

### Text Layout Detector API

| API | 返回 | 说明 |
| --- | --- | --- |
| `TextLayoutCandidateDetector()` | `TextLayoutCandidateDetector` | 使用默认配置创建 detector。 |
| `TextLayoutCandidateDetector(config)` | `TextLayoutCandidateDetector` | 使用自定义 `TextLayoutDetectorConfig`。 |
| `detector.detect(reader)` | `tuple[ChapterCandidate, ...]` | 检测全部页面，只返回文本布局来源的候选。 |
| `detector.detect(reader, pages=(0, 5))` | `tuple[ChapterCandidate, ...]` | 只检测指定 0-based 页面。 |

### TextLayoutFeatures

| 字段 | 说明 |
| --- | --- |
| `text` | 轻量清理空白后的候选标题文本。 |
| `text_length` | 候选文本字符数。 |
| `page_index` | 0-based 页码。 |
| `block_index` | reader 返回的 `TextBlock.block_index`。 |
| `font_size` | block 内 span 字号的字符数加权平均。 |
| `body_font_size` | 当前检测范围内估计出的正文基准字号。 |
| `font_size_ratio` | `font_size / body_font_size`。 |
| `top_position_ratio` | `block.bbox.y0 / page_height`。 |
| `pattern_name` | 命中的标题模式名称，例如 `chinese_chapter`、`english_chapter`、`numeric`。 |

## Phase 7

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| 多来源候选融合 | `CandidateFusion` 接受任意来源的 `ChapterCandidate`，输出新的融合候选。 |
| 页码距离配置 | `CandidateFusionConfig.max_page_distance` 默认 `1`，相邻页候选可融合。 |
| 标题轻量规范化 | 融合前会统一大小写、折叠空白、弱化常见标点差异；中文标题会忽略空白差异。 |
| 章节编号辅助 | 支持提取 `Chapter 3`、`第 3 章`、`3 Introduction` 里的简单编号，编号冲突时不融合。 |
| 来源完整保留 | `ChapterCandidate.sources` 保存融合后的所有来源，`source` 保留为向后兼容的代表来源。 |
| 原始标题保留 | `ChapterCandidate.original_titles` 保存融合组中出现过的原始标题。 |
| Evidence 合并 | 融合候选保留所有来源的 `ChapterEvidence`，不重新计算 detector 内部证据分数。 |
| Manual 优先 | Manual 候选在代表标题、代表页码、代表来源上优先；但仍然只输出 `ChapterCandidate`。 |
| confidence 融合 | Manual 直接保持 `1.0`；非 Manual 使用最高输入置信度并按独立来源数量做小幅提升，结果限制在 `0.0 ~ 1.0`。 |
| 输入顺序无关 | 融合分组、代表选择和输出排序不依赖传入列表顺序。 |
| 输出排序 | 融合结果按 `start_page_index` 升序；同页时按 `confidence` 降序稳定排序。 |
| 同页不同标题保留 | 同一页出现 `Part I` 和 `Chapter 1` 这类不同候选时不会仅按页码去重。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| Candidate Ranking 独立层 | 暂不实现 |
| `ChapterCandidate -> Chapter` 自动确认或推导 | 暂不实现 |
| `Chapter -> SplitSegment` 边界解析 | 已在 Phase 9 作为独立领域层实现；Phase 7 不负责 |
| 语义相似标题融合 | 暂不实现 |
| 跨页标题合并 | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| GUI | 暂不实现 |

### Candidate Fusion API

| API | 返回 | 说明 |
| --- | --- | --- |
| `CandidateFusion()` | `CandidateFusion` | 使用默认配置创建融合器。 |
| `CandidateFusion(config)` | `CandidateFusion` | 使用自定义 `CandidateFusionConfig`。 |
| `fusion.fuse(candidates)` | `tuple[ChapterCandidate, ...]` | 融合候选并返回新的候选对象，不修改输入。 |
| `CandidateFusionConfig(max_page_distance=1)` | `CandidateFusionConfig` | 配置可融合候选的最大页码距离。 |

### Candidate Fusion 规则

| 项目 | 规则 |
| --- | --- |
| 分组条件 | `abs(page_a - page_b) <= max_page_distance`，并且标题规范化后相同；Manual 候选可按近邻页优先融合。 |
| 编号冲突 | 如果两个标题都能提取章节编号且编号不同，则不融合。 |
| 代表标题 | 按来源优先级选择：`MANUAL`、`TEXT_LAYOUT`、`OUTLINE`、`OCR`、`AI`。 |
| 代表页码 | 使用代表候选的 `start_page_index`，例如 Outline 与 TextLayout 相邻时优先 TextLayout 页码。 |
| 多来源表达 | `sources` 保存完整来源集合，按来源优先级排序。 |
| Evidence | 按证据类型、描述、页码、文本去重后保留。 |
| confidence | 取组内最高 confidence，多来源支持增加小幅 bonus，并用 `min(1.0, value)` 封顶。 |

## Phase 8

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| Candidate confirmation | `ChapterConfirmationService.accept(candidate)` 表示外部用户已经接受候选，并生成 `Chapter`。 |
| Candidate editing | `accept()` 支持传入修改后的 `title`、0-based `start_page_index` 或 1-based `start_page_number`。 |
| Candidate rejection | `ChapterConfirmationService.reject(candidate)` 记录拒绝动作，不生成 `Chapter`。 |
| Manual Chapter creation | `create_manual(title, start_page_number, level=1)` 支持无 Candidate 的用户直接新增确认章节。 |
| 批量确认 | `apply_decisions(decisions, page_count=None)` 处理接受、修改后接受和拒绝，并返回确认结果。 |
| Chapter validation | `Chapter` 校验标题、0-based 起始页和层级；`validate(page_count=...)` 可校验 PDF 页数边界。 |
| Chapter 集合验证 | `ChapterValidator().validate(chapters, page_count=None)` 校验重复起始页并按起始页排序。 |
| Candidate provenance | `Chapter.provenance` 保存候选标题、候选起始页、候选来源、confidence、原始标题和 Evidence 快照。 |
| Evidence traceability | 确认后的 `Chapter` 可以通过 provenance 追溯到 Candidate 的 Evidence。 |
| 输入不可变 | 确认服务生成新的 `Chapter`，不修改原始 `ChapterCandidate`。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| GUI | 暂不实现 |
| Chapter end page 字段 | 不实现，边界只存在于 `SplitSegment` |
| `Chapter -> SplitSegment` 的 CLI/GUI/PDFSplitter 集成 | 暂不实现 |
| PDF splitting | 暂不实现 |
| ZIP | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| 外部 API | 暂不实现 |

### Confirmation API

| API | 返回 | 说明 |
| --- | --- | --- |
| `ChapterConfirmationService().accept(candidate)` | `Chapter` | 接受候选，使用候选标题和 0-based 起始页。 |
| `accept(candidate, title=...)` | `Chapter` | 修改标题后接受，provenance 仍保留原候选标题。 |
| `accept(candidate, start_page_number=129)` | `Chapter` | 使用 1-based 用户页码修改起始页，内部转换为 `128`。 |
| `accept(candidate, start_page_index=128)` | `Chapter` | 使用内部 0-based 页码修改起始页。 |
| `reject(candidate)` | `ChapterConfirmationOutcome` | 记录拒绝动作，不产生 Chapter。 |
| `create_manual(title, start_page_number, level=1)` | `Chapter` | 用户直接新增确认章节，不需要 Candidate。 |
| `ChapterConfirmationDecision.accept(candidate, ...)` | `ChapterConfirmationDecision` | 批量确认中的接受/修改后接受动作。 |
| `ChapterConfirmationDecision.reject(candidate)` | `ChapterConfirmationDecision` | 批量确认中的拒绝动作。 |
| `apply_decisions(decisions, page_count=None)` | `ChapterConfirmationResult` | 返回 `accepted_chapters`、`rejected_candidates` 和每一步 `outcomes`。 |

### Chapter Provenance

| 字段 | 说明 |
| --- | --- |
| `candidate_title` | 被确认候选的代表标题；手动直接创建时为 `None`。 |
| `candidate_start_page_index` | 被确认候选的 0-based 起始页；手动直接创建时为 `None`。 |
| `candidate_sources` | 候选来源集合，例如 `OUTLINE`、`TEXT_LAYOUT`、`MANUAL`。 |
| `candidate_confidence` | 被确认候选的 confidence；手动直接创建时为 `None`。 |
| `candidate_evidences` | 被确认候选的 Evidence 快照。 |
| `candidate_original_titles` | 候选融合前后的原始标题快照。 |
| `confirmed_from_candidate` | 是否来自 Candidate；手动直接创建时为 `False`。 |

### Phase 8 边界

| 对象 | 当前语义 |
| --- | --- |
| `ChapterCandidate` | 系统认为这里可能是章节。 |
| `Chapter` | 用户已经确认这里是章节起点。 |
| `SplitSegment` | 已经确定要拆分的 PDF 页面范围，由 Phase 9 的边界推导生成。 |

## Phase 9

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| 确定性边界推导 | `ChapterBoundaryResolver` 将已经确认的 `Chapter[]` 转换为 `SplitSegment[]`，不重新识别章节。 |
| `page_count` 验证 | 拒绝 `page_count <= 0`，并拒绝超出 PDF 物理页范围的章节起点。 |
| 乱序输入处理 | 输入 `Chapter` 可乱序；resolver 会返回按 `start_page_index` 升序排列的结果，不修改原始输入。 |
| 重复起点验证 | 相同 `start_page_index` 的多个章节会被拒绝，避免产生空 segment 或静默合并。 |
| 半开区间语义 | 内部始终使用 0-based `[start_page_index, end_page_index)`。 |
| 最后章节延伸到 PDF 末尾 | 最后一个 `SplitSegment.end_page_index == page_count`。 |
| 不生成前置隐式 Segment | 第一个章节之前的封面、目录、前言等页面不会被自动拆成未确认 segment。 |
| 空章节输入 | `Chapter[]` 为空时返回空结果，不隐式生成整本 PDF segment。 |
| 标题传递 | `Chapter.title` 会传递给对应的 `SplitSegment.title`，但不做文件名清理。 |
| 来源追溯 | 通过 `BoundaryResolution(chapter, segment)` 保留确认章节与拆分区间的对应关系，不把 provenance 塞进 `SplitSegment`。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| CLI 集成 | 暂不实现 |
| GUI 集成 | 暂不实现 |
| PDFSplitter 调用 | 暂不实现 |
| ZIP | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| 自动新章节识别 | 暂不实现 |
| 印刷页码识别 | 暂不实现 |
| PDF 物理页码与印刷页码映射 | 暂不实现 |
| 复杂 PDF layout 处理 | 暂不实现 |

### Boundary Resolver API

| API | 返回 | 说明 |
| --- | --- | --- |
| `ChapterBoundaryResolver().resolve(chapters, page_count)` | `BoundaryResolutionResult` | 将已确认章节起点解析为拆分区间，只依赖 `Chapter[]` 和 PDF 总页数。 |
| `BoundaryResolutionResult.resolutions` | `tuple[BoundaryResolution, ...]` | 保存每个 `Chapter` 与对应 `SplitSegment` 的映射。 |
| `BoundaryResolutionResult.segments` | `tuple[SplitSegment, ...]` | 按起始页排序后的拆分区间。 |
| `BoundaryResolutionResult.source_chapters` | `tuple[Chapter, ...]` | 与 `segments` 顺序一致的来源章节。 |

### Boundary Resolver 规则

| 场景 | 规则 |
| --- | --- |
| 普通章节 | 对排序后的 `Chapter[i]`，`start = Chapter[i].start_page_index`。 |
| 非最后章节 | `end = Chapter[i + 1].start_page_index`。 |
| 最后章节 | `end = page_count`。 |
| 单章节 | 生成一个 `[chapter.start_page_index, page_count)` segment。 |
| 空章节 | 返回空 `BoundaryResolutionResult`。 |
| 第一个章节不是第一页 | 不生成 `[0, first_chapter.start_page_index)` 的前置 segment。 |
| 重复起点 | 抛出 `ValueError`。 |
| 非法页码 | 起点小于 `0` 或大于等于 `page_count` 时抛出 `ValueError`。 |

## Phase 10

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| Application Workflow | `PDFChapterWorkflow` 作为应用层编排入口，只串联已有 Reader、Detector、Fusion、Confirmation、Boundary、Splitter 和 ZIP 组件。 |
| PDF analysis orchestration | `analyze(input_path)` 打开 PDF，读取 `page_count`、metadata、outline，并调用 outline/text-layout detector 与 `CandidateFusion`。 |
| AnalysisResult | 保存 `input_path`、`page_count`、`metadata`、`candidates`；不包含 `Chapter`，不会自动确认。 |
| Candidate confirmation orchestration | `confirm(decisions, page_count=None)` 调用 `ChapterConfirmationService.apply_decisions()`，继续要求外部 caller 明确 accept/reject/edit。 |
| Chapter boundary orchestration | `resolve(chapters, page_count)` 调用 `ChapterBoundaryResolver`，只得到边界结果，不拆 PDF。 |
| Manual split path | `build_manual_segments(inputs)` 将用户 1-based 闭区间直接转换为 `SplitSegment`，不伪装成 `Chapter`。 |
| Split execution orchestration | `execute(input_path, segments, output_directory, zip_path=None)` 调用 `PDFSplitter` 执行拆分。 |
| ZIP execution orchestration | `zip_path` 存在时，`execute()` 在拆分后调用 `ZipCreator`。 |
| Automatic path | `process_confirmed_chapters()` 支持 `Chapter[] -> BoundaryResolver -> SplitSegment[] -> PDFSplitter -> optional ZIP`。 |
| Manual path | `process_manual_ranges()` 支持 `ManualSplitInput[] -> SplitSegment[] -> PDFSplitter -> optional ZIP`。 |
| ProcessingResult | 保存 `input_path`、`output_directory`、`split_result` 和可选 `zip_result`。 |
| 轻量依赖注入 | Workflow 构造函数允许替换 reader factory、detectors、fusion、confirmation、boundary、splitter 和 zip creator，便于测试和未来 GUI 调用。 |

当前尚未支持：

| 功能 | 状态 |
| --- | --- |
| GUI | 暂不实现 |
| CLI 自动章节工作流集成 | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| 外部 API | 暂不实现 |
| 基于 confidence 的自动确认 | 暂不实现 |
| 印刷页码识别 | 暂不实现 |
| PDF 物理页码与印刷页码映射 | 暂不实现 |
| 高级 PDF layout 处理 | 暂不实现 |

### Application Workflow API

| API | 返回 | 说明 |
| --- | --- | --- |
| `PDFChapterWorkflow().analyze(input_path)` | `AnalysisResult` | 分析 PDF，返回文本质量报告和融合后的候选，不产生 `Chapter`。 |
| `PDFChapterWorkflow().confirm(decisions, page_count=None)` | `ChapterConfirmationResult` | 应用外部用户确认决策，生成已确认 `Chapter`。 |
| `PDFChapterWorkflow().resolve(chapters, page_count)` | `BoundaryResolutionResult` | 将已确认章节起点转换为 `SplitSegment` 边界结果。 |
| `PDFChapterWorkflow().build_manual_segments(inputs)` | `tuple[SplitSegment, ...]` | 将手动页码范围直接转换为拆分区间。 |
| `PDFChapterWorkflow().execute(input_path, segments, output_directory, zip_path=None)` | `ProcessingResult` | 执行 PDF 拆分，并按需创建 ZIP。 |
| `PDFChapterWorkflow().process_confirmed_chapters(...)` | `ProcessingResult` | 自动章节路径在用户确认后的一步式编排入口。 |
| `PDFChapterWorkflow().process_manual_ranges(...)` | `ProcessingResult` | 手动页码拆分路径的一步式编排入口。 |

`AnalysisResult.text_quality_report` 保存 `PDFTextQualityReport`。它只描述 PDF 文本输入质量，不自动确认候选，也不改变 `Chapter` 或 `SplitSegment` 语义。

### 当前整体架构

```text
PDF
  ↓
Reader
  ↓
Candidate Detection
  ↓
Fusion
  ↓
User Confirmation
  ↓
Chapter
  ↓
Boundary Resolver
  ↓
SplitSegment
  ↓
PDFSplitter
  ↓
ZipCreator

Manual Page Range
  ↓
SplitSegment
  ↓
PDFSplitter
  ↓
ZipCreator
```

## Phase 11

当前已经验证：

| 验证项 | 说明 |
| --- | --- |
| Real PDF fixture | 测试运行时动态生成 10 页真实 PDF，不提交二进制 fixture。 |
| Real PDF analysis | `PDFChapterWorkflow().analyze(pdf_path)` 可通过真实 `PyMuPDFReader` 读取页数、metadata、outline 和文本布局。 |
| Real TextLayout detection | 真实 PDF 文本块可被 `TextLayoutCandidateDetector` 识别为 `ChapterCandidate`，并保留 confidence、sources、original_titles 和 evidence。 |
| Candidate extraction | 10 页 fixture 中的 `Chapter 1 Introduction`、`Chapter 2 Methods`、`Chapter 3 Results` 能稳定得到候选起点。 |
| 不自动确认 | `analyze()` 只返回候选，不产生 `Chapter` 或 accepted chapters，即使候选 confidence 很高。 |
| Manual PDF splitting | `process_manual_ranges()` 可用真实 PDF 生成多个实际输出 PDF。 |
| 输出 PDF 内容 | 输出 PDF 的页数正确，且首页文本对应原始 PDF 的目标页。 |
| ZIP generation | 手动拆分路径可生成真实 ZIP，并验证 ZIP 内 PDF 条目和解压后的 PDF 页数/内容。 |
| Automatic confirmation flow | 真实 `analyze()` 结果经过显式 `ChapterConfirmationDecision.accept()` 后，可 `resolve()` 为 `SplitSegment` 并继续真实拆分和 ZIP。 |
| Confirmed chapters path | 可跳过检测，直接用已确认 `Chapter[]` 跑通 `BoundaryResolver -> PDFSplitter -> ZIP`。 |
| Original PDF preservation | 拆分前后原始 PDF 页数和文件 hash 保持不变。 |
| Error propagation | 缺失 PDF 的 `PDFOpenError` 和边界错误的 `ValueError` 不会被 Workflow 吞掉或包装成泛化错误。 |

当前仍未实现：

| 功能 | 状态 |
| --- | --- |
| GUI | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| 外部 API | 暂不实现 |
| 自动确认 | 暂不实现 |
| 印刷页码识别 | 暂不实现 |
| PDF 物理页码与印刷页码映射 | 暂不实现 |
| 高级语义章节识别 | 暂不实现 |

### Phase 11 测试覆盖

| 测试组 | 覆盖 |
| --- | --- |
| Real PDF Analysis | 真实 PDF、真实 reader、真实 detector、真实 fusion。 |
| Real Manual Path | 真实 PDF、真实 `PDFSplitter`、真实输出 PDF。 |
| Real ZIP | 真实 `ZipCreator`、ZIP 条目、解压后 PDF 可读性。 |
| Automatic Path Smoke | 真实候选分析、显式确认、边界推导、真实拆分、真实 ZIP。 |
| Safety Regression | 不自动确认、不修改原始 PDF、不吞掉底层异常。 |

## Phase 12

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| WorkflowStage | 应用层阶段标签，用于表达 workflow 当前正在进行的高层业务阶段，不是状态机。 |
| ProgressEvent | 不可变事件快照，包含 `stage`、`message`、可选 `current`、可选 `total`。 |
| progress listener | `PDFChapterWorkflow(progress_listener=listener)` 支持同步回调，供未来 GUI/CLI 观察进度。 |
| listener 隔离 | listener 自身抛异常时不会中断 PDF 分析、拆分或 ZIP 业务流程。 |
| ApplicationError | 应用层错误基类，提供 `stage`、`message`、`cause`。 |
| WorkflowError | 应用层 workflow 错误，继承 `ApplicationError`，保留旧 API 中 `WorkflowError` 名称。 |
| cause 保留 | execute 阶段包装已知底层错误时使用 `raise ... from exc`，同时保存 `error.cause`。 |
| 错误阶段 | 空 segments 和 split 失败标记为 `SPLITTING`；ZIP 失败标记为 `CREATING_ZIP`。 |
| 兼容旧异常语义 | `analyze()` 的 `PDFOpenError` 和 `resolve()` 的边界 `ValueError` 继续原样传播，不被泛化包装。 |

当前仍未实现：

| 功能 | 状态 |
| --- | --- |
| GUI | 暂不实现 |
| async progress | 暂不实现 |
| cancellation | 暂不实现 |
| threading | 暂不实现 |
| multiprocessing | 暂不实现 |
| logging framework | 暂不实现 |
| event bus / observable framework | 暂不实现 |
| retry framework | 暂不实现 |
| OCR | 暂不实现 |
| AI / embedding | 暂不实现 |
| 外部 API / 网络服务 | 暂不实现 |

### WorkflowStage

| Stage | 语义 |
| --- | --- |
| `READING_PDF` | 正在打开或读取 PDF 基础信息。 |
| `ANALYZING` | 正在调用候选 detector。 |
| `FUSING_CANDIDATES` | 正在融合候选。 |
| `WAITING_FOR_CONFIRMATION` | 候选分析完成，等待外部 caller 提供确认决策；Workflow 不阻塞等待用户。 |
| `CONFIRMING` | 正在应用外部确认决策。 |
| `CONFIRMED` | 确认决策已应用。 |
| `RESOLVING_BOUNDARIES` | 正在将 `Chapter[]` 推导为 `SplitSegment[]`。 |
| `RESOLVED` | 边界推导完成。 |
| `SPLITTING` | 正在调用 `PDFSplitter`。 |
| `CREATING_ZIP` | 正在调用 `ZipCreator`。 |
| `EXECUTION_COMPLETED` | `execute()` 完成拆分与可选 ZIP。 |
| `FAILED` | 保留给应用层错误或未来失败事件语义。 |

### Progress Event 顺序

| Workflow 方法 | 事件顺序 |
| --- | --- |
| `analyze()` | `READING_PDF -> ANALYZING -> FUSING_CANDIDATES -> WAITING_FOR_CONFIRMATION` |
| `confirm()` | `CONFIRMING -> CONFIRMED` |
| `resolve()` | `RESOLVING_BOUNDARIES -> RESOLVED` |
| `execute(..., zip_path=None)` | `SPLITTING -> EXECUTION_COMPLETED` |
| `execute(..., zip_path=...)` | `SPLITTING -> CREATING_ZIP -> EXECUTION_COMPLETED` |
| `process_manual_ranges(..., zip_path=...)` | `SPLITTING -> CREATING_ZIP -> EXECUTION_COMPLETED` |

### Error Contract

| 场景 | 行为 |
| --- | --- |
| Workflow 自身非法调用 | 抛 `WorkflowError`，例如空 `segments`，`stage=SPLITTING`，`cause=None`。 |
| PDF split 已知底层错误 | 包装为 `WorkflowError(stage=SPLITTING, cause=原始异常)`，并保留 `__cause__`。 |
| ZIP 已知底层错误 | 包装为 `WorkflowError(stage=CREATING_ZIP, cause=原始异常)`，并保留 `__cause__`。 |
| PDF 打开失败 | `analyze()` 继续原样抛出 `PDFOpenError`，保持 Phase 10/11 API 兼容。 |
| 边界推导失败 | `resolve()` 继续原样抛出 `ValueError`，保持 Phase 9/10/11 API 兼容。 |
| 编程错误 | `AttributeError`、`TypeError` 等不被包装，避免隐藏真实 bug。 |

### 未来调用模型

```text
Future GUI / CLI
  ↓
PDFChapterWorkflow(progress_listener=listener)
  ↓
ProgressEvent → Future GUI / CLI

PDFChapterWorkflow
  ↓
ApplicationError / WorkflowError
  ↓
underlying cause
```

## Phase 13

当前已经支持：

| 能力 | 说明 |
| --- | --- |
| WorkflowSession | 位于 application 层的轻量会话对象，为未来 GUI 保存一次用户操作的状态和中间结果。 |
| SessionState | 描述整个用户工作流状态，独立于 Phase 12 的 `WorkflowStage`。 |
| Workflow 委托 | Session 只调用 `PDFChapterWorkflow`，不直接读取 PDF、不识别章节、不推导边界、不拆 PDF、不创建 ZIP。 |
| Candidate 确认入口 | 提供 `accept_candidate()`、`reject_candidate()`、`confirm()`，内部继续委托 `PDFChapterWorkflow.confirm()`。 |
| Resolve 入口 | `resolve()` 使用已确认 `Chapter[]` 和 analysis 的 `page_count` 委托 `PDFChapterWorkflow.resolve()`。 |
| Execute 入口 | `execute(output_directory=..., zip_path=...)` 只委托 `PDFChapterWorkflow.execute()`。 |
| Manual Path | `process_manual_ranges()` 只委托 `PDFChapterWorkflow.process_manual_ranges()`，不在 Session 内解析或拆分 PDF。 |
| Progress 转发 | `WorkflowSession(progress_listener=listener)` 继续使用现有 `ProgressEvent` / `WorkflowStage`，不定义第二套事件。 |
| 错误保存 | 失败时保存 `session.error` 并进入 `SessionState.FAILED`；成功路径会清空旧错误。 |
| 非法顺序保护 | `resolve()`、`execute()` 等明显错误调用会抛 `InvalidSessionStateError`。 |
| 重新 analyze | 允许重新选择 PDF，并清理上一轮 analysis、confirmation、boundary、processing 和 error 数据。 |

当前仍未实现：

| 功能 | 状态 |
| --- | --- |
| GUI | 暂不实现 |
| Tkinter / PyQt / PySide 界面 | 暂不实现 |
| Web UI / HTTP server | 暂不实现 |
| async / asyncio | 暂不实现 |
| threading / cancellation | 暂不实现 |
| persistence / database | 暂不实现 |
| logging framework | 暂不实现 |
| OCR | 暂不实现 |
| AI / LLM / embedding | 暂不实现 |
| 外部 API / 网络服务 | 暂不实现 |

### Session API

| API | 返回 | 说明 |
| --- | --- | --- |
| `WorkflowSession(workflow=None, progress_listener=None)` | `WorkflowSession` | 默认创建 `PDFChapterWorkflow`；测试或未来上层可注入 workflow。 |
| `session.analyze(input_path)` | `AnalysisResult` | 分析 PDF 并保存 `input_path`、`analysis_result`、`candidates`。 |
| `session.accept_candidate(candidate, title=None, start_page_index=None, start_page_number=None)` | `ChapterConfirmationResult` | 接受单个候选，可带 GUI 编辑后的标题或页码。 |
| `session.reject_candidate(candidate)` | `ChapterConfirmationResult` | 拒绝单个候选；没有任何 accepted chapter 时继续等待确认。 |
| `session.confirm(decisions)` | `ChapterConfirmationResult` | 批量应用外部确认决策。 |
| `session.resolve()` | `BoundaryResolutionResult` | 将已确认章节委托 workflow 解析为 `SplitSegment[]`。 |
| `session.execute(output_directory=..., zip_path=None)` | `ProcessingResult` | 对已解析 segments 执行拆分和可选 ZIP。 |
| `session.process_manual_ranges(input_path, manual_inputs, output_directory, zip_path=None)` | `ProcessingResult` | 直接执行手动页码范围路径。 |

### SessionState

| State | 语义 |
| --- | --- |
| `IDLE` | 尚未开始一次用户工作流。 |
| `ANALYZING` | 正在委托 workflow 分析 PDF。 |
| `WAITING_FOR_CONFIRMATION` | 候选已产生，等待外部 caller 接受或拒绝。 |
| `CONFIRMING` | 正在委托 workflow 应用确认决策。 |
| `READY_TO_RESOLVE` | 已有 accepted chapter，可以解析边界。 |
| `RESOLVING` | 正在委托 workflow 解析章节边界。 |
| `READY_TO_EXECUTE` | 已有 `SplitSegment[]`，可以执行拆分。 |
| `EXECUTING` | 正在委托 workflow 执行拆分和可选 ZIP。 |
| `COMPLETED` | 当前用户工作流执行完成。 |
| `FAILED` | 当前用户工作流失败，`session.error` 保存应用层错误。 |

### Session 状态转换

| 操作 | 成功转换 |
| --- | --- |
| `analyze()` | `IDLE/WAITING_FOR_CONFIRMATION/COMPLETED/FAILED/... -> ANALYZING -> WAITING_FOR_CONFIRMATION` |
| `accept_candidate()` | `WAITING_FOR_CONFIRMATION/READY_TO_RESOLVE -> CONFIRMING -> READY_TO_RESOLVE` |
| `reject_candidate()` | `WAITING_FOR_CONFIRMATION/READY_TO_RESOLVE -> CONFIRMING -> WAITING_FOR_CONFIRMATION`，当没有 accepted chapter 时继续等待。 |
| `confirm()` | `WAITING_FOR_CONFIRMATION/READY_TO_RESOLVE -> CONFIRMING -> READY_TO_RESOLVE`，当没有 accepted chapter 时回到 `WAITING_FOR_CONFIRMATION`。 |
| `resolve()` | `READY_TO_RESOLVE -> RESOLVING -> READY_TO_EXECUTE` |
| `execute()` | `READY_TO_EXECUTE -> EXECUTING -> COMPLETED` |
| `process_manual_ranges()` | `IDLE/... -> EXECUTING -> COMPLETED` |
| 非法调用 | 抛 `InvalidSessionStateError`，并进入 `FAILED`。 |

### Session 架构关系

```text
Future GUI
  ↓
WorkflowSession
  ↓
PDFChapterWorkflow
  ↓
Existing Domain/Application Services

PDF
  ↓
Reader
  ↓
Candidate Detection
  ↓
Candidate Fusion
  ↓
User Confirmation
  ↓
Chapter
  ↓
Boundary Resolution
  ↓
SplitSegment
  ↓
PDF Split
  ↓
ZIP
  ↓
ProcessingResult
```

## Phase 14 — GUI MVP

当前已经支持一个最小但完整可操作的 PySide6 桌面界面：

| 能力 | 说明 |
| --- | --- |
| PDF 选择 | 通过「选择 PDF」按钮选择本地 PDF，并调用 `WorkflowSession.analyze()`。 |
| Candidate 展示 | 候选列表显示标题、1-based 页码、confidence、sources 和 Evidence 摘要。 |
| Evidence 展示 | 选择候选后在详情区域查看候选 Evidence 摘要。 |
| Accept / Reject / Edit | 用户可编辑标题和起始页，再明确接受候选；也可拒绝候选。 |
| Manual Chapter | 用户可输入标题、起始页和 level，通过 Session 添加手动确认章节。 |
| Chapter Confirmation | 已确认章节列表显示标题、1-based 起始页、level 和来源。 |
| Boundary Resolution | 点击「开始拆分」时先通过 Session 委托 workflow 解析边界。 |
| PDF Split | 边界解析后通过 Session 委托 workflow 执行 PDF 拆分。 |
| ZIP | 勾选「生成 ZIP」并填写路径后，由 workflow 执行 ZIP 创建。 |
| Progress | GUI 复用 `ProgressEvent` / `WorkflowStage`，显示阶段消息和可用的 current / total。 |
| Error Display | GUI 显示 `ApplicationError` 的 message、stage 和 cause 摘要。 |
| 后台执行 | PDF 分析、拆分和 ZIP 使用最小 `threading.Thread + queue.Queue + QTimer`，工作线程不直接修改 Qt widget。 |
| 启动入口 | 可通过 `python -m pdf_chapter_splitter.gui` 启动桌面 GUI。 |

当前仍未实现：

| 功能 | 状态 |
| --- | --- |
| OCR | 暂不实现 |
| AI / LLM / embedding | 暂不实现 |
| PDF Preview / PDF 渲染预览 | 暂不实现 |
| Cancel / pause / resume | 暂不实现 |
| 多任务并行 / 任务队列 | 暂不实现 |
| 云服务 / 外部 API / 网络服务 | 暂不实现 |
| 数据库 / 持久化 | 暂不实现 |
| 用户系统 | 暂不实现 |
| 自动确认章节 | 暂不实现 |
| 自动修改用户决策 | 暂不实现 |
| 修改 `Chapter` 语义或恢复 `Chapter.end_page_index` | 不实现 |
| 高级 UI / PDF 在线预览 | 暂不实现 |

### GUI 依赖关系

GUI 代码保持为 Application Layer 的消费者：

```text
GUI
 ↓
WorkflowSession
 ↓
PDFChapterWorkflow
 ↓
┌───────────────┬──────────────┬──────────────┐
│ Chapters      │ PDF Reader   │ Processing   │
│ Detector      │ PyMuPDF      │ Splitter     │
│ Fusion        │              │ ZIP Creator  │
│ Confirmation  │              │              │
│ Boundary      │              │              │
└───────────────┴──────────────┴──────────────┘
```

### GUI 模块结构

| 模块 | 职责 |
| --- | --- |
| `pdf_chapter_splitter.gui.presenters` | 将 application/domain 返回对象转换为 GUI 展示文本，不执行业务逻辑。 |
| `pdf_chapter_splitter.gui.adapter` | 将 GUI 操作转发给 `WorkflowSession`，不调用底层模块。 |
| `pdf_chapter_splitter.gui.app` | PySide6 窗口、控件、后台任务队列、进度和错误展示。 |
| `pdf_chapter_splitter.gui.__main__` | GUI 启动入口。 |

## Phase 15B — PDF Input Quality Diagnostic + Candidate Quality Governance

Phase 15B 基于真实 PDF 黑盒验证结果，新增输入质量诊断和候选质量治理。它只提供可解释信号，不做 OCR、不接 AI、不自动确认、不删除用户可能需要的候选。

### PDF 文本质量诊断

| API / 模型 | 位置 | 说明 |
| --- | --- | --- |
| `PDFTextQualityDiagnostic().analyze(reader)` | `pdf_chapter_splitter.pdf` | 使用现有 `PDFReader` 的 `page_count`、`get_all_page_text()` 和 metadata 输出文本质量报告。 |
| `PDFTextQualityReport` | `pdf_chapter_splitter.pdf` | 不可变报告，包含页数、文本覆盖率、字符数、可读页比例、质量等级和 warnings。 |
| `PDFTextQualityLevel` | `pdf_chapter_splitter.pdf` | 文本质量等级：`HIGH`、`MEDIUM`、`LOW`、`NONE`。 |
| `AnalysisResult.text_quality_report` | `pdf_chapter_splitter.application` | `PDFChapterWorkflow.analyze()` 返回的输入质量报告。 |

### PDFTextQualityReport 字段

| 字段 | 说明 |
| --- | --- |
| `page_count` | PDF 总页数。 |
| `pages_with_text` | 至少有非空可提取文本的页面数。 |
| `text_coverage_ratio` | `pages_with_text / page_count`。 |
| `total_characters` | 所有非空白提取文本字符数。 |
| `average_characters_per_text_page` | 有文本页面的平均字符数。 |
| `readable_page_ratio` | 被判定为可读文本页面的比例。 |
| `quality_level` | `HIGH`、`MEDIUM`、`LOW` 或 `NONE`。 |
| `likely_scanned` | 无文本或几乎无文本时标记可能是扫描 PDF。 |
| `likely_ocr` | metadata 或字符噪声显示可能来自 OCR 时标记。 |
| `warnings` | 可解释 warning，例如 `no_extractable_text`、`weak_text_layer`、`ocr_noise_suspected`。 |

### 文本质量等级规则

| 等级 | 规则 |
| --- | --- |
| `HIGH` | 文本覆盖率和可读页比例都达到高阈值，且未发现 OCR 噪声。 |
| `MEDIUM` | 文本覆盖率达到中等阈值、可读页比例仍可用，且未发现 OCR 噪声。 |
| `LOW` | 存在文本但覆盖率低、可读页比例低或疑似 OCR 噪声。 |
| `NONE` | 没有任何可提取文本。 |

### TOC Page Detection

| API / 模型 | 位置 | 说明 |
| --- | --- | --- |
| `TOCPageDetector().classify_reader_page(reader, page_index)` | `pdf_chapter_splitter.chapters` | 对单页文本做目录页分类。 |
| `TOCPageClassification` | `pdf_chapter_splitter.chapters` | 保存 `page_index`、`is_toc_page`、`confidence` 和 evidence。 |
| `TOCPageEvidenceType` | `pdf_chapter_splitter.chapters` | 目录页证据类型。 |

TOC 检测使用轻量确定性规则：

| Evidence | 触发含义 |
| --- | --- |
| `detected_contents_heading` | 页面前部出现 `Contents`、`Table of Contents` 或 `目录`。 |
| `chapter_entry_density` | 页面中出现多个 `Chapter N`、`第 N 章` 或数字章节条目。 |
| `dotted_leader_pattern` | 出现类似 `Chapter 1 ...... 12` 的点线页码结构。 |
| `page_number_pattern` | 多行条目末尾带页码。 |
| `title_candidate_density` | 疑似章节条目在页面文本行中占比较高。 |

当 `TextLayoutCandidateDetector` 发现候选来自疑似 TOC 页时，会保留候选，但添加 `ChapterEvidenceType.TOC_PAGE_SUSPECTED`，并添加 `ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED`，同时降低 confidence。它不会删除候选。

### Outline Quality Governance

| API / 模型 | 位置 | 说明 |
| --- | --- | --- |
| `OutlineQualityClassifier().classify(title)` | `pdf_chapter_splitter.chapters` | 对 outline 标题做结构类型与标题质量判断。 |
| `OutlineCandidateQuality` | `pdf_chapter_splitter.chapters` | 保存结构类型、建议 confidence、quality flags 和 evidence。 |
| `ChapterStructureType` | `pdf_chapter_splitter.chapters` | 候选结构类型。 |
| `ChapterCandidateQualityFlag` | `pdf_chapter_splitter.chapters` | 候选质量标记。 |

Outline 结构分类规则：

| 类型 | 示例 | 行为 |
| --- | --- | --- |
| `PRIMARY_CHAPTER` | `Chapter 1`、`第 N 章`、`1 Introduction` | 优先视为主章节候选。 |
| `SECTION` | `1.1 Motivation`、`第一节` | 保留候选，但标记为非一级章节结构。 |
| `SUBSECTION` | `1.1.1 Detail` | 保留候选，但标记为更低层结构。 |
| `PART` | `Part I`、`第Ⅰ部分` | 保留候选，但不盲目视为主章节。 |
| `FRONT_MATTER` | `Preface`、`目录`、`版权信息` | 保留候选并标记为前置内容。 |
| `BACK_MATTER` | `References`、`Index`、`Appendix`、`附录` | 保留候选并标记为后置内容。 |
| `UNKNOWN` | 无法可靠判断的标题 | 保留候选并标记未知。 |

对于 DOI、文件名式标题，例如 `10.1525_9780520386976-001`，会添加 `POOR_TITLE_QUALITY` 和 `DOI_OR_FILE_TITLE`。Outline 候选会保留原始标题、页码、level 和 `OUTLINE` evidence，并额外增加 `OUTLINE_STRUCTURE` / `OUTLINE_TITLE_QUALITY` evidence。

### Candidate 质量字段

| 字段 | 说明 |
| --- | --- |
| `ChapterCandidate.structure_type` | 默认 `UNKNOWN`；Outline 候选会填入结构分类。 |
| `ChapterCandidate.quality_flags` | 默认空 tuple；用于保存 `toc_page_suspected`、`poor_title_quality` 等信号。 |

`CandidateFusion` 会保留并合并 `quality_flags`，并尽量保留更有用的 `structure_type`。原有 `source`、`sources`、`original_titles` 和 `evidences` 语义保持不变。

当前仍未实现：

| 功能 | 状态 |
| --- | --- |
| OCR | 暂不实现 |
| AI / LLM / embedding | 暂不实现 |
| 外部 API / 网络服务 | 暂不实现 |
| Candidate 自动确认 | 暂不实现 |
| `Chapter -> SplitSegment` 新逻辑 | 不在本阶段修改 |
| PDFSplitter / ZipCreator 修改 | 不在本阶段修改 |
| GUI 大改 | 暂不实现 |
| 自动删除低质量候选 | 不实现，低质量候选只标记、不删除 |

## Phase 16 — Analysis Summary & Candidate Filtering Strategy

Phase 16 将 Phase 15B 已有的质量信号整理为用户可理解的分析摘要，并提供候选展示策略。它不改章节识别算法，不自动确认章节，不删除候选。

### Analysis Summary

| API / 模型 | 位置 | 说明 |
| --- | --- | --- |
| `AnalysisSummary` | `pdf_chapter_splitter.application` | 面向应用层和 GUI 的分析摘要，统计候选数量、主要章节候选、TOC 可疑候选、低质量候选、标题质量和来源分布。 |
| `AnalysisResult.summary` | `pdf_chapter_splitter.application` | `PDFChapterWorkflow.analyze()` 在候选融合后生成的摘要；原有 `candidates` 和 `text_quality_report` 保持存在。 |

### AnalysisSummary 字段

| 字段 | 说明 |
| --- | --- |
| `text_quality_report` | 复用 Phase 15B 的 `PDFTextQualityReport`，不复制文本质量模型。 |
| `candidate_count` | 当前 fused candidates 总数。 |
| `primary_chapter_candidate_count` | `structure_type == PRIMARY_CHAPTER` 的候选数。 |
| `toc_suspected_candidate_count` | 带 `TOC_PAGE_SUSPECTED` flag 的候选数。 |
| `low_quality_candidate_count` | 低 confidence、非一级结构或带严重 quality flag 的候选数。 |
| `poor_title_candidate_count` | 带 `POOR_TITLE_QUALITY` flag 的候选数。 |
| `manual_candidate_count` | 来源中包含 `MANUAL` 的候选数。 |
| `outline_candidate_count` | 来源中包含 `OUTLINE` 的候选数。 |
| `text_layout_candidate_count` | 来源中包含 `TEXT_LAYOUT` 的候选数。 |
| `fused_candidate_count` | 融合后的候选数量，目前与 `candidate_count` 一致。 |

### Candidate Presentation Policy

| API / 模型 | 位置 | 说明 |
| --- | --- | --- |
| `CandidatePresentationPolicy.present(candidates, show_all=False)` | `pdf_chapter_splitter.application` | 将候选转换为展示记录，决定默认可见、折叠或隐藏。 |
| `CandidatePresentation` | `pdf_chapter_splitter.application` | 保存 `candidate`、`visible`、`collapsed`、`hidden_by_default` 和 `display_reason`。 |

默认策略：

| 候选类型 | 默认展示 |
| --- | --- |
| `PRIMARY_CHAPTER` | 显示 |
| `MANUAL` 来源 | 显示 |
| 高 confidence 且无严重质量 flag | 显示 |
| `TOC_PAGE_SUSPECTED` | 默认隐藏/折叠，但保留 |
| `NON_PRIMARY_STRUCTURE`、section、subsection、front matter、back matter、part | 默认隐藏/折叠，但保留 |
| `POOR_TITLE_QUALITY` 或低 confidence | 默认隐藏/折叠，但保留 |

如果一个候选同时是 `PRIMARY_CHAPTER` 且带 `TOC_PAGE_SUSPECTED`，GUI 默认仍显示该候选，并在展示原因中说明它位于疑似目录页。

Filtering / collapsing candidates is a presentation concern, not deletion or confirmation.

### GUI 质量展示

| GUI 能力 | 说明 |
| --- | --- |
| PDF Quality Banner | 显示 `PDF Analysis Quality`、文本覆盖率、可读页比例、OCR 风险和 warnings。 |
| Candidate 表格增强 | 候选表格现在显示标题、页码、confidence、structure、sources、quality flags 和 Evidence。 |
| 默认候选过滤 | 默认只显示主章节、人工候选或高 confidence 且质量较好的候选。 |
| 显示全部候选 | 用户可勾选“显示全部候选”，查看被默认隐藏/折叠的候选。 |
| Evidence 详情 | 继续复用已有 `ChapterEvidence`，不生成第二套解释数据。 |

### Phase 16 边界

| 未实现内容 | 状态 |
| --- | --- |
| OCR | 暂不实现 |
| AI / LLM / embedding | 暂不实现 |
| semantic similarity / semantic ranking | 暂不实现 |
| 外部 API / 网络服务 / 云服务 | 暂不实现 |
| 数据库 / 持久化 | 暂不实现 |
| PDF Preview / PDF 渲染预览 | 暂不实现 |
| cancellation / pause / resume | 暂不实现 |
| 自动确认 Candidate | 不实现 |
| 自动生成 Chapter | 不实现 |
| 自动生成 SplitSegment | 不实现 |
| 修改 `ChapterBoundaryResolver` | 不实现 |
| 修改 `PDFSplitter` / `ZipCreator` | 不实现 |

Phase 16 继续遵守：

```text
Detection
  ↓
Fusion
  ↓
Quality / Summary
  ↓
Presentation / Filtering
  ↓
Human Decision
  ↓
Confirmation
  ↓
Chapter
  ↓
Boundary Resolution
  ↓
SplitSegment
```

## 开发环境

要求 Python 3.12+。

安装开发依赖：

```powershell
python -m pip install -e ".[dev]"
```

运行测试：

```powershell
python -m pytest
```
