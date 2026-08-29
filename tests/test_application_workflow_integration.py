from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import fitz
import pytest

from pdf_chapter_splitter.application import ManualSplitInput, PDFChapterWorkflow
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterEvidenceType,
)
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFOpenError, PyMuPDFReader


def test_real_pdf_analysis_returns_page_count_and_candidates(
    workflow_smoke_pdf_path: Path,
):
    result = PDFChapterWorkflow().analyze(workflow_smoke_pdf_path)

    assert result.page_count == 10
    assert result.metadata["title"] == "Workflow Smoke Book"
    assert result.candidates != ()


def test_real_pdf_analysis_returns_text_layout_candidates_with_evidence(
    workflow_smoke_pdf_path: Path,
):
    result = PDFChapterWorkflow().analyze(workflow_smoke_pdf_path)
    text_layout_candidates = [
        candidate
        for candidate in result.candidates
        if ChapterCandidateSource.TEXT_LAYOUT in candidate.sources
    ]

    assert text_layout_candidates
    for candidate in text_layout_candidates:
        assert candidate.title
        assert 0 <= candidate.start_page_index < result.page_count
        assert 0.0 <= candidate.confidence <= 1.0
        assert candidate.evidences != ()


def test_real_pdf_analysis_detects_expected_chapter_start_pages(
    workflow_smoke_pdf_path: Path,
):
    result = PDFChapterWorkflow().analyze(workflow_smoke_pdf_path)

    detected_by_title = {
        candidate.title: candidate.start_page_index
        for candidate in result.candidates
        if ChapterCandidateSource.TEXT_LAYOUT in candidate.sources
    }

    assert detected_by_title["Chapter 1 Introduction"] == 1
    assert detected_by_title["Chapter 2 Methods"] == 4
    assert detected_by_title["Chapter 3 Results"] == 7


def test_real_pdf_analysis_does_not_auto_confirm_chapters(
    workflow_smoke_pdf_path: Path,
):
    result = PDFChapterWorkflow().analyze(workflow_smoke_pdf_path)

    assert result.candidates != ()
    assert not hasattr(result, "chapters")
    assert not hasattr(result, "accepted_chapters")


