from __future__ import annotations

from pathlib import Path

import pytest

from pdf_chapter_splitter.application import (
    AnalysisResult,
    ManualSplitInput,
    PDFChapterWorkflow,
    ProcessingResult,
    WorkflowError,
)
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFOpenError, PDFTextQualityReport, PDFTextQualityLevel
from pdf_chapter_splitter.pdf.models import OutlineItem
from pdf_chapter_splitter.splitter import SplitOutput, SplitResult
from pdf_chapter_splitter.archive import ZipResult


def test_analyze_pdf_returns_page_count_metadata_and_fused_candidates(tmp_path: Path):
    outline_candidate = _candidate("Chapter 1", 0, ChapterCandidateSource.OUTLINE, 0.95)
    text_candidate = _candidate("Chapter 1", 0, ChapterCandidateSource.TEXT_LAYOUT, 0.9)
    fused_candidate = _candidate(
        "Chapter 1",
        0,
        ChapterCandidateSource.TEXT_LAYOUT,
        1.0,
        sources=(ChapterCandidateSource.TEXT_LAYOUT, ChapterCandidateSource.OUTLINE),
    )
    reader_factory = FakeReaderFactory(
        FakeReader(
            page_count=12,
            metadata={"title": "Book"},
            outline=[OutlineItem("Chapter 1", 1, 0)],
        )
    )
    outline_detector = FakeOutlineDetector((outline_candidate,))
    text_detector = FakeTextDetector((text_candidate,))
    fusion = FakeFusion((fused_candidate,))
    text_quality_report = PDFTextQualityReport(
        page_count=12,
        pages_with_text=12,
        text_coverage_ratio=1.0,
        total_characters=1200,
        average_characters_per_text_page=100.0,
        readable_page_ratio=1.0,
        quality_level=PDFTextQualityLevel.HIGH,
        likely_scanned=False,
        likely_ocr=False,
        warnings=(),
    )
    workflow = PDFChapterWorkflow(
        reader_factory=reader_factory,
        outline_detector=outline_detector,
        text_layout_detector=text_detector,
        fusion=fusion,
        text_quality_diagnostic=FakeTextQualityDiagnostic(text_quality_report),
    )

    result = workflow.analyze(tmp_path / "book.pdf")

    assert result.input_path == tmp_path / "book.pdf"
    assert result.page_count == 12
    assert result.metadata == {"title": "Book"}
    assert result.candidates == (fused_candidate,)
    assert result.text_quality_report is text_quality_report
    assert outline_detector.calls == [([OutlineItem("Chapter 1", 1, 0)],)]
    assert text_detector.calls == [(reader_factory.reader,)]
    assert fusion.calls == [(outline_candidate, text_candidate)]
    assert workflow.text_quality_diagnostic.calls == [reader_factory.reader]
    assert reader_factory.reader.closed is True


def test_analyze_pdf_returns_summary_consistent_with_candidates_and_text_quality(tmp_path: Path):
    outline_candidate = _candidate(
        "Chapter 1",
        0,
        ChapterCandidateSource.OUTLINE,
        0.95,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )
    toc_candidate = _candidate(
        "Chapter 2 ........ 12",
        1,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.42,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )
    text_quality_report = PDFTextQualityReport(
        page_count=12,
        pages_with_text=12,
        text_coverage_ratio=1.0,
        total_characters=1200,
        average_characters_per_text_page=100.0,
        readable_page_ratio=1.0,
        quality_level=PDFTextQualityLevel.HIGH,
        likely_scanned=False,
        likely_ocr=False,
        warnings=(),
    )
    workflow = PDFChapterWorkflow(
        reader_factory=FakeReaderFactory(FakeReader(page_count=12)),
        outline_detector=FakeOutlineDetector((outline_candidate,)),
        text_layout_detector=FakeTextDetector((toc_candidate,)),
        fusion=FakeFusion((outline_candidate, toc_candidate)),
        text_quality_diagnostic=FakeTextQualityDiagnostic(text_quality_report),
    )

    result = workflow.analyze(tmp_path / "book.pdf")

    assert result.summary is not None
    assert result.summary.text_quality_report is text_quality_report
    assert result.summary.candidate_count == len(result.candidates)
    assert result.summary.primary_chapter_candidate_count == 1
    assert result.summary.toc_suspected_candidate_count == 1
    assert result.summary.text_layout_candidate_count == 1
    assert result.summary.outline_candidate_count == 1


def test_analyze_pdf_does_not_produce_chapters_without_user_confirmation(tmp_path: Path):
    candidate = _candidate("Chapter 1", 0, ChapterCandidateSource.TEXT_LAYOUT, 1.0)
    workflow = PDFChapterWorkflow(
        reader_factory=FakeReaderFactory(FakeReader(page_count=10)),
        outline_detector=FakeOutlineDetector(()),
        text_layout_detector=FakeTextDetector((candidate,)),
        fusion=FakeFusion((candidate,)),
    )

    result = workflow.analyze(tmp_path / "book.pdf")

    assert result.candidates == (candidate,)
    assert not hasattr(result, "chapters")


