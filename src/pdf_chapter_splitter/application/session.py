"""Application session state for future GUI adapters."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pdf_chapter_splitter.application.workflow import (
    AnalysisResult,
    ApplicationError,
    ManualSplitInput,
    PDFChapterWorkflow,
    ProcessingResult,
    ProgressEvent,
    WorkflowError,
    WorkflowStage,
)
from pdf_chapter_splitter.chapters import (
    BoundaryResolutionResult,
    Chapter,
    ChapterCandidate,
    ChapterConfirmationDecision,
    ChapterConfirmationResult,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFReaderError


class SessionState(StrEnum):
    """Application session state across a user-facing workflow."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CONFIRMING = "confirming"
    READY_TO_RESOLVE = "ready_to_resolve"
    RESOLVING = "resolving"
    READY_TO_EXECUTE = "ready_to_execute"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class InvalidSessionStateError(ApplicationError):
    """Raised when a session method is called in an invalid state."""

    def __init__(
        self,
        message: str,
        *,
        current_state: SessionState,
    ) -> None:
        super().__init__(message, stage=WorkflowStage.FAILED)
        self.current_state = current_state


class WorkflowSession:
    """Hold application-level workflow state for future GUI adapters."""

    def __init__(
        self,
        *,
        workflow: Any | None = None,
        progress_listener: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        self.workflow = (
            PDFChapterWorkflow(progress_listener=progress_listener)
            if workflow is None
            else workflow
        )
        if workflow is not None and progress_listener is not None:
            setattr(self.workflow, "progress_listener", progress_listener)

        self.state = SessionState.IDLE
        self.input_path: Path | None = None
        self.analysis_result: AnalysisResult | None = None
        self.confirmation_result: ChapterConfirmationResult | None = None
        self.boundary_result: BoundaryResolutionResult | None = None
        self.processing_result: ProcessingResult | None = None
        self.error: ApplicationError | None = None
        self._confirmation_decisions: tuple[ChapterConfirmationDecision, ...] = ()

    @property
    def candidates(self) -> tuple[ChapterCandidate, ...]:
        if self.analysis_result is None:
            return ()
        return self.analysis_result.candidates

    @property
    def confirmed_chapters(self) -> tuple[Chapter, ...]:
        if self.confirmation_result is None:
            return ()
        return self.confirmation_result.accepted_chapters

    @property
    def segments(self) -> tuple[SplitSegment, ...]:
        if self.boundary_result is None:
            return ()
        return self.boundary_result.segments

    def analyze(self, input_path: str | Path) -> AnalysisResult:
        """Analyze a PDF and store candidates for external confirmation."""

        normalized_input_path = Path(input_path)
        self._reset_for_new_input(normalized_input_path)
        self.state = SessionState.ANALYZING
        try:
            result = self.workflow.analyze(normalized_input_path)
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except PDFReaderError as exc:
            error = WorkflowError(
                "Unable to analyze PDF",
                stage=WorkflowStage.READING_PDF,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        self.analysis_result = result
        self.state = SessionState.WAITING_FOR_CONFIRMATION
        self.error = None
        return result

    def accept_candidate(
        self,
        candidate: ChapterCandidate,
        *,
        title: str | None = None,
        start_page_index: int | None = None,
        start_page_number: int | None = None,
    ) -> ChapterConfirmationResult:
        """Accept one candidate through the workflow confirmation service."""

        decision = ChapterConfirmationDecision.accept(
            candidate,
            title=title,
            start_page_index=start_page_index,
            start_page_number=start_page_number,
        )
        return self._append_confirmation_decision(decision)

    def reject_candidate(
        self,
        candidate: ChapterCandidate,
    ) -> ChapterConfirmationResult:
        """Reject one candidate through the workflow confirmation service."""

        return self._append_confirmation_decision(ChapterConfirmationDecision.reject(candidate))

    def accept_candidates(
        self,
        candidates: Iterable[ChapterCandidate],
    ) -> ChapterConfirmationResult:
        """Accept multiple candidates through one explicit user action."""

        decisions = tuple(
            ChapterConfirmationDecision.accept(candidate)
            for candidate in candidates
        )
        return self._append_confirmation_decisions(decisions)

    def reject_candidates(
        self,
        candidates: Iterable[ChapterCandidate],
    ) -> ChapterConfirmationResult:
        """Reject multiple candidates through one explicit user action."""

        decisions = tuple(
            ChapterConfirmationDecision.reject(candidate)
            for candidate in candidates
        )
        return self._append_confirmation_decisions(decisions)

    def add_manual_chapter(
        self,
        title: str,
        *,
        start_page_number: int,
        level: int = 1,
    ) -> ChapterConfirmationResult:
        """Add one user-created confirmed chapter through the workflow."""

        self._ensure_state(
            SessionState.WAITING_FOR_CONFIRMATION,
            SessionState.READY_TO_RESOLVE,
            action="add a manual chapter",
        )
        if self.analysis_result is None:
            self._fail_invalid_state("Cannot add a manual chapter before analysis data is available")

        self.state = SessionState.CONFIRMING
        try:
            chapter = self.workflow.create_manual_chapter(
                title,
                start_page_number,
                level=level,
                page_count=self.analysis_result.page_count,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except ValueError as exc:
            error = WorkflowError(
                "Unable to add manual chapter",
                stage=WorkflowStage.CONFIRMING,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        accepted_chapters = self.confirmed_chapters + (chapter,)
        self.confirmation_result = ChapterConfirmationResult(
            accepted_chapters=accepted_chapters,
            rejected_candidates=(
                ()
                if self.confirmation_result is None
                else self.confirmation_result.rejected_candidates
            ),
            outcomes=(() if self.confirmation_result is None else self.confirmation_result.outcomes),
        )
        self.boundary_result = None
        self.processing_result = None
        self.state = SessionState.READY_TO_RESOLVE
        self.error = None
        return self.confirmation_result

    def update_confirmed_chapter(
        self,
        index: int,
        *,
        title: str,
        start_page_number: int,
        level: int = 1,
    ) -> ChapterConfirmationResult:
        """Replace one confirmed chapter through explicit user editing."""

        self._ensure_state(SessionState.READY_TO_RESOLVE, action="update a confirmed chapter")
        if self.analysis_result is None:
            self._fail_invalid_state("Cannot update a chapter before analysis data is available")
        if index < 0 or index >= len(self.confirmed_chapters):
            raise ValueError("confirmed chapter index is outside valid range")

        self.state = SessionState.CONFIRMING
        try:
            replacement = self.workflow.create_manual_chapter(
                title,
                start_page_number,
                level=level,
                page_count=self.analysis_result.page_count,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except ValueError as exc:
            error = WorkflowError(
                "Unable to update confirmed chapter",
                stage=WorkflowStage.CONFIRMING,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        accepted_chapters = list(self.confirmed_chapters)
        accepted_chapters[index] = replacement
        self.confirmation_result = self._confirmation_result_with_chapters(tuple(accepted_chapters))
        self.boundary_result = None
        self.processing_result = None
        self.state = SessionState.READY_TO_RESOLVE
        self.error = None
        return self.confirmation_result

    def remove_confirmed_chapter(self, index: int) -> ChapterConfirmationResult:
        """Remove one confirmed chapter after explicit user action."""

        self._ensure_state(SessionState.READY_TO_RESOLVE, action="remove a confirmed chapter")
        if index < 0 or index >= len(self.confirmed_chapters):
            raise ValueError("confirmed chapter index is outside valid range")

        accepted_chapters = tuple(
            chapter
            for chapter_index, chapter in enumerate(self.confirmed_chapters)
            if chapter_index != index
        )
        self.confirmation_result = self._confirmation_result_with_chapters(accepted_chapters)
        self.boundary_result = None
        self.processing_result = None
        self.state = (
            SessionState.READY_TO_RESOLVE
            if accepted_chapters
            else SessionState.WAITING_FOR_CONFIRMATION
        )
        self.error = None
        return self.confirmation_result

    def confirm(
        self,
        decisions: Iterable[ChapterConfirmationDecision],
    ) -> ChapterConfirmationResult:
        """Apply a batch of explicit user confirmation decisions."""

        self._ensure_state(
            SessionState.WAITING_FOR_CONFIRMATION,
            SessionState.READY_TO_RESOLVE,
            action="confirm candidates",
        )
        self._confirmation_decisions = tuple(decisions)
        return self._apply_confirmation_decisions()

    def resolve(self) -> BoundaryResolutionResult:
        """Resolve confirmed chapters into split segments through the workflow."""

        self._ensure_state(SessionState.READY_TO_RESOLVE, action="resolve boundaries")
        if self.analysis_result is None:
            self._fail_invalid_state("Cannot resolve before analysis data is available")

        self.state = SessionState.RESOLVING
        try:
            result = self.workflow.resolve(
                self.confirmed_chapters,
                page_count=self.analysis_result.page_count,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except ValueError as exc:
            error = WorkflowError(
                "Unable to resolve chapter boundaries",
                stage=WorkflowStage.RESOLVING_BOUNDARIES,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        self.boundary_result = result
        self.processing_result = None
        self.state = SessionState.READY_TO_EXECUTE
        self.error = None
        return result

    def execute(
        self,
        *,
        output_directory: str | Path,
        zip_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Execute the resolved split plan through the workflow."""

        self._ensure_state(SessionState.READY_TO_EXECUTE, action="execute split")
        if self.input_path is None:
            self._fail_invalid_state("Cannot execute before an input PDF is selected")

        normalized_output_directory = Path(output_directory)
        normalized_zip_path = None if zip_path is None else Path(zip_path)
        self.state = SessionState.EXECUTING
        try:
            result = self.workflow.execute(
                self.input_path,
                self.segments,
                normalized_output_directory,
                zip_path=normalized_zip_path,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise

        self.processing_result = result
        self.state = SessionState.COMPLETED
        self.error = None
        return result

    def process_manual_ranges(
        self,
        input_path: str | Path,
        manual_inputs: Iterable[ManualSplitInput],
        output_directory: str | Path,
        *,
        zip_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Run the manual split path through the workflow."""

        normalized_input_path = Path(input_path)
        normalized_output_directory = Path(output_directory)
        normalized_zip_path = None if zip_path is None else Path(zip_path)
        normalized_manual_inputs = tuple(manual_inputs)
        self._reset_for_new_input(normalized_input_path)
        self.state = SessionState.EXECUTING
        try:
            result = self.workflow.process_manual_ranges(
                normalized_input_path,
                normalized_manual_inputs,
                normalized_output_directory,
                zip_path=normalized_zip_path,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except (PDFReaderError, ValueError) as exc:
            error = WorkflowError(
                "Unable to process manual ranges",
                stage=WorkflowStage.SPLITTING,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        self.processing_result = result
        self.state = SessionState.COMPLETED
        self.error = None
        return result

    def _append_confirmation_decision(
        self,
        decision: ChapterConfirmationDecision,
    ) -> ChapterConfirmationResult:
        return self._append_confirmation_decisions((decision,))

    def _append_confirmation_decisions(
        self,
        decisions: tuple[ChapterConfirmationDecision, ...],
    ) -> ChapterConfirmationResult:
        self._ensure_state(
            SessionState.WAITING_FOR_CONFIRMATION,
            SessionState.READY_TO_RESOLVE,
            action="confirm candidates",
        )
        self._confirmation_decisions = self._confirmation_decisions + decisions
        return self._apply_confirmation_decisions()

    def _apply_confirmation_decisions(self) -> ChapterConfirmationResult:
        if self.analysis_result is None:
            self._fail_invalid_state("Cannot confirm before analysis data is available")

        self.state = SessionState.CONFIRMING
        try:
            result = self.workflow.confirm(
                self._confirmation_decisions,
                page_count=self.analysis_result.page_count,
            )
        except ApplicationError as exc:
            self._mark_failed(exc)
            raise
        except ValueError as exc:
            error = WorkflowError(
                "Unable to confirm chapter candidates",
                stage=WorkflowStage.CONFIRMING,
                cause=exc,
            )
            self._mark_failed(error)
            raise error from exc

        self.confirmation_result = result
        self.boundary_result = None
        self.processing_result = None
        self.state = (
            SessionState.READY_TO_RESOLVE
            if result.accepted_chapters
            else SessionState.WAITING_FOR_CONFIRMATION
        )
        self.error = None
        return result

    def _confirmation_result_with_chapters(
        self,
        accepted_chapters: tuple[Chapter, ...],
    ) -> ChapterConfirmationResult:
        return ChapterConfirmationResult(
            accepted_chapters=accepted_chapters,
            rejected_candidates=(
                ()
                if self.confirmation_result is None
                else self.confirmation_result.rejected_candidates
            ),
            outcomes=(() if self.confirmation_result is None else self.confirmation_result.outcomes),
        )

    def _reset_for_new_input(self, input_path: Path) -> None:
        self.input_path = input_path
        self.analysis_result = None
        self.confirmation_result = None
        self.boundary_result = None
        self.processing_result = None
        self.error = None
        self._confirmation_decisions = ()

    def _ensure_state(
        self,
        *allowed_states: SessionState,
        action: str,
    ) -> None:
        if self.state in allowed_states:
            return
        allowed = ", ".join(state.value for state in allowed_states)
        self._fail_invalid_state(
            f"Cannot {action} while session state is {self.state.value}; expected {allowed}"
        )

    def _fail_invalid_state(self, message: str) -> None:
        error = InvalidSessionStateError(message, current_state=self.state)
        self._mark_failed(error)
        raise error

    def _mark_failed(self, error: ApplicationError) -> None:
        self.error = error
        self.state = SessionState.FAILED


__all__ = [
    "InvalidSessionStateError",
    "SessionState",
    "WorkflowSession",
]
