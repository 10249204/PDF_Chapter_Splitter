from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_chapter_splitter.chapters import (
    ChapterCandidateSource,
    ChapterEvidenceType,
    TextLayoutCandidateDetector,
    TextLayoutDetectorConfig,
)
from pdf_chapter_splitter.pdf import BoundingBox, PageSize, PyMuPDFReader, TextBlock, TextLine, TextSpan


def test_text_layout_detector_detects_chinese_chapter_with_explanatory_evidence(
):
    reader = _LayoutReader(
        [
            [
                _block("第 3 章 文件系统", y=72, size=20, block_index=0),
                _block(_body_text("文件系统用于组织和保存数据。"), y=118, size=11, block_index=1),
            ],
            [
                _block(_body_text("这一页只是普通正文内容。"), y=72, size=11, block_index=0),
            ],
        ]
    )

    candidates = TextLayoutCandidateDetector().detect(reader)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "第 3 章 文件系统"
    assert candidate.start_page_index == 0
    assert candidate.source is ChapterCandidateSource.TEXT_LAYOUT
    assert candidate.confidence >= TextLayoutDetectorConfig().min_confidence
    assert candidate.level == 1
    evidence_types = {evidence.evidence_type for evidence in candidate.evidences}
    assert ChapterEvidenceType.TEXT_PATTERN in evidence_types
    assert ChapterEvidenceType.FONT_SIZE in evidence_types
    assert ChapterEvidenceType.POSITION in evidence_types
    assert any("font_size=20.0" in evidence.description for evidence in candidate.evidences)
    assert any("body_font_size=11.0" in evidence.description for evidence in candidate.evidences)


def test_text_layout_detector_ignores_plain_body_and_numbered_sentence(tmp_path: Path):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("1. First, we define the storage model.", y=72, size=11),
                _Text(_body_text("This is ordinary body text with normal font size."), y=104, size=11),
            ]
        ],
    )

    with PyMuPDFReader(path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    assert candidates == ()


def test_text_layout_detector_detects_english_and_numeric_titles_without_fixed_font_size(
    tmp_path: Path,
):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("Chapter 2 Data Structures", y=72, size=15),
                _Text(_body_text("Linked lists and trees are introduced here."), y=116, size=9),
            ],
            [
                _Text("3 Algorithms", y=72, size=20),
                _Text(_body_text("Sorting and searching are discussed here."), y=122, size=12),
            ],
        ],
    )

    with PyMuPDFReader(path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    assert [candidate.title for candidate in candidates] == [
        "Chapter 2 Data Structures",
        "3 Algorithms",
    ]
    assert [candidate.start_page_index for candidate in candidates] == [0, 1]


def test_text_layout_detector_does_not_treat_subsections_as_chapters_by_default(
    tmp_path: Path,
):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("1.1 Motivation", y=72, size=20),
                _Text(_body_text("Motivation appears as a subsection."), y=116, size=11),
            ],
            [
                _Text("第一节 研究背景", y=72, size=20),
                _Text(_body_text("这一节默认不作为一级章节候选。"), y=116, size=11),
            ],
        ],
    )

    with PyMuPDFReader(path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    assert candidates == ()


def test_text_layout_detector_can_include_chinese_sections_when_configured():
    reader = _LayoutReader(
        [
            [
                _block("第一节 研究背景", y=72, size=20, block_index=0),
                _block(_body_text("这一节在显式配置后可以作为候选。"), y=116, size=11, block_index=1),
            ]
        ]
    )

    candidates = TextLayoutCandidateDetector(
        TextLayoutDetectorConfig(include_sections=True)
    ).detect(reader)

    assert [candidate.title for candidate in candidates] == ["第一节 研究背景"]


def test_text_layout_detector_honors_min_confidence_threshold(tmp_path: Path):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("Chapter 4 Low Contrast", y=72, size=11),
                _Text(_body_text("The heading uses the same size as body text."), y=116, size=11),
            ]
        ],
    )

    with PyMuPDFReader(path) as reader:
        relaxed_candidates = TextLayoutCandidateDetector(
            TextLayoutDetectorConfig(min_confidence=0.60)
        ).detect(reader)
        strict_candidates = TextLayoutCandidateDetector(
            TextLayoutDetectorConfig(min_confidence=0.75)
        ).detect(reader)

    assert [candidate.title for candidate in relaxed_candidates] == ["Chapter 4 Low Contrast"]
    assert strict_candidates == ()


