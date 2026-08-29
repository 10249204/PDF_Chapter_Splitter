"""PySide6 desktop GUI for PDF Chapter Splitter."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
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
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.resize(1120, 760)

        self.task_runner = GuiTaskRunner()
        self.adapter = adapter or GuiWorkflowAdapter(progress_listener=self.task_runner.put_progress)
        self._selected_pdf_path: Path | None = None
        self._candidate_presentation_policy = CandidatePresentationPolicy()
        self._displayed_candidate_presentations: tuple[Any, ...] = ()
        self._chapter_review_completed = False
        self._editing_confirmed_chapter_index: int | None = None

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

        self.workflow_steps_label = QLabel("步骤 1 选择 PDF  →  步骤 2 确认章节  →  步骤 3 拆分 PDF")
        self.workflow_steps_label.setObjectName("workflowStepsLabel")
        self.current_step_label = QLabel("当前：步骤 1 选择 PDF")
        self.current_step_label.setObjectName("currentStepLabel")
        layout.addWidget(self.workflow_steps_label)
        layout.addWidget(self.current_step_label)

        source_box = QGroupBox("选择 PDF")
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
        self.pdf_quality_banner = QLabel("请选择一个 PDF 开始。")
        self.pdf_quality_banner.setObjectName("pdfQualityBanner")
        self.pdf_quality_banner.setWordWrap(True)
        source_layout.addWidget(self.pdf_quality_banner, 1, 0, 1, 4)
        layout.addWidget(source_box)

        candidates_box = QGroupBox("发现的章节")
        candidates_layout = QVBoxLayout(candidates_box)
        candidate_header = QHBoxLayout()
        self.candidate_summary_label = QLabel("程序会在这里显示发现的章节。")
        self.candidate_summary_label.setObjectName("candidateSummaryLabel")
        self.show_all_candidates_checkbox = QCheckBox("显示其他候选")
        self.show_all_candidates_checkbox.setObjectName("showAllCandidatesCheckBox")
        candidate_header.addWidget(self.candidate_summary_label)
        candidate_header.addStretch(1)
        candidate_header.addWidget(self.show_all_candidates_checkbox)
        candidates_layout.addLayout(candidate_header)

        self.candidates_table = QTableWidget(0, 4)
        self.candidates_table.setObjectName("candidatesTable")
        self.candidates_table.setHorizontalHeaderLabels(
            ["标题", "起始页", "识别可信度", "状态"]
        )
        self.candidates_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidates_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.candidates_table.horizontalHeader().setStretchLastSection(True)
        candidates_layout.addWidget(self.candidates_table)
        layout.addWidget(candidates_box, stretch=3)

        edit_box = QGroupBox("章节编辑")
        edit_box.setObjectName("chapterEditGroupBox")
        edit_layout = QGridLayout(edit_box)
        self.editing_candidate_label = QLabel("请选择上方发现的章节，或手动填写章节。")
        self.editing_candidate_label.setObjectName("editingCandidateLabel")
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("candidateTitleEdit")
        self.page_spin = QSpinBox()
        self.page_spin.setObjectName("candidatePageSpin")
        self.page_spin.setRange(1, 999999)
        self.level_spin = QSpinBox()
        self.level_spin.setObjectName("manualLevelSpin")
        self.level_spin.setRange(1, 20)
        self.accept_button = QPushButton("确认此章节")
        self.accept_button.setObjectName("confirmSelectedChapterButton")
        self.accept_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.reject_button = QPushButton("忽略此章节")
        self.reject_button.setObjectName("ignoreSelectedChapterButton")
        self.reject_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.add_manual_button = QPushButton("手动添加章节")
        self.add_manual_button.setObjectName("addManualChapterButton")
        self.update_confirmed_button = QPushButton("保存修改")
        self.update_confirmed_button.setObjectName("updateConfirmedChapterButton")
        self.confirm_button = QPushButton("章节检查完成，进入拆分")
        self.confirm_button.setObjectName("completeChapterReviewButton")
        self.confirm_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        edit_layout.addWidget(self.editing_candidate_label, 0, 0, 1, 4)
        edit_layout.addWidget(QLabel("标题"), 1, 0)
        edit_layout.addWidget(self.title_edit, 1, 1, 1, 3)
        edit_layout.addWidget(QLabel("起始页"), 2, 0)
        edit_layout.addWidget(self.page_spin, 2, 1)
        edit_layout.addWidget(QLabel("章节层级"), 2, 2)
        edit_layout.addWidget(self.level_spin, 2, 3)
        edit_layout.addWidget(self.accept_button, 3, 0)
        edit_layout.addWidget(self.reject_button, 3, 1)
        edit_layout.addWidget(self.add_manual_button, 3, 2)
        edit_layout.addWidget(self.update_confirmed_button, 3, 3)
        edit_layout.addWidget(self.confirm_button, 4, 0, 1, 4)
        layout.addWidget(edit_box)

        confirmed_header = QHBoxLayout()
        self.confirmed_chapters_title = QLabel("已确认章节")
        self.confirmed_chapters_title.setObjectName("confirmedChaptersTitle")
        self.confirmed_chapter_source_label = QLabel("来源：-")
        self.confirmed_chapter_source_label.setObjectName("confirmedChapterSourceLabel")
        self.edit_confirmed_button = QPushButton("修改")
        self.edit_confirmed_button.setObjectName("editConfirmedChapterButton")
        self.remove_confirmed_button = QPushButton("撤销确认")
        self.remove_confirmed_button.setObjectName("removeConfirmedChapterButton")
        confirmed_header.addWidget(self.confirmed_chapters_title)
        confirmed_header.addWidget(self.confirmed_chapter_source_label)
        confirmed_header.addStretch(1)
        confirmed_header.addWidget(self.edit_confirmed_button)
        confirmed_header.addWidget(self.remove_confirmed_button)
        layout.addLayout(confirmed_header)

        self.chapters_table = QTableWidget(0, 4)
        self.chapters_table.setObjectName("chaptersTable")
        self.chapters_table.setHorizontalHeaderLabels(["章节", "起始页", "层级", "状态"])
        self.chapters_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chapters_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.chapters_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.chapters_table, stretch=2)

        output_box = QGroupBox("拆分 PDF")
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
        self.split_help_label = QLabel("确认章节后，程序会根据相邻章节的起始页自动计算拆分范围。")
        self.split_help_label.setObjectName("splitHelpLabel")
        self.split_help_label.setWordWrap(True)
        output_layout.addRow("输出目录", output_row)
        output_layout.addRow(self.zip_checkbox, self.zip_path_edit)
        output_layout.addRow(self.split_help_label)
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

        self.evidence_group_box = QGroupBox("为什么推荐这个章节？")
        self.evidence_group_box.setObjectName("evidenceGroupBox")
        self.evidence_group_box.setCheckable(True)
        self.evidence_group_box.setChecked(False)
        evidence_layout = QVBoxLayout(self.evidence_group_box)
        self.evidence_detail = QTextEdit()
        self.evidence_detail.setObjectName("evidenceDetail")
        self.evidence_detail.setReadOnly(True)
        self.evidence_detail.setFixedHeight(80)
        self.evidence_detail.setHidden(True)
        evidence_layout.addWidget(self.evidence_detail)
        layout.addWidget(self.evidence_group_box)

        self.result_label = QLabel("")
        self.result_label.setObjectName("resultLabel")
        layout.addWidget(self.result_label)

    def _connect_actions(self) -> None:
        self.select_pdf_button.clicked.connect(self._choose_pdf)
        self.choose_output_button.clicked.connect(self._choose_output_directory)
        self.show_all_candidates_checkbox.toggled.connect(self._refresh_from_session)
        self.candidates_table.itemSelectionChanged.connect(self._load_selected_candidate)
        self.chapters_table.itemSelectionChanged.connect(self._show_selected_chapter_source)
        self.evidence_group_box.toggled.connect(self.evidence_detail.setVisible)
        self.accept_button.clicked.connect(self._accept_selected_candidate)
        self.reject_button.clicked.connect(self._reject_selected_candidate)
        self.add_manual_button.clicked.connect(self._add_manual_chapter)
        self.update_confirmed_button.clicked.connect(self._update_confirmed_chapter)
        self.edit_confirmed_button.clicked.connect(self._edit_selected_confirmed_chapter)
        self.remove_confirmed_button.clicked.connect(self._remove_selected_confirmed_chapter)
        self.confirm_button.clicked.connect(self._complete_chapter_review)
        self.split_button.clicked.connect(self._start_split)

    def _choose_pdf(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF files (*.pdf)")
        if file_name:
            self.start_analyze(Path(file_name))

    def start_analyze(self, input_path: Path) -> None:
        self._selected_pdf_path = input_path
        self._chapter_review_completed = False
        self._editing_confirmed_chapter_index = None
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
        self.level_spin.setValue(candidate.level)
        self._editing_confirmed_chapter_index = None
        self.editing_candidate_label.setText(f"正在编辑：{candidate.title}")
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
        self._chapter_review_completed = False
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
        self._chapter_review_completed = False
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
        self._chapter_review_completed = False
        self._editing_confirmed_chapter_index = None
        self._refresh_from_session()

    def _complete_chapter_review(self) -> None:
        if not tuple(self.adapter.session.confirmed_chapters):
            QMessageBox.warning(self, "还没有确认章节", "请先确认或手动添加至少一个章节。")
            return
        self._chapter_review_completed = True
        self._refresh_from_session()

    def _edit_selected_confirmed_chapter(self) -> None:
        selected = self._selected_confirmed_chapter_with_index()
        if selected is None:
            return
        index, chapter = selected
        self._editing_confirmed_chapter_index = index
        self.title_edit.setText(chapter.title)
        self.page_spin.setValue(chapter.gui_page_number)
        self.level_spin.setValue(chapter.level)
        self.editing_candidate_label.setText(f"正在修改已确认章节：{chapter.title}")

    def _update_confirmed_chapter(self) -> None:
        if self._editing_confirmed_chapter_index is None:
            return
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "标题缺失", "请先输入章节标题。")
            return
        try:
            self.adapter.update_confirmed_chapter(
                self._editing_confirmed_chapter_index,
                title=title,
                start_page_number=self.page_spin.value(),
                level=self.level_spin.value(),
            )
        except ApplicationError as exc:
            self._show_error(exc)
            return
        self._chapter_review_completed = False
        self._editing_confirmed_chapter_index = None
        self._refresh_from_session()

    def _remove_selected_confirmed_chapter(self) -> None:
        selected = self._selected_confirmed_chapter_with_index()
        if selected is None:
            return
        try:
            self.adapter.remove_confirmed_chapter(selected[0])
        except ApplicationError as exc:
            self._show_error(exc)
            return
        self._chapter_review_completed = False
        self._editing_confirmed_chapter_index = None
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
            self.pdf_quality_banner.setText("请选择一个 PDF 开始。")
            self.candidate_summary_label.setText("程序会在这里显示发现的章节。")
        if session.error is None:
            self.error_label.setText("")

        self._update_current_step()
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
                view_model.title,
                view_model.page_label,
                view_model.confidence_label,
                _candidate_status_label(presentation, accepted=view_model.accepted),
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
                    f"程序发现了 {summary.candidate_count} 个可能的章节，"
                    f"其中 {summary.primary_chapter_candidate_count} 个被判断为主要章节。"
                )
            )
        else:
            quality_view_model = format_text_quality_report(
                getattr(analysis_result, "text_quality_report", None)
            )
            candidate_count = len(tuple(getattr(analysis_result, "candidates", ())))
            self.candidate_summary_label.setText(f"程序发现了 {candidate_count} 个可能的章节。")
        self.pdf_quality_banner.setText(_quality_banner_text(quality_view_model))

    def _fill_chapters_table(self, chapters: tuple[Any, ...]) -> None:
        self.chapters_table.setRowCount(len(chapters))
        for row, chapter in enumerate(chapters):
            view_model = format_chapter(chapter)
            values = [
                view_model.title,
                view_model.page_label,
                view_model.level_label,
                "已确认",
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
        has_confirmed_chapters = bool(tuple(self.adapter.session.confirmed_chapters))
        can_execute = (
            state is SessionState.READY_TO_RESOLVE
            and has_confirmed_chapters
            and self._chapter_review_completed
        )
        self.select_pdf_button.setEnabled(not is_busy)
        self.accept_button.setEnabled(can_confirm and self._selected_candidate() is not None)
        self.reject_button.setEnabled(can_confirm and self._selected_candidate() is not None)
        self.add_manual_button.setEnabled(can_confirm)
        self.update_confirmed_button.setEnabled(
            state is SessionState.READY_TO_RESOLVE
            and self._editing_confirmed_chapter_index is not None
        )
        self.edit_confirmed_button.setEnabled(has_confirmed_chapters)
        self.remove_confirmed_button.setEnabled(has_confirmed_chapters)
        self.confirm_button.setEnabled(state is SessionState.READY_TO_RESOLVE and has_confirmed_chapters)
        self.split_button.setEnabled(can_execute and not is_busy)

    def _set_busy(self, is_busy: bool) -> None:
        self.select_pdf_button.setEnabled(not is_busy)
        self.accept_button.setEnabled(not is_busy)
        self.reject_button.setEnabled(not is_busy)
        self.add_manual_button.setEnabled(not is_busy)
        self.update_confirmed_button.setEnabled(not is_busy)
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

    def _selected_confirmed_chapter_with_index(self) -> tuple[int, Any] | None:
        selected_rows = self.chapters_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        chapters = tuple(self.adapter.session.confirmed_chapters)
        if row < 0 or row >= len(chapters):
            return None
        return row, chapters[row]

    def _show_selected_chapter_source(self) -> None:
        selected = self._selected_confirmed_chapter_with_index()
        if selected is None:
            self.confirmed_chapter_source_label.setText("来源：-")
            return
        chapter = selected[1]
        view_model = format_chapter(chapter)
        self.confirmed_chapter_source_label.setText(f"来源：{view_model.source_label}")

    def _update_current_step(self) -> None:
        state = self.adapter.session.state
        if (
            self._chapter_review_completed
            and state is SessionState.READY_TO_RESOLVE
            and tuple(self.adapter.session.confirmed_chapters)
        ) or state in {
            SessionState.RESOLVING,
            SessionState.READY_TO_EXECUTE,
            SessionState.EXECUTING,
            SessionState.COMPLETED,
        }:
            text = "当前：步骤 3 拆分 PDF"
        elif self.adapter.session.analysis_result is not None:
            text = "当前：步骤 2 确认章节"
        else:
            text = "当前：步骤 1 选择 PDF"
        self.current_step_label.setText(text)

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


def _candidate_status_label(presentation: Any, *, accepted: bool) -> str:
    if accepted:
        return "已确认"
    if presentation.hidden_by_default:
        return "建议核对"
    return "推荐"


def _quality_banner_text(view_model: Any) -> str:
    quality_level = view_model.quality_level_label.lower()
    if quality_level == "high":
        message = "PDF 文本质量良好，可以正常分析。"
    elif quality_level == "medium":
        message = "PDF 文本质量一般，建议检查程序发现的章节。"
    elif quality_level == "low":
        message = "这个 PDF 的文本质量较低，章节识别可能不完整。建议检查候选章节。"
    elif quality_level == "none":
        message = "这个 PDF 没有可读取的文本，自动识别章节可能无法工作。你仍可以手动添加章节。"
    else:
        message = "选择 PDF 后会显示文本质量和章节识别建议。"

    details = [
        view_model.text_coverage_label.replace("Text coverage", "文本覆盖率"),
        view_model.readable_pages_label.replace("Readable pages", "可读页面"),
    ]
    if "suspected" in view_model.ocr_risk_label:
        details.append("可能包含 OCR 噪声")
    if view_model.warnings_label:
        details.append(f"提示：{view_model.warnings_label}")
    return f"{message} {'；'.join(details)}"


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
