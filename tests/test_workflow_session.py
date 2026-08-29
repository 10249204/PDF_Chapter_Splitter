from __future__ import annotations

from pathlib import Path

import pytest

from pdf_chapter_splitter.application import (
    AnalysisResult,
    ApplicationError,
    InvalidSessionStateError,
    ManualSplitInput,
    ProcessingResult,
    ProgressEvent,
    SessionState,
    WorkflowError,
    WorkflowSession,
    WorkflowStage,
)
from pdf_chapter_splitter.chapters import (
    BoundaryResolution,
    BoundaryResolutionResult,
    Chapter,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterConfirmationResult,
    ChapterEvidence,
    ChapterEvidenceType,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFOpenError
from pdf_chapter_splitter.splitter import SplitOutput, SplitResult


def test_session_starts_idle_without_result_data():
    session = WorkflowSession(workflow=FakeWorkflow())

    assert session.state is SessionState.IDLE
    assert session.input_path is None
    assert session.analysis_result is None
    assert session.candidates == ()
    assert session.confirmed_chapters == ()
    assert session.boundary_result is None
    assert session.segments == ()
    assert session.processing_result is None
    assert session.error is None


def test_analyze_delegates_to_workflow_and_stores_candidates(tmp_path: Path):
    candidate = _candidate("Chapter 1", 0)
    analysis = AnalysisResult(tmp_path / "book.pdf", 12, {"title": "Book"}, (candidate,))
    workflow = FakeWorkflow(analysis_result=analysis)
    session = WorkflowSession(workflow=workflow)

    result = session.analyze(tmp_path / "book.pdf")

    assert result is analysis
    assert workflow.calls == [("analyze", tmp_path / "book.pdf")]
    assert session.state is SessionState.WAITING_FOR_CONFIRMATION
    assert session.input_path == tmp_path / "book.pdf"
    assert session.analysis_result is analysis
    assert session.candidates == (candidate,)
    assert session.error is None


def test_analyze_does_not_create_confirmed_chapters(tmp_path: Path):
    candidate = _candidate("Chapter 1", 0)
    analysis = AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate,))
    session = WorkflowSession(workflow=FakeWorkflow(analysis_result=analysis))

    session.analyze(tmp_path / "book.pdf")

    assert session.confirmed_chapters == ()
    assert not hasattr(session.analysis_result, "chapters")


def test_analyze_failure_sets_failed_state_and_preserves_cause(tmp_path: Path):
    cause = PDFOpenError("missing PDF")
    session = WorkflowSession(workflow=FakeWorkflow(analyze_error=cause))

    with pytest.raises(WorkflowError) as exc_info:
        session.analyze(tmp_path / "missing.pdf")

    error = exc_info.value
    assert session.state is SessionState.FAILED
    assert session.error is error
    assert error.stage is WorkflowStage.READING_PDF
    assert error.cause is cause
    assert error.__cause__ is cause


def test_accept_candidate_delegates_confirmation_and_ready_to_resolve(tmp_path: Path):
    candidate = _candidate("Chapter 1", 0)
    chapter = Chapter.from_page_number("Chapter 1", 1)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate,)),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")

    result = session.accept_candidate(candidate, title="Chapter 1", start_page_number=1)

    assert result.accepted_chapters == (chapter,)
    assert workflow.calls[-1] == (
        "confirm",
        (ChapterConfirmationDecision.accept(candidate, title="Chapter 1", start_page_number=1),),
        10,
    )
    assert session.state is SessionState.READY_TO_RESOLVE
    assert session.confirmation_result is result
    assert session.confirmed_chapters == (chapter,)


def test_reject_candidate_keeps_session_waiting_when_no_chapter_is_accepted(tmp_path: Path):
    candidate = _candidate("Preface", 0)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate,)),
        confirmation_result=ChapterConfirmationResult((), (candidate,), ()),
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")

    result = session.reject_candidate(candidate)

    assert result.rejected_candidates == (candidate,)
    assert session.confirmed_chapters == ()
    assert session.state is SessionState.WAITING_FOR_CONFIRMATION