def test_confirm_accepts_candidate_through_confirmation_service():
    candidate = _candidate("Chapter 1", 0, ChapterCandidateSource.TEXT_LAYOUT, 0.9)
    workflow = PDFChapterWorkflow()

    result = workflow.confirm(
        (ChapterConfirmationDecision.accept(candidate),),
        page_count=10,
    )

    assert [chapter.title for chapter in result.accepted_chapters] == ["Chapter 1"]
    assert result.accepted_chapters[0].start_page_index == 0
    assert result.rejected_candidates == ()


def test_confirm_rejects_candidate_without_creating_chapter():
    candidate = _candidate("Table 1", 3, ChapterCandidateSource.TEXT_LAYOUT, 0.7)
    workflow = PDFChapterWorkflow()

    result = workflow.confirm((ChapterConfirmationDecision.reject(candidate),), page_count=10)

    assert result.accepted_chapters == ()
    assert result.rejected_candidates == (candidate,)
    assert result.outcomes[0].chapter is None


def test_confirm_accepts_edited_title():
    candidate = _candidate("Chapter 3", 20, ChapterCandidateSource.OUTLINE, 0.95)
    workflow = PDFChapterWorkflow()

    result = workflow.confirm(
        (ChapterConfirmationDecision.accept(candidate, title="第三章 文件系统"),),
        page_count=100,
    )

    assert result.accepted_chapters[0].title == "第三章 文件系统"


def test_confirm_accepts_edited_one_based_start_page():
    candidate = _candidate("Chapter 3", 20, ChapterCandidateSource.OUTLINE, 0.95)
    workflow = PDFChapterWorkflow()

    result = workflow.confirm(
        (ChapterConfirmationDecision.accept(candidate, start_page_number=22),),
        page_count=100,
    )

    assert result.accepted_chapters[0].start_page_index == 21
    assert result.accepted_chapters[0].gui_page_number == 22


def test_create_manual_chapter_delegates_to_confirmation_service():
    workflow = PDFChapterWorkflow()

    chapter = workflow.create_manual_chapter(
        title="Appendix",
        start_page_number=12,
        level=2,
        page_count=20,
    )

    assert chapter.title == "Appendix"
    assert chapter.start_page_index == 11
    assert chapter.gui_page_number == 12
    assert chapter.level == 2
    assert chapter.provenance is not None
    assert chapter.provenance.confirmed_from_candidate is False


def test_resolve_confirmed_chapters_returns_boundary_segments():
    workflow = PDFChapterWorkflow()
    chapters = (
        Chapter.from_page_number("Chapter 1", 10),
        Chapter.from_page_number("Chapter 2", 45),
    )

    result = workflow.resolve(chapters, page_count=100)

    assert result.segments == (
        SplitSegment("Chapter 1", 9, 44),
        SplitSegment("Chapter 2", 44, 100),
    )


def test_build_manual_segments_uses_user_page_ranges_directly():
    workflow = PDFChapterWorkflow()

    segments = workflow.build_manual_segments(
        (
            ManualSplitInput("Part 1", 1, 30),
            ManualSplitInput("Part 2", 31, 50),
        )
    )

    assert segments == (
        SplitSegment("Part 1", 0, 30),
        SplitSegment("Part 2", 30, 50),
    )


def test_manual_path_does_not_produce_chapters_or_call_boundary_resolver():
    boundary_resolver = FakeBoundaryResolver()
    workflow = PDFChapterWorkflow(boundary_resolver=boundary_resolver)

    segments = workflow.build_manual_segments((ManualSplitInput("Part 1", 1, 30),))

    assert segments == (SplitSegment("Part 1", 0, 30),)
    assert boundary_resolver.calls == []
    assert all(not isinstance(segment, Chapter) for segment in segments)


def test_execute_calls_pdf_splitter_with_segments(tmp_path: Path):
    splitter = FakeSplitter()
    workflow = PDFChapterWorkflow(splitter=splitter)
    segments = (SplitSegment("Part 1", 0, 3),)

    result = workflow.execute(tmp_path / "book.pdf", segments, tmp_path / "out")

    assert splitter.calls == [(tmp_path / "book.pdf", segments, tmp_path / "out")]
    assert result.split_result == splitter.result


