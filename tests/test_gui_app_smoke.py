from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QCheckBox, QLabel
except Exception:  # pragma: no cover - depends on local GUI runtime availability
    QApplication = None
    QCheckBox = None
    QLabel = None

from pdf_chapter_splitter.application import AnalysisResult, SessionState
from pdf_chapter_splitter.chapters import (
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
        assert window.findChild(type(window.select_pdf_button), "selectPdfButton") is not None
        assert window.findChild(type(window.candidates_table), "candidatesTable") is not None
        assert window.findChild(type(window.accept_button), "acceptCandidateButton") is not None
        assert window.findChild(type(window.reject_button), "rejectCandidateButton") is not None
        assert window.findChild(type(window.add_manual_button), "addManualChapterButton") is not None
        assert window.findChild(type(window.confirm_button), "confirmChaptersButton") is not None
        assert window.findChild(type(window.split_button), "startSplitButton") is not None
        assert window.findChild(type(window.progress_bar), "progressBar") is not None
        assert window.findChild(type(window.error_label), "errorLabel") is not None
        assert window.findChild(QLabel, "pdfQualityBanner") is not None
        assert window.findChild(QCheckBox, "showAllCandidatesCheckBox") is not None
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
        assert "LOW" in window.findChild(QLabel, "pdfQualityBanner").text()
        assert window.candidates_table.rowCount() == 1
        assert window.candidates_table.item(0, 4).text() == "primary_chapter"
        assert window.candidates_table.item(0, 6).text() == "Good"

        show_all = window.findChild(QCheckBox, "showAllCandidatesCheckBox")
        show_all.setChecked(True)
        app.processEvents()

        assert window.candidates_table.rowCount() == 2
        assert window.candidates_table.item(1, 6).text() == "toc_page_suspected"
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
        window.candidates_table.selectRow(0)
        app.processEvents()

        assert window.title_edit.text() == "Chapter 1"
        assert "primary evidence" in window.evidence_detail.toPlainText()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


class FakeAdapter:
    def __init__(self, session):
        self.session = session


class FakeSession:
    def __init__(self, analysis_result: AnalysisResult) -> None:
        self.state = SessionState.WAITING_FOR_CONFIRMATION
        self.input_path = analysis_result.input_path
        self.analysis_result = analysis_result
        self.confirmed_chapters = ()
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


def _quality_report() -> PDFTextQualityReport:
    return PDFTextQualityReport(
        page_count=10,
        pages_with_text=2,
        text_coverage_ratio=0.2,
        total_characters=200,
        average_characters_per_text_page=100.0,
        readable_page_ratio=0.2,
        quality_level=PDFTextQualityLevel.LOW,
        likely_scanned=False,
        likely_ocr=True,
        warnings=("weak_text_layer", "ocr_noise_suspected"),
    )