def test_add_manual_chapter_delegates_to_workflow_and_ready_to_resolve(tmp_path: Path):
    chapter = Chapter.from_page_number("Appendix", 8)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        manual_chapter=chapter,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")

    result = session.add_manual_chapter("Appendix", start_page_number=8, level=2)

    assert result.accepted_chapters == (chapter,)
    assert workflow.calls[-1] == ("create_manual_chapter", "Appendix", 8, 2, 10)
    assert session.state is SessionState.READY_TO_RESOLVE
    assert session.confirmed_chapters == (chapter,)


def test_update_confirmed_chapter_replaces_existing_chapter_through_workflow(tmp_path: Path):
    first = Chapter.from_page_number("Chapter 1", 1)
    replacement = Chapter.from_page_number("Chapter 1 Edited", 2, level=2)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        confirmation_result=ChapterConfirmationResult((first,), (), ()),
        manual_chapter=replacement,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))

    result = session.update_confirmed_chapter(
        0,
        title="Chapter 1 Edited",
        start_page_number=2,
        level=2,
    )

    assert result.accepted_chapters == (replacement,)
    assert workflow.calls[-1] == ("create_manual_chapter", "Chapter 1 Edited", 2, 2, 10)
    assert session.state is SessionState.READY_TO_RESOLVE


def test_remove_confirmed_chapter_deletes_selected_chapter_without_touching_candidates(tmp_path: Path):
    first = Chapter.from_page_number("Chapter 1", 1)
    second = Chapter.from_page_number("Chapter 2", 5)
    candidate = _candidate("Chapter 1", 0)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate,)),
        confirmation_result=ChapterConfirmationResult((first, second), (), ()),
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(candidate),))

    result = session.remove_confirmed_chapter(0)

    assert result.accepted_chapters == (second,)
    assert session.candidates == (candidate,)
    assert session.state is SessionState.READY_TO_RESOLVE


def test_batch_confirm_delegates_to_workflow_and_stores_confirmation_result(tmp_path: Path):
    candidate_1 = _candidate("Chapter 1", 0)
    candidate_2 = _candidate("Chapter 2", 3)
    chapter = Chapter.from_page_number("Chapter 1", 1)
    decision_1 = ChapterConfirmationDecision.accept(candidate_1)
    decision_2 = ChapterConfirmationDecision.reject(candidate_2)
    confirmation = ChapterConfirmationResult((chapter,), (candidate_2,), ())
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (candidate_1, candidate_2)),
        confirmation_result=confirmation,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")

    result = session.confirm((decision_1, decision_2))

    assert result is confirmation
    assert workflow.calls[-1] == ("confirm", (decision_1, decision_2), 10)
    assert session.state is SessionState.READY_TO_RESOLVE
    assert session.confirmed_chapters == (chapter,)


def test_resolve_delegates_to_workflow_and_stores_segments(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    segment = SplitSegment("Chapter 1", 0, 10)
    boundary_result = BoundaryResolutionResult((BoundaryResolution(chapter, segment),))
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        boundary_result=boundary_result,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))

    result = session.resolve()

    assert result is boundary_result
    assert workflow.calls[-1] == ("resolve", (chapter,), 10)
    assert session.state is SessionState.READY_TO_EXECUTE
    assert session.boundary_result is boundary_result
    assert session.segments == (segment,)
    assert session.processing_result is None