def test_text_layout_detector_detects_non_top_chapter_when_pattern_and_font_are_strong(
    tmp_path: Path,
):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text(_body_text("The page starts with a preface paragraph."), y=72, size=11),
                _Text("Chapter 5: Storage", y=360, size=20),
                _Text(_body_text("The chapter continues after the heading."), y=410, size=11),
            ]
        ],
    )

    with PyMuPDFReader(path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    assert [candidate.title for candidate in candidates] == ["Chapter 5: Storage"]


def test_text_layout_detector_honors_pages_parameter_and_does_not_read_outline(
    tmp_path: Path,
):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("Chapter 1 Skipped", y=72, size=20),
                _Text(_body_text("Body text on skipped page."), y=116, size=11),
            ],
            [
                _Text("Chapter 2 Included", y=72, size=20),
                _Text(_body_text("Body text on included page."), y=116, size=11),
            ],
        ],
    )

    with PyMuPDFReader(path) as reader:
        reader_without_outline = _ReaderWithoutOutline(reader)
        candidates = TextLayoutCandidateDetector().detect(reader_without_outline, pages=(1,))

    assert [candidate.title for candidate in candidates] == ["Chapter 2 Included"]
    assert [candidate.start_page_index for candidate in candidates] == [1]


def test_text_layout_detector_rejects_common_non_chapter_false_positives(tmp_path: Path):
    path = _make_pdf(
        tmp_path,
        [
            [
                _Text("Table 1", y=72, size=20),
                _Text("Figure 2", y=112, size=20),
                _Text("Example 3", y=152, size=20),
                _Text("Copyright 2026", y=192, size=20),
                _Text("References", y=232, size=20),
                _Text(_body_text("These labels should not become chapters."), y=280, size=11),
            ]
        ],
    )

    with PyMuPDFReader(path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    assert candidates == ()


@pytest.mark.parametrize(
    "page_index",
    [-1, 2],
)
def test_text_layout_detector_rejects_out_of_range_pages(text_pdf_path: Path, page_index: int):
    with PyMuPDFReader(text_pdf_path) as reader:
        with pytest.raises(ValueError):
            TextLayoutCandidateDetector().detect(reader, pages=(page_index,))


class _ReaderWithoutOutline:
    def __init__(self, reader: PyMuPDFReader) -> None:
        self._reader = reader

    @property
    def page_count(self) -> int:
        return self._reader.page_count

    def get_page_text_blocks(self, page_index: int):
        return self._reader.get_page_text_blocks(page_index)

    def get_page_size(self, page_index: int):
        return self._reader.get_page_size(page_index)

    def get_outline(self):
        raise AssertionError("TextLayoutCandidateDetector must not read outline")


class _LayoutReader:
    def __init__(self, pages: list[list[TextBlock]]) -> None:
        self._pages = pages

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def get_page_text_blocks(self, page_index: int):
        return self._pages[page_index]

    def get_page_size(self, page_index: int):
        return PageSize(width=595, height=842)

    def get_outline(self):
        raise AssertionError("TextLayoutCandidateDetector must not read outline")


class _Text:
    def __init__(self, text: str, y: float, size: float) -> None:
        self.text = text
        self.y = y
        self.size = size


def _body_text(seed: str) -> str:
    return " ".join([seed] * 12)


def _make_pdf(tmp_path: Path, pages: list[list[_Text]]) -> Path:
    path = tmp_path / "layout-candidates.pdf"
    document = fitz.open()

    for page_items in pages:
        page = document.new_page(width=595, height=842)
        for item in page_items:
            page.insert_text((72, item.y), item.text, fontsize=item.size, fontname="helv")

    document.save(path)
    document.close()
    return path


def _block(text: str, y: float, size: float, block_index: int) -> TextBlock:
    width = max(40.0, len(text) * size * 0.55)
    bbox = BoundingBox(72, y, 72 + width, y + size * 1.4)
    span = TextSpan(
        text=text,
        bbox=bbox,
        font_size=size,
        font_name="test-font",
        block_index=block_index,
        line_index=0,
        span_index=0,
    )
    line = TextLine(
        bbox=bbox,
        block_index=block_index,
        line_index=0,
        spans=(span,),
    )
    return TextBlock(bbox=bbox, block_index=block_index, lines=(line,))
