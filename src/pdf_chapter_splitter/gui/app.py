"""PySide6 desktop GUI for PDF Chapter Splitter."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pdf_chapter_splitter.application import (
    ApplicationError,
    CandidatePresentationPolicy,
    ManualSplitInput,
    ProgressEvent,
    SessionState,
)
from pdf_chapter_splitter.gui.adapter import GuiWorkflowAdapter
from pdf_chapter_splitter.gui.presenters import (
    format_analysis_summary,
    format_application_error,
    format_candidate,
    format_chapter,
    format_progress_event,
    format_text_quality_report,
)


@dataclass(frozen=True, slots=True)
class GuiTaskMessage:
    """Message sent from background work to the GUI thread."""

    kind: str
    payload: Any


class GuiTaskRunner:
    """Run one blocking application call outside the Qt main thread."""

    def __init__(self) -> None:
        self.messages: queue.Queue[GuiTaskMessage] = queue.Queue()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, task: Callable[[], Any]) -> None:
        if self.is_running:
            return
        self._thread = threading.Thread(target=self._run, args=(task,), daemon=True)
        self._thread.start()

    def put_progress(self, event: ProgressEvent) -> None:
        self.messages.put(GuiTaskMessage("progress", event))

    def drain(self) -> list[GuiTaskMessage]:
        messages: list[GuiTaskMessage] = []
        while True:
            try:
                messages.append(self.messages.get_nowait())
            except queue.Empty:
                return messages

    def _run(self, task: Callable[[], Any]) -> None:
        try:
            self.messages.put(GuiTaskMessage("result", task()))
        except ApplicationError as exc:
            self.messages.put(GuiTaskMessage("error", exc))


class PDFChapterSplitterWindow(QMainWindow):
    """Minimal GUI that consumes the application session."""

    def __init__(self, *, adapter: GuiWorkflowAdapter | None = None) -> None:
        super().__init__()
        self.setObjectName("pdfChapterSplitterWindow")
        self.setWindowTitle("PDF Chapter Splitter")
        self.resize(1120, 760)

        self.task_runner = GuiTaskRunner()
        self.adapter = adapter or GuiWorkflowAdapter(progress_listener=self.task_runner.put_progress)
        self._selected_pdf_path: Path | None = None
        self._candidate_presentation_policy = CandidatePresentationPolicy()
        self._displayed_candidate_presentations: tuple[Any, ...] = ()

        self._build_ui()
        self._connect_actions()
        self._refresh_from_session()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_task_messages)
        self._timer.start(80)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(10)

        source_box = QGroupBox("PDF")
        source_layout = QGridLayout(source_box)
        self.select_pdf_button = QPushButton("选择 PDF")
        self.select_pdf_button.setObjectName("selectPdfButton")
        self.select_pdf_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.current_pdf_label = QLabel("尚未选择 PDF")
        self.current_pdf_label.setObjectName("currentPdfLabel")
        self.page_count_label = QLabel("页数：-")
        self.page_count_label.setObjectName("pageCountLabel")
        self.status_label = QLabel("状态：idle")
        self.status_label.setObjectName("statusLabel")
        source_layout.addWidget(self.select_pdf_button, 0, 0)
        source_layout.addWidget(self.current_pdf_label, 0, 1)
        source_layout.addWidget(self.page_count_label, 0, 2)
        source_layout.addWidget(self.status_label, 0, 3)
        self.pdf_quality_banner = QLabel("PDF quality: -")
        self.pdf_quality_banner.setObjectName("pdfQualityBanner")
        self.pdf_quality_banner.setWordWrap(True)
        source_layout.addWidget(self.pdf_quality_banner, 1, 0, 1, 4)
        layout.addWidget(source_box)

        candidate_header = QHBoxLayout()
        self.candidate_summary_label = QLabel("候选：-")
        self.candidate_summary_label.setObjectName("candidateSummaryLabel")
        self.show_all_candidates_checkbox = QCheckBox("显示全部候选")
        self.show_all_candidates_checkbox.setObjectName("showAllCandidatesCheckBox")
        candidate_header.addWidget(self.candidate_summary_label)
        candidate_header.addStretch(1)
        candidate_header.addWidget(self.show_all_candidates_checkbox)
        layout.addLayout(candidate_header)

        self.candidates_table = QTableWidget(0, 8)
        self.candidates_table.setObjectName("candidatesTable")
        self.candidates_table.setHorizontalHeaderLabels(
            ["选择", "标题", "页码", "置信度", "结构", "来源", "质量", "Evidence"]
        )
        self.candidates_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.candidates_table, stretch=3)

        edit_box = QGroupBox("候选操作")
        edit_layout = QGridLayout(edit_box)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("candidateTitleEdit")
        self.page_spin = QSpinBox()
        self.page_spin.setObjectName("candidatePageSpin")
        self.page_spin.setRange(1, 999999)
        self.level_spin = QSpinBox()
        self.level_spin.setObjectName("manualLevelSpin")
        self.level_spin.setRange(1, 20)
        self.accept_button = QPushButton("接受")
        self.accept_button.setObjectName("acceptCandidateButton")
        self.accept_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.reject_button = QPushButton("拒绝")
        self.reject_button.setObjectName("rejectCandidateButton")
        self.reject_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.add_manual_button = QPushButton("添加章节")
        self.add_manual_button.setObjectName("addManualChapterButton")
        self.confirm_button = QPushButton("确认章节")
        self.confirm_button.setObjectName("confirmChaptersButton")
        self.confirm_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        edit_layout.addWidget(QLabel("标题"), 0, 0)
        edit_layout.addWidget(self.title_edit, 0, 1, 1, 3)
        edit_layout.addWidget(QLabel("起始页"), 0, 4)
        edit_layout.addWidget(self.page_spin, 0, 5)
        edit_layout.addWidget(QLabel("层级"), 0, 6)
        edit_layout.addWidget(self.level_spin, 0, 7)
        edit_layout.addWidget(self.accept_button, 1, 0)
        edit_layout.addWidget(self.reject_button, 1, 1)
        edit_layout.addWidget(self.add_manual_button, 1, 2)
        edit_layout.addWidget(self.confirm_button, 1, 3)
        layout.addWidget(edit_box)

        self.chapters_table = QTableWidget(0, 4)
        self.chapters_table.setObjectName("chaptersTable")
        self.chapters_table.setHorizontalHeaderLabels(["标题", "起始页", "层级", "来源"])
        self.chapters_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.chapters_table, stretch=2)

        output_box = QGroupBox("输出")
        output_layout = QFormLayout(output_box)
        output_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setObjectName("outputDirectoryEdit")
        self.choose_output_button = QPushButton("选择目录")
        self.choose_output_button.setObjectName("chooseOutputButton")
        self.choose_output_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(self.choose_output_button)
        self.zip_checkbox = QCheckBox("生成 ZIP")
        self.zip_checkbox.setObjectName("createZipCheckBox")
        self.zip_path_edit = QLineEdit()
        self.zip_path_edit.setObjectName("zipPathEdit")
        self.split_button = QPushButton("开始拆分")
        self.split_button.setObjectName("startSplitButton")
        self.split_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        output_layout.addRow("输出目录", output_row)
        output_layout.addRow(self.zip_checkbox, self.zip_path_edit)
        output_layout.addRow(self.split_button)
        layout.addWidget(output_box)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 0)
        self.progress_label = QLabel("等待操作")
        self.progress_label.setObjectName("progressLabel")
        progress_row.addWidget(self.progress_bar)
        progress_row.addWidget(self.progress_label)
        layout.addLayout(progress_row)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.evidence_detail = QTextEdit()
        self.evidence_detail.setObjectName("evidenceDetail")
        self.evidence_detail.setReadOnly(True)
        self.evidence_detail.setFixedHeight(80)
        layout.addWidget(self.evidence_detail)

        self.result_label = QLabel("")
        self.result_label.setObjectName("resultLabel")
        layout.addWidget(self.result_label)

    def _connect_actions(self) -> None:
        self.select_pdf_button.clicked.connect(self._choose_pdf)
        self.choose_output_button.clicked.connect(self._choose_output_directory)
        self.show_all_candidates_checkbox.toggled.connect(self._refresh_from_session)
        self.candidates_table.itemSelectionChanged.connect(self._load_selected_candidate)
        self.accept_button.clicked.connect(self._accept_selected_candidate)
        self.reject_button.clicked.connect(self._reject_selected_candidate)
        self.add_manual_button.clicked.connect(self._add_manual_chapter)
        self.confirm_button.clicked.connect(self._refresh_confirmed_chapters)
        self.split_button.clicked.connect(self._start_split)

    def _choose_pdf(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF files (*.pdf)")
        if file_name:
            self.start_analyze(Path(file_name))

    def start_analyze(self, input_path: Path) -> None:
        self._selected_pdf_path = input_path
        self._set_busy(True)
        self.task_runner.start(lambda: self.adapter.analyze(input_path))

    def _choose_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_dir_edit.setText(directory)

    def _load_selected_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        self.title_edit.setText(candidate.title)
        self.page_spin.setValue(candidate.start_page_index + 1)
        view_model = format_candidate(candidate)
        self.evidence_detail.setPlainText(view_model.evidence_summary)

    def _accept_selected_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        try:
            self.adapter.accept_candidate(
                candidate,
                title=self.title_edit.text().strip() or None,
                start_page_number=self.page_spin.value(),
            )
        except ApplicationError as exc:
            self._show_error(exc)
            return
        self._refresh_from_session()

    def _reject_selected_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None:
            return
        try:
            self.adapter.reject_candidate(candidate)
        except ApplicationError as exc:
            self._show_error(exc)
            return
        self._refresh_from_session()

    def _add_manual_chapter(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "标题缺失", "请先输入章节标题。")
            return
        try:
            self.adapter.add_manual_chapter(
                title,
                start_page_number=self.page_spin.value(),
                level=self.level_spin.value(),
            )
        except ApplicationError as exc:
            self._show_error(exc)
            return
        self._refresh_from_session()

    def _refresh_confirmed_chapters(self) -> None:
        self._refresh_from_session()

    def _start_split(self) -> None:
        output_directory = self.output_dir_edit.text().strip()
        if not output_directory:
            QMessageBox.warning(self, "输出目录缺失", "请先选择输出目录。")
            return
        zip_path = self.zip_path_edit.text().strip() if self.zip_checkbox.isChecked() else None
        self._set_busy(True)
        self.task_runner.start(
            lambda: self.adapter.resolve_then_execute(
                Path(output_directory),
                zip_path=None if not zip_path else Path(zip_path),
            )
        )

    def _drain_task_messages(self) -> None:
        for message in self.task_runner.drain():
            if message.kind == "progress":
                self._show_progress(message.payload)
            elif message.kind == "error":
                self._set_busy(False)
                self._show_error(message.payload)
                self._refresh_from_session()
            elif message.kind == "result":
                self._set_busy(False)
                self._refresh_from_session()

    def _show_progress(self, event: ProgressEvent) -> None:
        view_model = format_progress_event(event)
        self.progress_label.setText(
            view_model.message
            if not view_model.progress_label
            else f"{view_model.message} ({view_model.progress_label})"
        )
        if view_model.is_indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(event.current * 100 / event.total))

    def _show_error(self, error: ApplicationError) -> None:
        view_model = format_application_error(error)
        detail = f"阶段：{view_model.stage_label}"
        if view_model.cause_label:
            detail = f"{detail}；原因：{view_model.cause_label}"
        self.error_label.setText(f"{view_model.message}（{detail}）")

    def _refresh_from_session(self) -> None:
        session = self.adapter.session
        self.status_label.setText(f"状态：{session.state.value}")
        if session.input_path is not None:
            self.current_pdf_label.setText(Path(session.input_path).name)
        if session.analysis_result is not None:
            self.page_count_label.setText(f"页数：{session.analysis_result.page_count}")
            self._update_analysis_summary(session.analysis_result)
        else:
            self.page_count_label.setText("页数：-")
            self.pdf_quality_banner.setText("PDF quality: -")
            self.candidate_summary_label.setText("候选：-")
        if session.error is None:
            self.error_label.setText("")

        self._fill_candidates_table(tuple(session.candidates))
        self._fill_chapters_table(tuple(session.confirmed_chapters))
        self._update_result_label()
        self._update_action_state()

    def _fill_candidates_table(self, candidates: tuple[Any, ...]) -> None:
        presentations = self._candidate_presentation_policy.present(
            candidates,
            show_all=self.show_all_candidates_checkbox.isChecked(),
        )
        self._displayed_candidate_presentations = tuple(
            presentation for presentation in presentations if presentation.visible
        )
        self.candidates_table.setRowCount(len(self._displayed_candidate_presentations))
        for row, presentation in enumerate(self._displayed_candidate_presentations):
            candidate = presentation.candidate
            view_model = format_candidate(
                candidate,
                accepted=self._candidate_is_accepted(candidate),
            )
            values = [
                "已选择" if view_model.accepted else "",
                view_model.title,
                view_model.page_label,
                view_model.confidence_label,
                view_model.structure_label,
                view_model.sources_label,
                view_model.quality_label,
                view_model.evidence_summary,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.candidates_table.setItem(row, column, item)

    def _update_analysis_summary(self, analysis_result: Any) -> None:
        summary = getattr(analysis_result, "summary", None)
        if summary is not None:
            summary_view_model = format_analysis_summary(summary)
            quality_view_model = format_text_quality_report(summary.text_quality_report)
            self.candidate_summary_label.setText(
                (
                    f"{summary_view_model.candidate_summary_label}; "
                    f"{summary_view_model.quality_signal_label}"
                )
            )
        else:
            quality_view_model = format_text_quality_report(
                getattr(analysis_result, "text_quality_report", None)
            )
            self.candidate_summary_label.setText(
                f"候选：{len(tuple(getattr(analysis_result, 'candidates', ())))}"
            )
        banner_parts = [
            f"PDF Analysis Quality: {quality_view_model.quality_level_label}",
            quality_view_model.text_coverage_label,
            quality_view_model.readable_pages_label,
            quality_view_model.ocr_risk_label,
        ]
        if quality_view_model.warnings_label:
            banner_parts.append(f"Warnings: {quality_view_model.warnings_label}")
        self.pdf_quality_banner.setText(" | ".join(banner_parts))

    def _fill_chapters_table(self, chapters: tuple[Any, ...]) -> None:
        self.chapters_table.setRowCount(len(chapters))
        for row, chapter in enumerate(chapters):
            view_model = format_chapter(chapter)
            values = [
                view_model.title,
                view_model.page_label,
                view_model.level_label,
                view_model.source_label,
            ]
            for column, value in enumerate(values):
                self.chapters_table.setItem(row, column, QTableWidgetItem(value))

    def _update_result_label(self) -> None:
        result = self.adapter.session.processing_result
        if result is None:
            self.result_label.setText("")
            return
        output_count = len(result.split_result.outputs)
        if result.zip_result is None:
            self.result_label.setText(f"已生成 {output_count} 个 PDF")
        else:
            self.result_label.setText(f"已生成 {output_count} 个 PDF 和 ZIP")

    def _update_action_state(self) -> None:
        state = self.adapter.session.state
        is_busy = state in {
            SessionState.ANALYZING,
            SessionState.CONFIRMING,
            SessionState.RESOLVING,
            SessionState.EXECUTING,
        }
        can_confirm = state in {SessionState.WAITING_FOR_CONFIRMATION, SessionState.READY_TO_RESOLVE}
        can_execute = state is SessionState.READY_TO_RESOLVE
        self.select_pdf_button.setEnabled(not is_busy)
        self.accept_button.setEnabled(can_confirm and self._selected_candidate() is not None)
        self.reject_button.setEnabled(can_confirm and self._selected_candidate() is not None)
        self.add_manual_button.setEnabled(can_confirm)
        self.confirm_button.setEnabled(can_confirm)
        self.split_button.setEnabled(can_execute and not is_busy)

    def _set_busy(self, is_busy: bool) -> None:
        self.select_pdf_button.setEnabled(not is_busy)
        self.accept_button.setEnabled(not is_busy)
        self.reject_button.setEnabled(not is_busy)
        self.add_manual_button.setEnabled(not is_busy)
        self.confirm_button.setEnabled(not is_busy)
        self.split_button.setEnabled(not is_busy)

    def _selected_candidate(self) -> Any | None:
        selected_rows = self.candidates_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        if row < 0 or row >= len(self._displayed_candidate_presentations):
            return None
        return self._displayed_candidate_presentations[row].candidate

    def _candidate_is_accepted(self, candidate: Any) -> bool:
        for chapter in self.adapter.session.confirmed_chapters:
            provenance = chapter.provenance
            if provenance is None:
                continue
            if (
                provenance.candidate_title == candidate.title
                and provenance.candidate_start_page_index == candidate.start_page_index
            ):
                return True
        return False


def run_app() -> int:
    """Run the desktop application."""

    app = QApplication.instance() or QApplication([])
    window = PDFChapterSplitterWindow()
    window.show()
    return app.exec()


__all__ = [
    "GuiTaskMessage",
    "GuiTaskRunner",
    "PDFChapterSplitterWindow",
    "run_app",
]