def test_execute_delegates_to_workflow_and_stores_processing_result(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    segment = SplitSegment("Chapter 1", 0, 10)
    processing_result = _processing_result(tmp_path / "book.pdf", tmp_path / "out", segment)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        boundary_result=BoundaryResolutionResult((BoundaryResolution(chapter, segment),)),
        processing_result=processing_result,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))
    session.resolve()

    result = session.execute(output_directory=tmp_path / "out", zip_path=tmp_path / "book.zip")

    assert result is processing_result
    assert workflow.calls[-1] == (
        "execute",
        tmp_path / "book.pdf",
        (segment,),
        tmp_path / "out",
        tmp_path / "book.zip",
    )
    assert session.state is SessionState.COMPLETED
    assert session.processing_result is processing_result
    assert session.error is None


def test_execute_failure_sets_failed_state_and_error(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    segment = SplitSegment("Chapter 1", 0, 10)
    error = WorkflowError("split failed", stage=WorkflowStage.SPLITTING)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        boundary_result=BoundaryResolutionResult((BoundaryResolution(chapter, segment),)),
        execute_error=error,
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))
    session.resolve()

    with pytest.raises(WorkflowError):
        session.execute(output_directory=tmp_path / "out")

    assert session.state is SessionState.FAILED
    assert session.error is error
    assert session.processing_result is None


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("resolve", {}),
        ("execute", {"output_directory": Path("out")}),
    ],
)
def test_idle_session_rejects_invalid_operations(method_name: str, kwargs: dict[str, Path]):
    session = WorkflowSession(workflow=FakeWorkflow())

    with pytest.raises(InvalidSessionStateError) as exc_info:
        getattr(session, method_name)(**kwargs)

    assert session.state is SessionState.FAILED
    assert session.error is exc_info.value


def test_waiting_for_confirmation_cannot_execute(tmp_path: Path):
    session = WorkflowSession(
        workflow=FakeWorkflow(
            analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),))
        )
    )
    session.analyze(tmp_path / "book.pdf")

    with pytest.raises(InvalidSessionStateError):
        session.execute(output_directory=tmp_path / "out")

    assert session.state is SessionState.FAILED


def test_ready_to_resolve_cannot_execute_before_resolve(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    session = WorkflowSession(
        workflow=FakeWorkflow(
            analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
            confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        )
    )
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))

    with pytest.raises(InvalidSessionStateError):
        session.execute(output_directory=tmp_path / "out")

    assert session.state is SessionState.FAILED


def test_completed_session_cannot_execute_again(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    segment = SplitSegment("Chapter 1", 0, 10)
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),)),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        boundary_result=BoundaryResolutionResult((BoundaryResolution(chapter, segment),)),
        processing_result=_processing_result(tmp_path / "book.pdf", tmp_path / "out", segment),
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "book.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))
    session.resolve()
    session.execute(output_directory=tmp_path / "out")

    with pytest.raises(InvalidSessionStateError):
        session.execute(output_directory=tmp_path / "out")

    assert session.state is SessionState.FAILED


def test_reanalyze_clears_previous_session_data(tmp_path: Path):
    chapter = Chapter.from_page_number("Chapter 1", 1)
    old_segment = SplitSegment("Chapter 1", 0, 10)
    first_analysis = AnalysisResult(tmp_path / "first.pdf", 10, {}, (_candidate("Chapter 1", 0),))
    second_candidate = _candidate("Chapter A", 2)
    second_analysis = AnalysisResult(tmp_path / "second.pdf", 20, {}, (second_candidate,))
    workflow = FakeWorkflow(
        analysis_results=(first_analysis, second_analysis),
        confirmation_result=ChapterConfirmationResult((chapter,), (), ()),
        boundary_result=BoundaryResolutionResult((BoundaryResolution(chapter, old_segment),)),
        processing_result=_processing_result(tmp_path / "first.pdf", tmp_path / "out", old_segment),
    )
    session = WorkflowSession(workflow=workflow)
    session.analyze(tmp_path / "first.pdf")
    session.confirm((ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0)),))
    session.resolve()
    session.execute(output_directory=tmp_path / "out")

    session.analyze(tmp_path / "second.pdf")

    assert session.state is SessionState.WAITING_FOR_CONFIRMATION
    assert session.input_path == tmp_path / "second.pdf"
    assert session.analysis_result is second_analysis
    assert session.candidates == (second_candidate,)
    assert session.confirmation_result is None
    assert session.confirmed_chapters == ()
    assert session.boundary_result is None
    assert session.segments == ()
    assert session.processing_result is None
    assert session.error is None


