from __future__ import annotations

import pytest

from pdf_chapter_splitter.chapters import (
    CandidateFusion,
    CandidateFusionConfig,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
)


def test_fusion_merges_same_page_same_title_into_one_candidate():
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((outline, layout))

    assert len(fused) == 1
    assert fused[0].title == "Chapter 3 File System"
    assert fused[0].start_page_index == 20


def test_fusion_merges_adjacent_pages_by_default_and_prefers_text_layout_page():
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((outline, layout))

    assert len(fused) == 1
    assert fused[0].start_page_index == 21
    assert fused[0].source is ChapterCandidateSource.TEXT_LAYOUT


def test_fusion_does_not_merge_pages_beyond_configured_distance():
    early = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    later = _candidate("Chapter 3 File System", 25, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion(CandidateFusionConfig(max_page_distance=1)).fuse((later, early))

    assert [candidate.start_page_index for candidate in fused] == [20, 25]


def test_fusion_merges_titles_with_light_formatting_differences():
    with_colon = _candidate("Chapter 3: File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    without_colon = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)
    spaced_chinese = _candidate("第 3 章 文件系统", 30, ChapterCandidateSource.OUTLINE, 0.95)
    compact_chinese = _candidate("第3章 文件系统", 31, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((with_colon, spaced_chinese, compact_chinese, without_colon))

    assert _signature(fused) == (
        ("Chapter 3 File System", 21, (ChapterCandidateSource.TEXT_LAYOUT, ChapterCandidateSource.OUTLINE)),
        ("第3章 文件系统", 31, (ChapterCandidateSource.TEXT_LAYOUT, ChapterCandidateSource.OUTLINE)),
    )


def test_fusion_does_not_merge_different_chapter_numbers_on_nearby_pages():
    chapter_three = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    chapter_four = _candidate("Chapter 4 Algorithms", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((chapter_four, chapter_three))

    assert [candidate.title for candidate in fused] == [
        "Chapter 3 File System",
        "Chapter 4 Algorithms",
    ]


def test_fusion_merges_evidence_without_dropping_observed_facts():
    outline = _candidate(
        "Chapter 3 File System",
        20,
        ChapterCandidateSource.OUTLINE,
        0.95,
        ChapterEvidenceType.OUTLINE,
    )
    layout = _candidate(
        "Chapter 3 File System",
        21,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.85,
        ChapterEvidenceType.TEXT_PATTERN,
        ChapterEvidenceType.FONT_SIZE,
        ChapterEvidenceType.POSITION,
    )

    fused = CandidateFusion().fuse((outline, layout))

    assert {evidence.evidence_type for evidence in fused[0].evidences} == {
        ChapterEvidenceType.OUTLINE,
        ChapterEvidenceType.TEXT_PATTERN,
        ChapterEvidenceType.FONT_SIZE,
        ChapterEvidenceType.POSITION,
    }


def test_fusion_preserves_all_sources_on_fused_candidate():
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((outline, layout))

    assert fused[0].source is ChapterCandidateSource.TEXT_LAYOUT
    assert fused[0].sources == (
        ChapterCandidateSource.TEXT_LAYOUT,
        ChapterCandidateSource.OUTLINE,
    )
    assert fused[0].original_titles == (
        "Chapter 3 File System",
    )


def test_fusion_prefers_manual_title_page_source_and_confidence():
    manual = _candidate("User Chapter Three", 22, ChapterCandidateSource.MANUAL, 1.0)
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion(CandidateFusionConfig(max_page_distance=2)).fuse((layout, outline, manual))

    assert len(fused) == 1
    assert fused[0].title == "User Chapter Three"
    assert fused[0].start_page_index == 22
    assert fused[0].source is ChapterCandidateSource.MANUAL
    assert fused[0].sources == (
        ChapterCandidateSource.MANUAL,
        ChapterCandidateSource.TEXT_LAYOUT,
        ChapterCandidateSource.OUTLINE,
    )
    assert fused[0].confidence == pytest.approx(1.0)
    assert set(fused[0].original_titles) == {
        "User Chapter Three",
        "Chapter 3 File System",
    }


def test_fusion_confidence_stays_in_range_and_does_not_drop_below_best_input():
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)

    fused = CandidateFusion().fuse((outline, layout))

    assert 0.0 <= fused[0].confidence <= 1.0
    assert fused[0].confidence >= 0.95


def test_fusion_result_does_not_depend_on_input_order():
    outline = _candidate("Chapter 3: File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)
    manual = _candidate("User Chapter Three", 22, ChapterCandidateSource.MANUAL, 1.0)
    config = CandidateFusionConfig(max_page_distance=2)

    left = CandidateFusion(config).fuse((outline, layout, manual))
    right = CandidateFusion(config).fuse((manual, layout, outline))

    assert _signature(left) == _signature(right)


def test_fusion_returns_candidates_sorted_by_page_then_confidence():
    page_100 = _candidate("Chapter 5", 100, ChapterCandidateSource.OUTLINE, 0.95)
    page_20_low = _candidate("Part I", 20, ChapterCandidateSource.OUTLINE, 0.70)
    page_20_high = _candidate("Chapter 1", 20, ChapterCandidateSource.TEXT_LAYOUT, 0.90)
    page_50 = _candidate("Chapter 3", 50, ChapterCandidateSource.OUTLINE, 0.80)

    fused = CandidateFusion().fuse((page_100, page_20_low, page_50, page_20_high))

    assert [(candidate.start_page_index, candidate.confidence, candidate.title) for candidate in fused] == [
        (20, 0.90, "Chapter 1"),
        (20, 0.70, "Part I"),
        (50, 0.80, "Chapter 3"),
        (100, 0.95, "Chapter 5"),
    ]


def test_fusion_keeps_same_page_different_titles_separate():
    part = _candidate("Part I", 20, ChapterCandidateSource.OUTLINE, 0.80)
    chapter = _candidate("Chapter 1", 20, ChapterCandidateSource.TEXT_LAYOUT, 0.90)

    fused = CandidateFusion().fuse((part, chapter))

    assert [candidate.title for candidate in fused] == ["Chapter 1", "Part I"]


def test_fusion_does_not_modify_original_candidates():
    outline = _candidate("Chapter 3 File System", 20, ChapterCandidateSource.OUTLINE, 0.95)
    layout = _candidate("Chapter 3 File System", 21, ChapterCandidateSource.TEXT_LAYOUT, 0.85)
    original_outline = outline
    original_layout = layout

    CandidateFusion().fuse((outline, layout))

    assert outline == original_outline
    assert layout == original_layout
    assert outline.sources == (ChapterCandidateSource.OUTLINE,)
    assert layout.sources == (ChapterCandidateSource.TEXT_LAYOUT,)


def _candidate(
    title: str,
    start_page_index: int,
    source: ChapterCandidateSource,
    confidence: float,
    *evidence_types: ChapterEvidenceType,
) -> ChapterCandidate:
    types = evidence_types or (_default_evidence_type(source),)
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=source,
        confidence=confidence,
        level=1,
        evidences=tuple(
            ChapterEvidence(
                evidence_type=evidence_type,
                description=f"{source.value} evidence for {title}",
                page_index=start_page_index,
                text=title,
            )
            for evidence_type in types
        ),
    )


def _default_evidence_type(source: ChapterCandidateSource) -> ChapterEvidenceType:
    if source is ChapterCandidateSource.OUTLINE:
        return ChapterEvidenceType.OUTLINE
    if source is ChapterCandidateSource.MANUAL:
        return ChapterEvidenceType.MANUAL
    return ChapterEvidenceType.TEXT_PATTERN


def _signature(candidates: tuple[ChapterCandidate, ...]):
    return tuple(
        (
            candidate.title,
            candidate.start_page_index,
            candidate.sources,
        )
        for candidate in candidates
    )