def test_real_manual_path_splits_pdf_into_expected_page_counts(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    result = PDFChapterWorkflow().process_manual_ranges(
        workflow_smoke_pdf_path,
        (
            ManualSplitInput("Part 1", 1, 3),
            ManualSplitInput("Part 2", 4, 7),
            ManualSplitInput("Part 3", 8, 10),
        ),
        tmp_path / "manual-output",
    )

    assert [output.output_path.name for output in result.split_result.outputs] == [
        "Part 1.pdf",
        "Part 2.pdf",
        "Part 3.pdf",
    ]
    assert [_page_count(output.output_path) for output in result.split_result.outputs] == [
        3,
        4,
        3,
    ]


def test_real_manual_path_preserves_expected_output_page_content(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    result = PDFChapterWorkflow().process_manual_ranges(
        workflow_smoke_pdf_path,
        (
            ManualSplitInput("Part 1", 1, 3),
            ManualSplitInput("Part 2", 4, 7),
            ManualSplitInput("Part 3", 8, 10),
        ),
        tmp_path / "manual-output",
    )

    output_paths = [output.output_path for output in result.split_result.outputs]
    assert "Page 1" in _page_text(output_paths[0], 0)
    assert "Page 4" in _page_text(output_paths[1], 0)
    assert "Page 8" in _page_text(output_paths[2], 0)


def test_real_manual_path_creates_zip_with_expected_pdf_entries(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    result = PDFChapterWorkflow().process_manual_ranges(
        workflow_smoke_pdf_path,
        (
            ManualSplitInput("Part 1", 1, 3),
            ManualSplitInput("Part 2", 4, 7),
            ManualSplitInput("Part 3", 8, 10),
        ),
        tmp_path / "manual-output",
        zip_path=tmp_path / "manual-output" / "book.zip",
    )

    assert result.zip_result is not None
    assert result.zip_result.output_zip_path.exists()
    with ZipFile(result.zip_result.output_zip_path) as archive:
        assert archive.namelist() == ["Part 1.pdf", "Part 2.pdf", "Part 3.pdf"]
        extracted_part_2 = tmp_path / "extracted" / "Part 2.pdf"
        archive.extract("Part 2.pdf", extracted_part_2.parent)

    assert _page_count(extracted_part_2) == 4
    assert "Page 4" in _page_text(extracted_part_2, 0)


def test_real_automatic_path_requires_explicit_confirmation_before_split(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    workflow = PDFChapterWorkflow()
    analysis = workflow.analyze(workflow_smoke_pdf_path)
    chapter_candidates = _expected_chapter_candidates(analysis.candidates)

    confirmation = workflow.confirm(
        tuple(ChapterConfirmationDecision.accept(candidate) for candidate in chapter_candidates),
        page_count=analysis.page_count,
    )
    resolution = workflow.resolve(confirmation.accepted_chapters, page_count=analysis.page_count)

    assert resolution.segments == (
        SplitSegment("Chapter 1 Introduction", 1, 4),
        SplitSegment("Chapter 2 Methods", 4, 7),
        SplitSegment("Chapter 3 Results", 7, 10),
    )

    result = workflow.execute(
        workflow_smoke_pdf_path,
        resolution.segments,
        tmp_path / "automatic-output",
        zip_path=tmp_path / "automatic-output" / "chapters.zip",
    )

    assert [_page_count(output.output_path) for output in result.split_result.outputs] == [
        3,
        3,
        3,
    ]
    assert result.zip_result is not None
    assert result.zip_result.output_zip_path.exists()


def test_real_confirmed_chapters_path_can_split_and_zip_without_detection(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    chapters = (
        Chapter.from_page_number("Chapter 1 Introduction", 2),
        Chapter.from_page_number("Chapter 2 Methods", 5),
        Chapter.from_page_number("Chapter 3 Results", 8),
    )

    result = PDFChapterWorkflow().process_confirmed_chapters(
        workflow_smoke_pdf_path,
        chapters,
        page_count=10,
        output_directory=tmp_path / "confirmed-output",
        zip_path=tmp_path / "confirmed-output" / "confirmed.zip",
    )

    assert [_page_count(output.output_path) for output in result.split_result.outputs] == [
        3,
        3,
        3,
    ]
    assert result.zip_result is not None
    with ZipFile(result.zip_result.output_zip_path) as archive:
        assert archive.namelist() == [
            "Chapter 1 Introduction.pdf",
            "Chapter 2 Methods.pdf",
            "Chapter 3 Results.pdf",
        ]


def test_real_manual_path_does_not_modify_original_pdf(
    workflow_smoke_pdf_path: Path,
    tmp_path: Path,
):
    before_hash = hashlib.sha256(workflow_smoke_pdf_path.read_bytes()).hexdigest()
    before_page_count = _page_count(workflow_smoke_pdf_path)

    PDFChapterWorkflow().process_manual_ranges(
        workflow_smoke_pdf_path,
        (ManualSplitInput("Part 1", 1, 3),),
        tmp_path / "manual-output",
    )

    after_hash = hashlib.sha256(workflow_smoke_pdf_path.read_bytes()).hexdigest()
    assert before_page_count == 10
    assert _page_count(workflow_smoke_pdf_path) == 10
    assert after_hash == before_hash


def test_real_workflow_analyze_keeps_pdf_open_error_for_missing_pdf(tmp_path: Path):
    with pytest.raises(PDFOpenError):
        PDFChapterWorkflow().analyze(tmp_path / "missing.pdf")


def test_real_workflow_resolve_keeps_boundary_error():
    with pytest.raises(ValueError):
        PDFChapterWorkflow().resolve(
            (Chapter.from_page_number("Chapter 1", 11),),
            page_count=10,
        )


@pytest.fixture
def workflow_smoke_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "workflow-smoke.pdf"
    document = fitz.open()
    chapter_titles = {
        2: "Chapter 1 Introduction",
        5: "Chapter 2 Methods",
        8: "Chapter 3 Results",
    }

    for page_number in range(1, 11):
        page = document.new_page()
        if page_number in chapter_titles:
            page.insert_text(
                (72, 72),
                chapter_titles[page_number],
                fontsize=24,
                fontname="helv",
            )
            page.insert_text(
                (72, 180),
                f"Page {page_number} chapter body text with enough words for baseline sizing.",
                fontsize=12,
                fontname="helv",
            )
        else:
            page.insert_text(
                (72, 140),
                f"Page {page_number} ordinary body text with enough words for baseline sizing.",
                fontsize=12,
                fontname="helv",
            )

    document.set_metadata({"title": "Workflow Smoke Book"})
    document.set_toc(
        [
            [1, "Chapter 1 Introduction", 2],
            [1, "Chapter 2 Methods", 5],
            [1, "Chapter 3 Results", 8],
        ]
    )
    document.save(path)
    document.close()
    return path


def _page_count(path: Path) -> int:
    with PyMuPDFReader(path) as reader:
        return reader.page_count


def _page_text(path: Path, page_index: int) -> str:
    with PyMuPDFReader(path) as reader:
        return reader.get_page_text(page_index)


def _expected_chapter_candidates(candidates):
    expected_titles = {
        "Chapter 1 Introduction",
        "Chapter 2 Methods",
        "Chapter 3 Results",
    }
    selected = tuple(
        candidate
        for candidate in candidates
        if candidate.title in expected_titles
        and ChapterEvidenceType.TEXT_PATTERN
        in {evidence.evidence_type for evidence in candidate.evidences}
    )
    assert {candidate.title for candidate in selected} == expected_titles
    return tuple(sorted(selected, key=lambda candidate: candidate.start_page_index))