def test_successful_analyze_after_failure_clears_error(tmp_path: Path):
    cause = PDFOpenError("missing PDF")
    analysis = AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),))
    workflow = FakeWorkflow(analyze_errors=(cause, None), analysis_results=(analysis,))
    session = WorkflowSession(workflow=workflow)

    with pytest.raises(WorkflowError):
        session.analyze(tmp_path / "missing.pdf")

    session.analyze(tmp_path / "book.pdf")

    assert session.state is SessionState.WAITING_FOR_CONFIRMATION
    assert session.error is None
    assert session.analysis_result is analysis


def test_process_manual_ranges_delegates_to_workflow_and_completes(tmp_path: Path):
    manual_inputs = (ManualSplitInput("Part 1", 1, 3),)
    segment = SplitSegment("Part 1", 0, 3)
    processing_result = _processing_result(tmp_path / "book.pdf", tmp_path / "manual-out", segment)
    workflow = FakeWorkflow(processing_result=processing_result)
    session = WorkflowSession(workflow=workflow)

    result = session.process_manual_ranges(
        tmp_path / "book.pdf",
        manual_inputs,
        tmp_path / "manual-out",
        zip_path=tmp_path / "manual.zip",
    )

    assert result is processing_result
    assert workflow.calls == [
        (
            "process_manual_ranges",
            tmp_path / "book.pdf",
            manual_inputs,
            tmp_path / "manual-out",
            tmp_path / "manual.zip",
        )
    ]
    assert session.state is SessionState.COMPLETED
    assert session.input_path == tmp_path / "book.pdf"
    assert session.processing_result is processing_result
    assert session.analysis_result is None
    assert session.candidates == ()


def test_session_uses_existing_progress_event_contract(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),))
    )
    session = WorkflowSession(workflow=workflow, progress_listener=events.append)

    session.analyze(tmp_path / "book.pdf")

    assert events == [ProgressEvent(WorkflowStage.READING_PDF, "Reading PDF")]


def test_progress_listener_exception_does_not_break_session(tmp_path: Path):
    def broken_listener(event: ProgressEvent) -> None:
        raise RuntimeError("listener failed")

    workflow = FakeWorkflow(
        analysis_result=AnalysisResult(tmp_path / "book.pdf", 10, {}, (_candidate("Chapter 1", 0),))
    )
    session = WorkflowSession(workflow=workflow, progress_listener=broken_listener)

    result = session.analyze(tmp_path / "book.pdf")

    assert result.page_count == 10
    assert session.state is SessionState.WAITING_FOR_CONFIRMATION


def test_programming_errors_are_not_wrapped_or_saved(tmp_path: Path):
    session = WorkflowSession(workflow=FakeWorkflow(analyze_error=TypeError("bug")))

    with pytest.raises(TypeError):
        session.analyze(tmp_path / "book.pdf")

    assert session.state is SessionState.ANALYZING
    assert session.error is None


