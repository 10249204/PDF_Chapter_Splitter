"""Application-level orchestration for PDF chapter splitting."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pdf_chapter_splitter.archive import ArchiveError, ZipCreator, ZipResult
from pdf_chapter_splitter.application.analysis import AnalysisSummary
from pdf_chapter_splitter.chapters import (
    CandidateFusion,
    Chapter,
    ChapterBoundaryResolver,
    ChapterCandidate,
    ChapterConfirmationDecision,
    ChapterConfirmationResult,
    ChapterConfirmationService,
    OutlineCandidateDetector,
    TextLayoutCandidateDetector,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import (
    PDFReaderError,
    PDFTextQualityDiagnostic,
    PDFTextQualityReport,
    PyMuPDFReader,
)
from pdf_chapter_splitter.splitter import PDFSplitter, PDFSplitError, SplitResult


class WorkflowStage(StrEnum):
    """High-level workflow stages for progress and application errors."""

    READING_PDF = "reading_pdf"
    ANALYZING = "analyzing"
    FUSING_CANDIDATES = "fusing_candidates"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    RESOLVING_BOUNDARIES = "resolving_boundaries"
    RESOLVED = "resolved"
    SPLITTING = "splitting"
    CREATING_ZIP = "creating_zip"
    EXECUTION_COMPLETED = "execution_completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """A lightweight application progress snapshot."""

    stage: WorkflowStage
    message: str
    current: int | None = None
    total: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, WorkflowStage):
            raise ValueError("stage must be a WorkflowStage")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must not be blank")
        if self.current is not None and self.current < 0:
            raise ValueError("current must be 0 or greater when present")
        if self.total is not None and self.total < 0:
            raise ValueError("total must be 0 or greater when present")
        if self.current is not None and self.total is not None and self.current > self.total:
            raise ValueError("current must be less than or equal to total")


class ApplicationError(Exception):
    """Application-layer error with stage and optional lower-level cause."""

    def __init__(
        self,
        message: str,
        *,
        stage: WorkflowStage = WorkflowStage.FAILED,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.cause = cause


class WorkflowError(ApplicationError):
    """Application workflow errors that are not owned by lower layers."""


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """PDF analysis output before any user confirmation."""

    input_path: Path
    page_count: int
    metadata: dict[str, str]
    candidates: tuple[ChapterCandidate, ...]
    text_quality_report: PDFTextQualityReport | None = None
    summary: AnalysisSummary | None = None


@dataclass(frozen=True, slots=True)
class ManualSplitInput:
    """User-facing manual split range using 1-based inclusive page numbers."""

    title: str
    start_page_number: int
    end_page_number: int


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Completed split operation, with optional ZIP output."""

    input_path: Path
    output_directory: Path
    split_result: SplitResult
    zip_result: ZipResult | None = None