def test_execute_calls_zip_creator_when_zip_path_is_provided(tmp_path: Path):
    splitter = FakeSplitter()
    zip_creator = FakeZipCreator()
    workflow = PDFChapterWorkflow(splitter=splitter, zip_creator=zip_creator)
    segments = (SplitSegment("Part 1", 0, 3),)

    result = workflow.execute(
        tmp_path / "book.pdf",
        segments,
        tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert zip_creator.calls == [(splitter.result, tmp_path / "book.zip")]
    assert result.zip_result == zip_creator.result


def test_execute_returns_processing_result_with_split_and_optional_zip(tmp_path: Path):
    splitter = FakeSplitter()
    zip_creator = FakeZipCreator()
    workflow = PDFChapterWorkflow(splitter=splitter, zip_creator=zip_creator)

    result = workflow.execute(
        tmp_path / "book.pdf",
        (SplitSegment("Part 1", 0, 3),),
        tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert result == ProcessingResult(
        input_path=tmp_path / "book.pdf",
        output_directory=tmp_path / "out",
        split_result=splitter.result,
        zip_result=zip_creator.result,
    )


def test_analyze_keeps_pdf_open_error_from_reader_factory(tmp_path: Path):
    workflow = PDFChapterWorkflow(reader_factory=FailingReaderFactory(PDFOpenError("missing PDF")))

    with pytest.raises(PDFOpenError):
        workflow.analyze(tmp_path / "missing.pdf")


def test_resolve_keeps_boundary_error_from_resolver():
    workflow = PDFChapterWorkflow(boundary_resolver=FakeBoundaryResolver(error=ValueError("bad boundary")))

    with pytest.raises(ValueError):
        workflow.resolve((Chapter.from_page_number("Chapter 1", 1),), page_count=0)


def test_execute_without_segments_fails_without_creating_entire_pdf_segment(tmp_path: Path):
    splitter = FakeSplitter()
    workflow = PDFChapterWorkflow(splitter=splitter)

    with pytest.raises(WorkflowError):
        workflow.execute(tmp_path / "book.pdf", (), tmp_path / "out")

    assert splitter.calls == []


def test_analyze_does_not_auto_accept_high_confidence_candidate(tmp_path: Path):
    candidate = _candidate("Chapter 1", 0, ChapterCandidateSource.TEXT_LAYOUT, 1.0)
    workflow = PDFChapterWorkflow(
        reader_factory=FakeReaderFactory(FakeReader(page_count=10)),
        outline_detector=FakeOutlineDetector(()),
        text_layout_detector=FakeTextDetector((candidate,)),
        fusion=FakeFusion((candidate,)),
    )

    result = workflow.analyze(tmp_path / "book.pdf")

    assert result.candidates[0].confidence == 1.0
    assert not hasattr(result, "accepted_chapters")
    assert not hasattr(result, "chapters")


def test_resolve_stage_does_not_call_pdf_splitter():
    splitter = FakeSplitter()
    workflow = PDFChapterWorkflow(splitter=splitter)

    workflow.resolve((Chapter.from_page_number("Chapter 1", 1),), page_count=10)

    assert splitter.calls == []


def test_manual_path_does_not_call_candidate_detectors():
    outline_detector = FakeOutlineDetector(())
    text_detector = FakeTextDetector(())
    workflow = PDFChapterWorkflow(
        outline_detector=outline_detector,
        text_layout_detector=text_detector,
    )

    workflow.build_manual_segments((ManualSplitInput("Part 1", 1, 10),))

    assert outline_detector.calls == []
    assert text_detector.calls == []


def test_process_confirmed_chapters_resolves_then_executes(tmp_path: Path):
    boundary_resolver = FakeBoundaryResolver(
        segments=(SplitSegment("Chapter 1", 0, 10),)
    )
    splitter = FakeSplitter()
    zip_creator = FakeZipCreator()
    workflow = PDFChapterWorkflow(
        boundary_resolver=boundary_resolver,
        splitter=splitter,
        zip_creator=zip_creator,
    )
    chapters = (Chapter.from_page_number("Chapter 1", 1),)

    result = workflow.process_confirmed_chapters(
        tmp_path / "book.pdf",
        chapters,
        page_count=10,
        output_directory=tmp_path / "out",
        zip_path=tmp_path / "book.zip",
    )

    assert boundary_resolver.calls == [(chapters, 10)]
    assert splitter.calls == [
        (tmp_path / "book.pdf", (SplitSegment("Chapter 1", 0, 10),), tmp_path / "out")
    ]
    assert zip_creator.calls == [(splitter.result, tmp_path / "book.zip")]
    assert result.split_result == splitter.result
    assert result.zip_result == zip_creator.result


def test_process_manual_ranges_builds_segments_then_executes(tmp_path: Path):
    splitter = FakeSplitter()
    workflow = PDFChapterWorkflow(splitter=splitter)

    workflow.process_manual_ranges(
        tmp_path / "book.pdf",
        (ManualSplitInput("Part 1", 1, 10), ManualSplitInput("Part 2", 11, 20)),
        tmp_path / "out",
    )

    assert splitter.calls == [
        (
            tmp_path / "book.pdf",
            (SplitSegment("Part 1", 0, 10), SplitSegment("Part 2", 10, 20)),
            tmp_path / "out",
        )
    ]


class FakeReader:
    def __init__(
        self,
        page_count: int,
        metadata: dict[str, str] | None = None,
        outline: list[OutlineItem] | None = None,
        page_texts: list[str] | None = None,
    ) -> None:
        self.page_count = page_count
        self.metadata = metadata or {}
        self.outline = outline or []
        self.page_texts = page_texts or ["Readable page text"] * page_count
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def get_metadata(self) -> dict[str, str]:
        return self.metadata

    def get_outline(self) -> list[OutlineItem]:
        return self.outline

    def get_page_text(self, page_index: int) -> str:
        return self.page_texts[page_index]

    def get_all_page_text(self) -> list[str]:
        return list(self.page_texts)

    def close(self) -> None:
        self.closed = True


class FakeReaderFactory:
    def __init__(self, reader: FakeReader) -> None:
        self.reader = reader
        self.calls: list[Path] = []

    def __call__(self, path: Path):
        self.calls.append(path)
        return self.reader


class FailingReaderFactory:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def __call__(self, path: Path):
        raise self.error


class FakeOutlineDetector:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[list[OutlineItem]]] = []

    def detect(self, outline_items: list[OutlineItem]) -> tuple[ChapterCandidate, ...]:
        self.calls.append((outline_items,))
        return self.candidates


class FakeTextDetector:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[FakeReader]] = []

    def detect(self, reader: FakeReader) -> tuple[ChapterCandidate, ...]:
        self.calls.append((reader,))
        return self.candidates


