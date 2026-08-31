from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QCheckBox,
        QGroupBox,
        QLabel,
        QPushButton,
        QScrollArea,
    )
except Exception:  # pragma: no cover - depends on local GUI runtime availability
    QApplication = None
    QAbstractItemView = None
    QCheckBox = None
    QGroupBox = None
    QLabel = None
    QPushButton = None
    QScrollArea = None
    Qt = None

from pdf_chapter_splitter.application import AnalysisResult, SessionState, WorkflowStage
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)
from pdf_chapter_splitter.gui.app import GuiTaskMessage, GuiTaskRunner, PDFChapterSplitterWindow
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
        assert window.findChild(QPushButton, "selectPrimaryChaptersButton").text() == "全选主要章节"
        assert window.findChild(QPushButton, "confirmSelectedChaptersButton").text() == "确认选中章节"
        assert window.findChild(QPushButton, "editSelectedChapterButton").text() == "编辑章节"
        assert window.findChild(QPushButton, "rejectSelectedChaptersButton").text() == "拒绝选中"
        assert window.findChild(type(window.add_manual_button), "addManualChapterButton") is not None
        assert window.findChild(QPushButton, "cancelChapterEditButton").text() == "取消"
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
        assert window.candidates_table.horizontalHeaderItem(0).text() == "✓"
        assert window.candidates_table.horizontalHeaderItem(1).text() == "标题"
        assert window.candidates_table.horizontalHeaderItem(2).text() == "起始页"
        assert window.candidates_table.horizontalHeaderItem(3).text() == "识别可信度"
        assert window.candidates_table.horizontalHeaderItem(4).text() == "识别来源"
        assert window.candidates_table.horizontalHeaderItem(5).text() == "状态"
        assert window.candidates_table.item(0, 5).text() == "推荐"

        show_all = window.findChild(QCheckBox, "showAllCandidatesCheckBox")
        assert show_all.text() == "显示其他候选"
        show_all.setChecked(True)
        app.processEvents()

        assert window.candidates_table.rowCount() == 2
        assert window.candidates_table.item(1, 5).text() == "建议核对"
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
        assert window.findChild(QLabel, "editingCandidateLabel").text() == "正在查看：Chapter 1"
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


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_checkbox_selection_is_independent_from_row_selection(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = (
        _candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
        _candidate("Chapter 2", 4, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
        _candidate("Chapter 3", 8, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, candidates, text_quality_report=_quality_report())
    adapter = FakeAdapter(FakeSession(analysis))
    window = PDFChapterSplitterWindow(adapter=adapter)

    try:
        window.candidates_table.selectRow(0)
        app.processEvents()

        assert adapter.calls == []
        assert window.candidates_table.item(0, 0).checkState() == Qt.CheckState.Unchecked
        assert window.findChild(QPushButton, "editSelectedChapterButton").isEnabled() is True
        assert window.findChild(QPushButton, "rejectSelectedChaptersButton").isEnabled() is True
        assert window.findChild(QPushButton, "confirmSelectedChaptersButton").isEnabled() is False

        window.candidates_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        window.candidates_table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        app.processEvents()

        assert window.findChild(QLabel, "selectedCandidateCountLabel").text() == "已勾选 2 个章节"
        assert window.findChild(QPushButton, "confirmSelectedChaptersButton").isEnabled() is True

        window.candidates_table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        app.processEvents()

        assert window.findChild(QLabel, "selectedCandidateCountLabel").text() == "已勾选 1 个章节"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_batch_confirms_only_checked_candidates_without_manual_chapter(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = (
        _candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
        _candidate("Chapter 2", 4, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
        _candidate("Chapter 3", 8, structure_type=ChapterStructureType.PRIMARY_CHAPTER),
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, candidates, text_quality_report=_quality_report())
    adapter = FakeAdapter(FakeSession(analysis))
    window = PDFChapterSplitterWindow(adapter=adapter)

    try:
        window.candidates_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        window.candidates_table.item(2, 0).setCheckState(Qt.CheckState.Checked)
        window.findChild(QPushButton, "confirmSelectedChaptersButton").click()
        app.processEvents()

        assert adapter.calls == [("accept_candidates", (candidates[0], candidates[2]))]
        assert [chapter.title for chapter in adapter.session.confirmed_chapters] == [
            "Chapter 1",
            "Chapter 3",
        ]
        assert adapter.session.state is SessionState.READY_TO_RESOLVE
        assert window.findChild(QLabel, "selectedCandidateCountLabel").text() == "已勾选 0 个章节"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_edits_selected_candidate_without_manual_chapter(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidate = _candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER)
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, (candidate,), text_quality_report=_quality_report())
    adapter = FakeAdapter(FakeSession(analysis))
    window = PDFChapterSplitterWindow(adapter=adapter)

    try:
        window.candidates_table.selectRow(0)
        window.findChild(QPushButton, "editSelectedChapterButton").click()
        app.processEvents()

        assert window.findChild(QLabel, "editingCandidateLabel").text() == "正在编辑：Chapter 1"
        window.title_edit.setText("Chapter 1 Edited")
        window.page_spin.setValue(3)
        window.findChild(QPushButton, "saveCandidateEditButton").click()
        app.processEvents()

        assert adapter.calls == [("accept_candidate", candidate, "Chapter 1 Edited", 3)]
        assert adapter.session.confirmed_chapters[0].title == "Chapter 1 Edited"
        assert adapter.session.confirmed_chapters[0].gui_page_number == 3
        assert adapter.session.state is SessionState.READY_TO_RESOLVE
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_cancel_candidate_edit_does_not_modify_candidate(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidate = _candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER)
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, (candidate,), text_quality_report=_quality_report())
    adapter = FakeAdapter(FakeSession(analysis))
    window = PDFChapterSplitterWindow(adapter=adapter)

    try:
        window.candidates_table.selectRow(0)
        window.findChild(QPushButton, "editSelectedChapterButton").click()
        window.title_edit.setText("Wrong title")
        window.page_spin.setValue(9)
        window.findChild(QPushButton, "cancelChapterEditButton").click()
        app.processEvents()

        assert adapter.calls == []
        assert candidate.title == "Chapter 1"
        assert candidate.start_page_index == 0
        assert window.title_edit.text() == "Chapter 1"
        assert window.page_spin.value() == 1
        assert window.findChild(QLabel, "editingCandidateLabel").text() == "正在查看：Chapter 1"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_rejects_checked_candidates_without_manual_chapter(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = (
        _candidate("Contents", 0, structure_type=ChapterStructureType.FRONT_MATTER),
        _candidate("References", 18, structure_type=ChapterStructureType.BACK_MATTER),
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, candidates, text_quality_report=_quality_report())
    adapter = FakeAdapter(FakeSession(analysis))
    window = PDFChapterSplitterWindow(adapter=adapter)

    try:
        window.show_all_candidates_checkbox.setChecked(True)
        window.candidates_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        window.candidates_table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        window.findChild(QPushButton, "rejectSelectedChaptersButton").click()
        app.processEvents()

        assert adapter.calls == [("reject_candidates", candidates)]
        assert adapter.session.confirmed_chapters == ()
        assert adapter.session.state is SessionState.WAITING_FOR_CONFIRMATION
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_tables_show_about_ten_rows(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = tuple(
        _candidate(f"Chapter {index}", index, structure_type=ChapterStructureType.PRIMARY_CHAPTER)
        for index in range(1, 13)
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 20, {}, candidates, text_quality_report=_quality_report())
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        assert window.candidates_table.minimumHeight() >= 260
        assert window.chapters_table.minimumHeight() >= 220
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_main_window_uses_page_level_scroll_area():
    app = QApplication.instance() or QApplication([])
    window = PDFChapterSplitterWindow()

    try:
        scroll_area = window.findChild(QScrollArea, "mainScrollArea")
        assert scroll_area is not None
        assert scroll_area.widgetResizable() is True
        assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert scroll_area.widget() is window.findChild(type(scroll_area.widget()), "mainPageWidget")
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_scroll_area_can_scroll_full_page_when_content_exceeds_viewport(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = tuple(
        _candidate(f"Chapter {index}", index, structure_type=ChapterStructureType.PRIMARY_CHAPTER)
        for index in range(1, 16)
    )
    confirmed_chapters = tuple(
        Chapter.from_page_number(f"Chapter {index}", index)
        for index in range(1, 13)
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 40, {}, candidates, text_quality_report=_quality_report())
    window = PDFChapterSplitterWindow(
        adapter=FakeAdapter(
            FakeSession(
                analysis,
                state=SessionState.READY_TO_RESOLVE,
                confirmed_chapters=confirmed_chapters,
            )
        )
    )

    try:
        window.resize(1120, 760)
        window.show()
        app.processEvents()

        scroll_area = window.findChild(QScrollArea, "mainScrollArea")
        assert scroll_area.widget().height() > scroll_area.viewport().height()
        assert scroll_area.verticalScrollBar().maximum() > 0
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_scroll_area_keeps_all_main_page_sections(tmp_path):
    app = QApplication.instance() or QApplication([])
    analysis = AnalysisResult(
        tmp_path / "book.pdf",
        20,
        {},
        (_candidate("Chapter 1", 0, structure_type=ChapterStructureType.PRIMARY_CHAPTER),),
        text_quality_report=_quality_report(),
    )
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        assert window.findChild(QScrollArea, "mainScrollArea") is not None
        assert window.findChild(type(window.candidates_table), "candidatesTable") is not None
        assert window.findChild(type(window.chapters_table), "chaptersTable") is not None
        assert window.findChild(type(window.output_dir_edit), "outputDirectoryEdit") is not None
        assert window.findChild(type(window.progress_bar), "progressBar") is not None
        assert window.findChild(QLabel, "statusLabel") is not None
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_scroll_area_does_not_compress_chapter_tables_or_need_horizontal_scroll(tmp_path):
    app = QApplication.instance() or QApplication([])
    candidates = tuple(
        _candidate(f"Chapter {index}", index, structure_type=ChapterStructureType.PRIMARY_CHAPTER)
        for index in range(1, 13)
    )
    analysis = AnalysisResult(tmp_path / "book.pdf", 30, {}, candidates, text_quality_report=_quality_report())
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(FakeSession(analysis)))

    try:
        window.resize(1120, 760)
        window.show()
        app.processEvents()

        scroll_area = window.findChild(QScrollArea, "mainScrollArea")
        assert window.candidates_table.minimumHeight() >= 260
        assert window.chapters_table.minimumHeight() >= 220
        assert scroll_area.horizontalScrollBar().maximum() == 0
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_task_runner_reports_unexpected_task_exception():
    runner = GuiTaskRunner()

    runner.start(_raise_bbox_value_error)
    _wait_for_runner_to_finish(runner)

    messages = runner.drain()
    assert [(message.kind, type(message.payload)) for message in messages] == [
        ("error", ValueError)
    ]
    assert str(messages[0].payload) == "x1 must be greater than or equal to x0"


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_worker_value_error_restores_controls_and_shows_error(tmp_path):
    app = QApplication.instance() or QApplication([])
    analysis = AnalysisResult(tmp_path / "book.pdf", 10, {}, (), text_quality_report=_quality_report())
    session = FakeSession(analysis, state=SessionState.ANALYZING)
    window = PDFChapterSplitterWindow(adapter=FakeAdapter(session))

    try:
        window._set_busy(True)
        assert window.select_pdf_button.isEnabled() is False

        window.task_runner.messages.put(
            GuiTaskMessage(
                "error",
                ValueError("x1 must be greater than or equal to x0"),
            )
        )
        window._drain_task_messages()
        app.processEvents()

        assert window.select_pdf_button.isEnabled() is True
        assert "分析 PDF 时发生错误" in window.error_label.text()
        assert "x1 must be greater than or equal to x0" in window.error_label.text()
        assert session.state is SessionState.FAILED
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.skipif(QApplication is None, reason="PySide6 is not available")
def test_gui_task_runner_reports_success_result():
    runner = GuiTaskRunner()

    runner.start(lambda: "ok")
    _wait_for_runner_to_finish(runner)

    messages = runner.drain()
    assert [(message.kind, message.payload) for message in messages] == [("result", "ok")]


class FakeAdapter:
    def __init__(self, session):
        self.session = session
        self.calls = []

    def accept_candidate(
        self,
        candidate,
        *,
        title: str | None = None,
        start_page_number: int | None = None,
    ):
        self.calls.append(("accept_candidate", candidate, title, start_page_number))
        return self.session.accept_candidate(
            candidate,
            title=title,
            start_page_number=start_page_number,
        )

    def accept_candidates(self, candidates):
        normalized = tuple(candidates)
        self.calls.append(("accept_candidates", normalized))
        return self.session.accept_candidates(normalized)

    def reject_candidates(self, candidates):
        normalized = tuple(candidates)
        self.calls.append(("reject_candidates", normalized))
        return self.session.reject_candidates(normalized)


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

    def accept_candidate(
        self,
        candidate,
        *,
        title: str | None = None,
        start_page_number: int | None = None,
    ):
        chapter = Chapter.from_page_number(
            candidate.title if title is None else title,
            candidate.start_page_index + 1 if start_page_number is None else start_page_number,
            level=candidate.level,
        )
        self.confirmed_chapters = self.confirmed_chapters + (chapter,)
        self.state = SessionState.READY_TO_RESOLVE
        return self

    def accept_candidates(self, candidates):
        for candidate in tuple(candidates):
            self.accept_candidate(candidate)
        return self

    def reject_candidates(self, candidates):
        self.state = SessionState.WAITING_FOR_CONFIRMATION
        return self


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


def _raise_bbox_value_error():
    raise ValueError("x1 must be greater than or equal to x0")


def _wait_for_runner_to_finish(runner: GuiTaskRunner) -> None:
    deadline = time.monotonic() + 1
    while runner.is_running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runner.is_running is False