class PDFChapterWorkflow:
    """Coordinate existing PDF, chapter, split, and archive components."""

    def __init__(
        self,
        *,
        reader_factory: Callable[[Path], Any] = PyMuPDFReader,
        outline_detector: Any | None = None,
        text_layout_detector: Any | None = None,
        fusion: Any | None = None,
        text_quality_diagnostic: Any | None = None,
        confirmation_service: Any | None = None,
        boundary_resolver: Any | None = None,
        splitter: Any | None = None,
        zip_creator: Any | None = None,
        progress_listener: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        self.reader_factory = reader_factory
        self.outline_detector = (
            OutlineCandidateDetector() if outline_detector is None else outline_detector
        )
        self.text_layout_detector = (
            TextLayoutCandidateDetector() if text_layout_detector is None else text_layout_detector
        )
        self.fusion = CandidateFusion() if fusion is None else fusion
        self.text_quality_diagnostic = (
            PDFTextQualityDiagnostic() if text_quality_diagnostic is None else text_quality_diagnostic
        )
        self.confirmation_service = (
            ChapterConfirmationService() if confirmation_service is None else confirmation_service
        )
        self.boundary_resolver = (
            ChapterBoundaryResolver() if boundary_resolver is None else boundary_resolver
        )
        self.splitter = PDFSplitter() if splitter is None else splitter
        self.zip_creator = ZipCreator() if zip_creator is None else zip_creator
        self.progress_listener = progress_listener

    def analyze(self, input_path: str | Path) -> AnalysisResult:
        """Read a PDF and return fused candidates without confirming chapters."""

        normalized_input_path = Path(input_path)
        self._emit_progress(WorkflowStage.READING_PDF, "Reading PDF")
        with self.reader_factory(normalized_input_path) as reader:
            page_count = reader.page_count
            metadata = dict(reader.get_metadata())
            text_quality_report = self.text_quality_diagnostic.analyze(reader)
            self._emit_progress(WorkflowStage.ANALYZING, "Analyzing chapter candidates")
            outline_candidates = tuple(self.outline_detector.detect(reader.get_outline()))
            text_candidates = tuple(self.text_layout_detector.detect(reader))

        self._emit_progress(WorkflowStage.FUSING_CANDIDATES, "Fusing chapter candidates")
        candidates = tuple(self.fusion.fuse(outline_candidates + text_candidates))
        summary = AnalysisSummary.from_candidates(
            candidates,
            text_quality_report=text_quality_report,
        )
        self._emit_progress(
            WorkflowStage.WAITING_FOR_CONFIRMATION,
            "Waiting for user confirmation",
            total=len(candidates),
        )
        return AnalysisResult(
            input_path=normalized_input_path,
            page_count=page_count,
            metadata=metadata,
            candidates=candidates,
            text_quality_report=text_quality_report,
            summary=summary,
        )

    def confirm(
        self,
        decisions: Iterable[ChapterConfirmationDecision],
        page_count: int | None = None,
    ) -> ChapterConfirmationResult:
        """Apply explicit user confirmation decisions to candidates."""

        normalized_decisions = tuple(decisions)
        self._emit_progress(
            WorkflowStage.CONFIRMING,
            "Confirming chapter candidates",
            total=len(normalized_decisions),
        )
        result = self.confirmation_service.apply_decisions(
            normalized_decisions,
            page_count=page_count,
        )
        self._emit_progress(
            WorkflowStage.CONFIRMED,
            "Chapter candidates confirmed",
            total=len(result.accepted_chapters),
        )
        return result

    def create_manual_chapter(
        self,
        title: str,
        start_page_number: int,
        *,
        level: int = 1,
        page_count: int | None = None,
    ) -> Chapter:
        """Create a confirmed chapter from explicit user input."""

        return self.confirmation_service.create_manual(
            title=title,
            start_page_number=start_page_number,
            level=level,
            page_count=page_count,
        )

    def resolve(
        self,
        chapters: Iterable[Chapter],
        page_count: int,
    ):
        """Resolve confirmed chapters into split segments."""

        normalized_chapters = tuple(chapters)
        self._emit_progress(
            WorkflowStage.RESOLVING_BOUNDARIES,
            "Resolving chapter boundaries",
            total=len(normalized_chapters),
        )
        result = self.boundary_resolver.resolve(normalized_chapters, page_count=page_count)
        self._emit_progress(
            WorkflowStage.RESOLVED,
            "Chapter boundaries resolved",
            total=len(result.segments),
        )
        return result

    def build_manual_segments(
        self,
        manual_inputs: Iterable[ManualSplitInput],
    ) -> tuple[SplitSegment, ...]:
        """Convert explicit manual page ranges directly into split segments."""

        return tuple(
            SplitSegment.from_page_numbers(
                title=manual_input.title,
                start_page_number=manual_input.start_page_number,
                end_page_number=manual_input.end_page_number,
            )
            for manual_input in manual_inputs
        )

    def execute(
        self,
        input_path: str | Path,
        segments: Iterable[SplitSegment],
        output_directory: str | Path,
        *,
        zip_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Split PDF segments and optionally create a ZIP archive."""

        normalized_input_path = Path(input_path)
        normalized_output_directory = Path(output_directory)
        normalized_segments = tuple(segments)
        if not normalized_segments:
            raise WorkflowError(
                "at least one split segment is required",
                stage=WorkflowStage.SPLITTING,
            )

        self._emit_progress(
            WorkflowStage.SPLITTING,
            "Splitting PDF",
            total=len(normalized_segments),
        )
        try:
            split_result = self.splitter.split(
                normalized_input_path,
                normalized_segments,
                normalized_output_directory,
            )
        except (PDFReaderError, PDFSplitError) as exc:
            raise WorkflowError(
                "Unable to split PDF",
                stage=WorkflowStage.SPLITTING,
                cause=exc,
            ) from exc

        zip_result = None
        if zip_path is not None:
            self._emit_progress(WorkflowStage.CREATING_ZIP, "Creating ZIP archive")
            try:
                zip_result = self.zip_creator.create(split_result, Path(zip_path))
            except ArchiveError as exc:
                raise WorkflowError(
                    "Unable to create ZIP archive",
                    stage=WorkflowStage.CREATING_ZIP,
                    cause=exc,
                ) from exc

        self._emit_progress(WorkflowStage.EXECUTION_COMPLETED, "Execution completed")

        return ProcessingResult(
            input_path=normalized_input_path,
            output_directory=normalized_output_directory,
            split_result=split_result,
            zip_result=zip_result,
        )

    def process_confirmed_chapters(
        self,
        input_path: str | Path,
        chapters: Iterable[Chapter],
        *,
        page_count: int,
        output_directory: str | Path,
        zip_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Run the automatic path after external confirmation has produced chapters."""

        resolution = self.resolve(chapters, page_count=page_count)
        return self.execute(
            input_path,
            resolution.segments,
            output_directory,
            zip_path=zip_path,
        )

    def process_manual_ranges(
        self,
        input_path: str | Path,
        manual_inputs: Iterable[ManualSplitInput],
        output_directory: str | Path,
        *,
        zip_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Run the manual page-range path without candidate or chapter conversion."""

        segments = self.build_manual_segments(manual_inputs)
        return self.execute(
            input_path,
            segments,
            output_directory,
            zip_path=zip_path,
        )

    def _emit_progress(
        self,
        stage: WorkflowStage,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        if self.progress_listener is None:
            return

        event = ProgressEvent(
            stage=stage,
            message=message,
            current=current,
            total=total,
        )
        try:
            self.progress_listener(event)
        except Exception:
            return


__all__ = [
    "ApplicationError",
    "AnalysisResult",
    "AnalysisSummary",
    "ManualSplitInput",
    "PDFChapterWorkflow",
    "ProgressEvent",
    "ProcessingResult",
    "WorkflowError",
    "WorkflowStage",
]
