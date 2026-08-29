from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QAbstractItemView, QCheckBox, QGroupBox, QLabel, QPushButton
except Exception:  # pragma: no cover - depends on local GUI runtime availability
    QApplication = None
    QAbstractItemView = None
    QCheckBox = None
    QGroupBox = None
    QLabel = None
    QPushButton = None

from pdf_chapter_splitter.application import AnalysisResult, SessionState
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)
from pdf_chapter_splitter.gui.app import PDFChapterSplitterWindow
from pdf_chapter_splitter.pdf import PDFTextQualityLevel, PDFTextQualityReport


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_window_can_be_created_with_core_controls():
    app = QApplication.instance() or QApplication([])
    window = PDFChapterSplitterWindow()

    try:
        assert window.objectName() == "pdfChapterSplitterWindow"
        steps = window.findChild(QLabel, "workflowStepsLabel")
        assert steps is not None
        assert "步骤 1 选择 PDF" in steps.text()
        assert "步骤 2 确认章节" in steps.text()
        assert "步骤 3 拆分 PDF" in steps.text()
        assert window.findChild(QLabel, "currentStepLabel").text() == "当前：步骤 1 选择 PDF"
        assert window.findChild(type(window.select_pdf_button), "selectPdfButton") is not None
        assert window.findChild(type(window.candidates_table), "candidatesTable") is not None
        assert window.findChild(QPushButton, "confirmSelectedChapterButton").text() == "确认此章节"
        assert window.findChild(QPushButton, "ignoreSelectedChapterButton").text() == "忽略此章节"
        assert window.findChild(type(window.add_manual_button), "addManualChapterButton") is not None
        assert window.findChild(QPushButton, "completeChapterReviewButton").text() == "章节检查完成，进入拆分"
        assert window.findChild(type(window.split_button), "startSplitButton") is not None
        assert window.findChild(type(window.progress_bar), "progressBar") is not None
        assert window.findChild(type(window.error_label), "errorLabel") is not None
        assert window.findChild(QLabel, "pdfQualityBanner") is not None
        assert window.findChild(QCheckBox, "showAllCandidatesCheckBox") is not None
        assert "接受" not in _visible_button_texts(window)
        assert "确认章节" not in _visible_button_texts(window)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_displays_pdf_quality_and_candidate_quality_fields(tmp_path):
    app = QApplication.instance() or QApplication([])
    primary = _candidate(
        "Chapter 1",
        0,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )
    toc = _candidate(
        "Chapter 2 ........ 12",
        1,
        confidence=0.42,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )
    analysis = AnalysisResult(
        tmp_path / "book.pdf",
        10,
        {},
        (primary, toc),
        text_quality_report=_quality_report(),
    )
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        assert "文本质量较低" in window.findChild(QLabel, "pdfQualityBanner").text()
        assert window.findChild(QLabel, "currentStepLabel").text() == "当前：步骤 2 确认章节"
        assert window.candidates_table.rowCount() == 1
        assert window.candidates_table.horizontalHeaderItem(0).text() == "标题"
        assert window.candidates_table.horizontalHeaderItem(1).text() == "起始页"
        assert window.candidates_table.horizontalHeaderItem(2).text() == "识别可信度"
        assert window.candidates_table.horizontalHeaderItem(3).text() == "状态"
        assert window.candidates_table.item(0, 3).text() == "推荐"

        show_all = window.findChild(QCheckBox, "showAllCandidatesCheckBox")
        assert show_all.text() == "显示其他候选"
        show_all.setChecked(True)
        app.processEvents()

        assert window.candidates_table.rowCount() == 2
        assert window.candidates_table.item(1, 3).text() == "建议核对"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_evidence_detail_uses_filtered_row_candidate_mapping(tmp_path):
    app = QApplication.instance() or QApplication([])
    hidden_toc = _candidate(
        "Chapter 2 ........ 12",
        1,
        confidence=0.42,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )
    visible_primary = _candidate(
        "Chapter 1",
        4,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )
    analysis = AnalysisResult(
        tmp_path / "book.pdf",
        10,
        {},
        (hidden_toc, visible_primary),
        text_quality_report=_quality_report(),
    )
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        assert len(window.adapter.session.candidates) == 2
        assert window.candidates_table.rowCount() == 1
        assert window.candidates_table.selectionBehavior() is QAbstractItemView.SelectionBehavior.SelectRows
        window.candidates_table.selectRow(0)
        app.processEvents()

        assert window.title_edit.text() == "Chapter 1"
        assert window.findChild(QLabel, "editingCandidateLabel").text() == "正在编辑：Chapter 1"
        assert "primary evidence" in window.evidence_detail.toPlainText()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_evidence_is_collapsed_by_default_and_can_be_expanded(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidate = _candidate(
        "Chapter 1",
        0,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate,), text_quality_report=_quality_report())
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        evidence_box = window.findChild(QGroupBox, "evidenceGroupBox")
        assert evidence_box.title() == "为什么推荐这个章节？"
        assert evidence_box.isCheckable() is True
        assert evidence_box.isChecked() is False
        assert window.evidence_detail.isHidden() is True

        evidence_box.setChecked(True)
        app.processEvents()

        assert window.evidence_detail.isHidden() is False
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_requires_explicit_review_completion_before_split_step(tmp_path):
    app = QApplication.instance() or QApplication([])
    analysis = AnalysisResult(
        tmp_path / "book.pdf",
        10,
        {},
        (_candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER),),
        text_quality_report=_quality_report(PDFTextQualityLevel.HIGH),
    )
    chapter = Chapter.from_page_number("Chapter 1", 1)
    window = PDFChapterSplitterWindow(
        adapter=FakeAdapter(
            FakeSession(
                analysis,
                state=SessionState.READY_TO_RESOLVE,
                confirmed_chapters=(chapter,),
            )
        )
    )

    try:
        assert window.findChild(QLabel, "confirmedChaptersTitle").text() == "已确认章节"
        assert window.chapters_table.horizontalHeaderItem(0).text() == "章节"
        assert window.chapters_table.horizontalHeaderItem(1).text() == "起始页"
        assert window.chapters_table.horizontalHeaderItem(2).text() == "层级"
        assert window.chapters_table.horizontalHeaderItem(3).text() == "状态"
        assert window.chapters_table.item(0, 3).text() == "已确认"
        assert window.findChild(QLabel, "currentStepLabel").text() == "当前：步骤 2 确认章节"
        assert window.split_button.isEnabled() is False

        window.findChild(QPushButton, "completeChapterReviewButton").click()
        app.processEvents()

        assert window.findChild(QLabel, "currentStepLabel").text() == "当前：步骤 3 拆分 PDF"
        assert window.split_button.isEnabled() is True
        assert "自动计算拆分范围" in window.findChild(QLabel, "splitHelpLabel").text()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_manual_chapter_wording_remains_available():
    app = QApplication.instance() or QApplication([])
    window = PDFChapterSplitterWindow()

    try:
        assert window.findChild(QPushButton, "addManualChapterButton").text() == "手动添加章节"
        assert window.findChild(QGroupBox, "chapterEditGroupBox").title() == "章节编辑"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