class FakeFusion:
    def __init__(self, candidates: tuple[ChapterCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[ChapterCandidate, ...]] = []

    def fuse(self, candidates: tuple[ChapterCandidate, ...]) -> tuple[ChapterCandidate, ...]:
        self.calls.append(candidates)
        return self.candidates


class FakeTextQualityDiagnostic:
    def __init__(self, report: PDFTextQualityReport) -> None:
        self.report = report
        self.calls: list[FakeReader] = []

    def analyze(self, reader: FakeReader) -> PDFTextQualityReport:
        self.calls.append(reader)
        return self.report


class FakeBoundaryResolver:
    def __init__(
        self,
        segments: tuple[SplitSegment, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.segments = segments
        self.error = error
        self.calls: list[tuple[tuple[Chapter, ...], int]] = []

    def resolve(self, chapters, page_count):
        normalized_chapters = tuple(chapters)
        self.calls.append((normalized_chapters, page_count))
        if self.error is not None:
            raise self.error
        return FakeBoundaryResult(self.segments)


class FakeBoundaryResult:
    def __init__(self, segments: tuple[SplitSegment, ...]) -> None:
        self.segments = segments


class FakeSplitter:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple[SplitSegment, ...], Path]] = []
        self.result = SplitResult(
            input_path=Path("book.pdf"),
            output_directory=Path("out"),
            outputs=(
                SplitOutput(
                    segment=SplitSegment("Part 1", 0, 3),
                    output_path=Path("out") / "Part 1.pdf",
                ),
            ),
        )

    def split(
        self,
        input_path: Path,
        segments: tuple[SplitSegment, ...],
        output_directory: Path,
    ) -> SplitResult:
        self.calls.append((input_path, segments, output_directory))
        return self.result


class FakeZipCreator:
    def __init__(self) -> None:
        self.calls: list[tuple[SplitResult, Path]] = []
        self.result = ZipResult(
            input_files=(Path("out") / "Part 1.pdf",),
            output_zip_path=Path("book.zip"),
        )

    def create(self, split_result: SplitResult, output_zip_path: Path) -> ZipResult:
        self.calls.append((split_result, output_zip_path))
        return self.result


def _candidate(
    title: str,
    start_page_index: int,
    source: ChapterCandidateSource,
    confidence: float,
    *,
    sources: tuple[ChapterCandidateSource, ...] | None = None,
    structure_type: ChapterStructureType = ChapterStructureType.UNKNOWN,
    quality_flags: tuple[ChapterCandidateQualityFlag, ...] = (),
) -> ChapterCandidate:
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=source,
        confidence=confidence,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=_evidence_type(source),
                description=f"{source.value} evidence",
                page_index=start_page_index,
                text=title,
            ),
        ),
        sources=sources,
        structure_type=structure_type,
        quality_flags=quality_flags,
    )


def _evidence_type(source: ChapterCandidateSource) -> ChapterEvidenceType:
    if source is ChapterCandidateSource.OUTLINE:
        return ChapterEvidenceType.OUTLINE
    if source is ChapterCandidateSource.MANUAL:
        return ChapterEvidenceType.MANUAL
    return ChapterEvidenceType.TEXT_PATTERN