class FakeWorkflow:
    def __init__(
        self,
        *,
        analysis_result: AnalysisResult | None = None,
        analysis_results: tuple[AnalysisResult, ...] = (),
        analyze_error: Exception | None = None,
        analyze_errors: tuple[Exception | None, ...] = (),
        confirmation_result: ChapterConfirmationResult | None = None,
        manual_chapter: Chapter | None = None,
        boundary_result: BoundaryResolutionResult | None = None,
        processing_result: ProcessingResult | None = None,
        execute_error: ApplicationError | None = None,
    ) -> None:
        self.analysis_result = analysis_result
        self.analysis_results = list(analysis_results)
        self.analyze_error = analyze_error
        self.analyze_errors = list(analyze_errors)
        self.confirmation_result = confirmation_result
        self.manual_chapter = manual_chapter
        self.boundary_result = boundary_result
        self.processing_result = processing_result
        self.execute_error = execute_error
        self.progress_listener = None
        self.calls = []

    def analyze(self, input_path: Path) -> AnalysisResult:
        self.calls.append(("analyze", input_path))
        self._emit(ProgressEvent(WorkflowStage.READING_PDF, "Reading PDF"))
        if self.analyze_errors:
            error = self.analyze_errors.pop(0)
            if error is not None:
                raise error
        if self.analyze_error is not None:
            raise self.analyze_error
        if self.analysis_results:
            return self.analysis_results.pop(0)
        if self.analysis_result is not None:
            return self.analysis_result
        return AnalysisResult(input_path, 10, {}, ())

    def confirm(
        self,
        decisions: tuple[ChapterConfirmationDecision, ...],
        page_count: int | None = None,
    ) -> ChapterConfirmationResult:
        self.calls.append(("confirm", decisions, page_count))
        if self.confirmation_result is not None:
            return self.confirmation_result
        return ChapterConfirmationResult((), (), ())

    def create_manual_chapter(
        self,
        title: str,
        start_page_number: int,
        *,
        level: int = 1,
        page_count: int | None = None,
    ) -> Chapter:
        self.calls.append(("create_manual_chapter", title, start_page_number, level, page_count))
        if self.manual_chapter is not None:
            return self.manual_chapter
        return Chapter.from_page_number(title, start_page_number, level=level)

    def resolve(
        self,
        chapters: tuple[Chapter, ...],
        page_count: int,
    ) -> BoundaryResolutionResult:
        self.calls.append(("resolve", chapters, page_count))
        if self.boundary_result is not None:
            return self.boundary_result
        return BoundaryResolutionResult(())

    def execute(
        self,
        input_path: Path,
        segments: tuple[SplitSegment, ...],
        output_directory: Path,
        *,
        zip_path: Path | None = None,
    ) -> ProcessingResult:
        self.calls.append(("execute", input_path, segments, output_directory, zip_path))
        if self.execute_error is not None:
            raise self.execute_error
        if self.processing_result is not None:
            return self.processing_result
        return _processing_result(input_path, output_directory, segments[0])

    def process_manual_ranges(
        self,
        input_path: Path,
        manual_inputs: tuple[ManualSplitInput, ...],
        output_directory: Path,
        *,
        zip_path: Path | None = None,
    ) -> ProcessingResult:
        self.calls.append(
            ("process_manual_ranges", input_path, manual_inputs, output_directory, zip_path)
        )
        if self.processing_result is not None:
            return self.processing_result
        segment = SplitSegment(manual_inputs[0].title, 0, 1)
        return _processing_result(input_path, output_directory, segment)

    def _emit(self, event: ProgressEvent) -> None:
        if self.progress_listener is None:
            return
        try:
            self.progress_listener(event)
        except Exception:
            return


def _candidate(title: str, start_page_index: int) -> ChapterCandidate:
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=ChapterCandidateSource.TEXT_LAYOUT,
        confidence=0.9,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.TEXT_PATTERN,
                description="text layout evidence",
                page_index=start_page_index,
                text=title,
            ),
        ),
    )


def _processing_result(
    input_path: Path,
    output_directory: Path,
    segment: SplitSegment,
) -> ProcessingResult:
    split_result = SplitResult(
        input_path=input_path,
        output_directory=output_directory,
        outputs=(SplitOutput(segment, output_directory / f"{segment.title}.pdf"),),
    )
    return ProcessingResult(
        input_path=input_path,
        output_directory=output_directory,
        split_result=split_result,
    )
