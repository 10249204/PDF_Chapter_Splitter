from __future__ import annotations

from dataclasses import replace

from pdf_chapter_splitter.application import AnalysisSummary, CandidatePresentationPolicy
from pdf_chapter_splitter.chapters import (
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)
from pdf_chapter_splitter.pdf import PDFTextQualityLevel, PDFTextQualityReport


def test_analysis_summary_counts_candidate_sources_and_quality_signals():
    candidates = (
        _candidate(
            "Chapter 1",
            0,
            ChapterCandidateSource.TEXT_LAYOUT,
            0.92,
            structure_type=ChapterStructureType.PRIMARY_CHAPTER,
        ),
        _candidate(
            "Chapter 2",
            8,
            ChapterCandidateSource.OUTLINE,
            0.97,
            sources=(ChapterCandidateSource.OUTLINE, ChapterCandidateSource.TEXT_LAYOUT),
            structure_type=ChapterStructureType.PRIMARY_CHAPTER,
        ),
        _candidate(
            "Chapter 3 ........ 21",
            1,
            ChapterCandidateSource.TEXT_LAYOUT,
            0.42,
            quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
        ),
        _candidate(
            "10.1525_9780520386976-001",
            30,
            ChapterCandidateSource.OUTLINE,
            0.2,
            quality_flags=(
                ChapterCandidateQualityFlag.POOR_TITLE_QUALITY,
                ChapterCandidateQualityFlag.DOI_OR_FILE_TITLE,
            ),
        ),
        _candidate("Manual chapter", 40, ChapterCandidateSource.MANUAL, 1.0),
    )

    summary = AnalysisSummary.from_candidates(
        candidates,
        text_quality_report=_quality_report(PDFTextQualityLevel.HIGH),
    )

    assert summary.text_quality_report.quality_level is PDFTextQualityLevel.HIGH
    assert summary.candidate_count == 5
    assert summary.primary_chapter_candidate_count == 2
    assert summary.toc_suspected_candidate_count == 1
    assert summary.low_quality_candidate_count == 2
    assert summary.poor_title_candidate_count == 1
    assert summary.manual_candidate_count == 1
    assert summary.outline_candidate_count == 2
    assert summary.text_layout_candidate_count == 3
    assert summary.fused_candidate_count == 5


def test_analysis_summary_handles_empty_candidates():
    summary = AnalysisSummary.from_candidates((), text_quality_report=None)

    assert summary.candidate_count == 0
    assert summary.primary_chapter_candidate_count == 0
    assert summary.toc_suspected_candidate_count == 0
    assert summary.low_quality_candidate_count == 0
    assert summary.manual_candidate_count == 0
    assert summary.outline_candidate_count == 0
    assert summary.text_layout_candidate_count == 0
    assert summary.fused_candidate_count == 0
    assert summary.text_quality_report is None


def test_presentation_policy_shows_primary_candidate_by_default():
    candidate = _candidate(
        "Chapter 1",
        0,
        ChapterCandidateSource.OUTLINE,
        0.95,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )

    presentation = CandidatePresentationPolicy().present((candidate,))[0]

    assert presentation.candidate is candidate
    assert presentation.visible is True
    assert presentation.hidden_by_default is False
    assert presentation.collapsed is False
    assert "primary chapter" in presentation.display_reason


def test_presentation_policy_keeps_toc_candidate_but_hides_it_by_default():
    candidate = _candidate(
        "Chapter 1 ........ 12",
        0,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.44,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )

    presentation = CandidatePresentationPolicy().present((candidate,))[0]

    assert presentation.candidate is candidate
    assert presentation.visible is False
    assert presentation.hidden_by_default is True
    assert presentation.collapsed is True
    assert "suspected table of contents page" in presentation.display_reason


def test_presentation_policy_keeps_primary_toc_candidate_visible_with_warning():
    candidate = _candidate(
        "Chapter 1",
        0,
        ChapterCandidateSource.OUTLINE,
        0.91,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )

    presentation = CandidatePresentationPolicy().present((candidate,))[0]

    assert presentation.visible is True
    assert presentation.hidden_by_default is False
    assert "suspected table of contents page" in presentation.display_reason


def test_presentation_policy_hides_non_primary_and_poor_title_candidates_by_default():
    section = _candidate(
        "1.1 Motivation",
        3,
        ChapterCandidateSource.OUTLINE,
        0.7,
        structure_type=ChapterStructureType.SECTION,
        quality_flags=(ChapterCandidateQualityFlag.NON_PRIMARY_STRUCTURE,),
    )
    poor_title = _candidate(
        "10.1525_9780520386976-001",
        10,
        ChapterCandidateSource.OUTLINE,
        0.2,
        quality_flags=(ChapterCandidateQualityFlag.POOR_TITLE_QUALITY,),
    )

    presentations = CandidatePresentationPolicy().present((section, poor_title))

    assert [presentation.visible for presentation in presentations] == [False, False]
    assert [presentation.hidden_by_default for presentation in presentations] == [True, True]
    assert [presentation.collapsed for presentation in presentations] == [True, True]


def test_presentation_policy_show_all_makes_every_candidate_visible_without_deleting_flags():
    primary = _candidate(
        "Chapter 1",
        0,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.9,
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
    )
    toc = _candidate(
        "Chapter 2 ........ 18",
        1,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.45,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )

    presentations = CandidatePresentationPolicy().present((primary, toc), show_all=True)

    assert [presentation.candidate for presentation in presentations] == [primary, toc]
    assert [presentation.visible for presentation in presentations] == [True, True]
    assert presentations[1].hidden_by_default is True
    assert toc.quality_flags == (ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,)


def test_presentation_policy_does_not_mutate_original_candidate():
    candidate = _candidate(
        "1.1 Motivation",
        3,
        ChapterCandidateSource.OUTLINE,
        0.7,
        structure_type=ChapterStructureType.SECTION,
        quality_flags=(ChapterCandidateQualityFlag.NON_PRIMARY_STRUCTURE,),
    )
    before = replace(candidate)

    CandidatePresentationPolicy().present((candidate,))

    assert candidate == before


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
                evidence_type=ChapterEvidenceType.TEXT_PATTERN,
                description="test evidence",
                page_index=start_page_index,
                text=title,
            ),
        ),
        sources=sources,
        structure_type=structure_type,
        quality_flags=quality_flags,
    )


def _quality_report(quality_level: PDFTextQualityLevel) -> PDFTextQualityReport:
    return PDFTextQualityReport(
        page_count=10,
        pages_with_text=10,
        text_coverage_ratio=1.0,
        total_characters=1000,
        average_characters_per_text_page=100.0,
        readable_page_ratio=1.0,
        quality_level=quality_level,
        likely_scanned=False,
        likely_ocr=False,
        warnings=(),
    )