class FakeAdapter:
    def __init__(self, session):
        self.session = session


class FakeSession:
    def __init__(
        self,
        analysis_result: AnalysisResult,
        *,
        state: SessionState = SessionState.WAITING_FOR_CONFIRMATION,
        confirmed_chapters=(),
    ) -> None:
        self.state = state
        self.input_path = analysis_result.input_path
        self.analysis_result = analysis_result
        self.confirmed_chapters = confirmed_chapters
        self.error = None
        self.processing_result = None

    @property
    def candidates(self):
        return self.analysis_result.candidates


def _candidate(
    title: str,
    start_page_index: int,
    *,
    confidence: float = 0.9,
    structure_type: ChapterStructureType = ChapterStructureType.UNKNOWN,
    quality_flags: tuple[ChapterCandidateQualityFlag, ...] = (),
) -> ChapterCandidate:
    evidence_description = (
        "primary evidence"
        if structure_type is ChapterStructureType.PRIMARY_CHAPTER
        else "quality evidence"
    )
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=ChapterCandidateSource.TEXT_LAYOUT,
        confidence=confidence,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.TEXT_PATTERN,
                description=evidence_description,
                page_index=start_page_index,
                text=title,
            ),
        ),
        structure_type=structure_type,
        quality_flags=quality_flags,
    )


def _quality_report(
    quality_level: PDFTextQualityLevel = PDFTextQualityLevel.LOW,
) -> PDFTextQualityReport:
    likely_ocr = quality_level is PDFTextQualityLevel.LOW
    return PDFTextQualityReport(
        page_count=10,
        pages_with_text=10 if quality_level is PDFTextQualityLevel.HIGH else 2,
        text_coverage_ratio=1.0 if quality_level is PDFTextQualityLevel.HIGH else 0.2,
        total_characters=200,
        average_characters_per_text_page=100.0,
        readable_page_ratio=1.0 if quality_level is PDFTextQualityLevel.HIGH else 0.2,
        quality_level=quality_level,
        likely_scanned=False,
        likely_ocr=likely_ocr,
        warnings=("weak_text_layer", "ocr_noise_suspected") if likely_ocr else (),
    )


def _visible_button_texts(window: PDFChapterSplitterWindow) -> set[str]:
    return {
        button.text()
        for button in window.findChildren(QPushButton)
        if button.isVisibleTo(window) or not window.isVisible()
    }
