from __future__ import annotations

from pathlib import Path

import pytest

from pdf_chapter_splitter.application import (
    ManualSplitInput,
    PDFChapterWorkflow,
    ProgressEvent,
    WorkflowStage,
)
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterEvidence,
    ChapterEvidenceType,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf.models import OutlineItem
from pdf_chapter_splitter.splitter import SplitOutput, SplitResult
from pdf_chapter_splitter.archive import ZipResult


def test_analyze_emits_stable_progress_events(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = PDFChapterWorkflow(
        progress_listener=events.append,
        reader_factory=FakeReaderFactory(FakeReader(page_count=10)),
        outline_detector=FakeOutlineDetector(()),
        text_layout_detector=FakeTextDetector((_candidate("Chapter 1", 0),)),
        fusion=FakeFusion((_candidate("Chapter 1", 0),)),
    )

    workflow.analyze(tmp_path / "book.pdf")

    assert _stages(events) == [
        WorkflowStage.READING_PDF,
        WorkflowStage.ANALYZING,
        WorkflowStage.FUSING_CANDIDATES,
        WorkflowStage.WAITING_FOR_CONFIRMATION,
    ]


def test_progress_events_have_valid_stage_and_non_blank_message(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = PDFChapterWorkflow(
        progress_listener=events.append,
        reader_factory=FakeReaderFactory(FakeReader(page_count=10)),
        outline_detector=FakeOutlineDetector(()),
        text_layout_detector=FakeTextDetector((_candidate("Chapter 1", 0),)),
        fusion=FakeFusion((_candidate("Chapter 1", 0),)),
    )

    workflow.analyze(tmp_path / "book.pdf")

    assert events
    assert all(isinstance(event.stage, WorkflowStage) for event in events)
    assert all(event.message.strip() for event in events)


def test_confirm_emits_confirmation_progress_events():
    events: list[ProgressEvent] = []
    candidate = _candidate("Chapter 1", 0)

    PDFChapterWorkflow(progress_listener=events.append).confirm(
        (ChapterConfirmationDecision.accept(candidate),),
        page_count=10,
    )

    assert _stages(events) == [
        WorkflowStage.CONFIRMING,
        WorkflowStage.CONFIRMED,
    ]


def test_resolve_emits_boundary_progress_events():
    events: list[ProgressEvent] = []

    PDFChapterWorkflow(progress_listener=events.append).resolve(
        (Chapter.from_page_number("Chapter 1", 1),),
        page_count=10,
    )

    assert _stages(events) == [
        WorkflowStage.RESOLVING_BOUNDARIES,
        WorkflowStage.RESOLVED,
    ]


def test_execute_with_zip_emits_split_zip_and_completion_events(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = PDFChapterWorkflow(
        progress_listener=events.append,
        splitter=FakeSplitter(),
        zip_creator=FakeZipCreator(),
    )

    workflow.execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3), SplitSegment("Part 2", 3, 5)),
        tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert _stages(events) == [
        WorkflowStage.SPLITTING,
        WorkflowStage.CREATING_ZIP,
        WorkflowStage.EXECUTION_COMPLETED,
    ]


def test_execute_without_zip_does_not_emit_zip_progress_event(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = PDFChapterWorkflow(
        progress_listener=events.append,
        splitter=FakeSplitter(),
        zip_creator=FakeZipCreator(),
    )

    workflow.execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3),),
        tmp_path / "out",
    )

    assert _stages(events) == [
        WorkflowStage.SPLITTING,
        WorkflowStage.EXECUTION_COMPLETED,
    ]


def test_execute_split_event_exposes_segment_total(tmp_path: Path):
    events: list[ProgressEvent] = []
    workflow = PDFChapterWorkflow(
        progress_listener=events.append,
        splitter=FakeSplitter(),
    )

    workflow.execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3), SplitSegment("Part 2", 3, 5)),
        tmp_path / "out",
    )

    split_event = events[0]
    assert split_event.stage is WorkflowStage.SPLITTING
    assert split_event.current is None
    assert split_event.total == 2


def test_workflow_runs_without_progress_listener(tmp_path: Path):
    result = PDFChapterWorkflow(splitter=FakeSplitter()).execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3),),
        tmp_path / "out",
    )

    assert result.split_result.outputs[0].segment == SplitSegment("Part 1", 0, 3)


def test_progress_listener_exception_does_not_break_workflow(tmp_path: Path):
    def broken_listener(event: ProgressEvent) -> None:
        raise RuntimeError("listener failed")

    result = PDFChapterWorkflow(
        progress_listener=broken_listener,
        splitter=FakeSplitter(),
        zip_creator=FakeZipCreator(),
    ).execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3),),
        tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert result.zip_result is not None


def test_manual_path_emits_only_execution_progress_events(tmp_path: Path):
    events: list[ProgressEvent] = []

    PDFChapterWorkflow(
        progress_listener=events.append,
        splitter=FakeSplitter(),
        zip_creator=FakeZipCreator(),
    ).process_manual_ranges(
        tmp_path / "book.pdf",
        (ManualSplitInput("Part 1", 1, 3),),
        tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert _stages(events) == [
        WorkflowStage.SPLITTING,
        WorkflowStage.CREATING_ZIP,
        WorkflowStage.EXECUTION_COMPLETED,
    ]


class FakeReader:
    def __init__(self, page_count: int) -> None:
        self.page_count = page_count
        self.page_texts = ["Readable page text"] * page_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def get_metadata(self) -> dict[str, str]:
        return {}

    def get_outline(self) -> list[OutlineItem]:
        return []

    def get_page_text(self, page_index: int) -> str:
        return self.page_texts[page_index]

    def get_all_page_text(self) -> list[str]:
        return list(self.page_texts)


class FakeReaderFactory:
    def __init__(self, reader: FakeReader) -> None:
        self.reader = reader

    def __call__(self, path: Path):
        return self.reader


class FakeOutlineDetector:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates

    def detect(self, outline_items: list[OutlineItem]) -> tuple[ChapterCandidate, ...]:
        return self.candidates


class FakeTextDetector:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates

    def detect(self, reader: FakeReader) -> tuple[ChapterCandidate, ...]:
        return self.candidates


class FakeFusion:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates

    def fuse(self, candidates: tuple[ChapterCandidate, ...]) -> tuple[ChapterCandidate, ...]:
        return self.candidates


class FakeSplitter:
    def split(
        self,
        input_path: Path,
        segments: tuple[SplitSegment, ...],
        output_directory: Path,
    ) -> SplitResult:
        return SplitResult(
            input_path=input_path,
            output_directory=output_directory,
            outputs=(
                SplitOutput(
                    segment=segments[0],
                    output_path=output_directory / "Part 1.pdf",
                ),
            ),
        )


class FakeZipCreator:
    def create(self, split_result: SplitResult, output_zip_path: Path) -> ZipResult:
        return ZipResult(
            input_files=tuple(output.output_path for output in split_result.outputs),
            output_zip_path=output_zip_path,
        )


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


def _stages(events: list[ProgressEvent]) -> list[WorkflowStage]:
    return [event.stage for event in events]
