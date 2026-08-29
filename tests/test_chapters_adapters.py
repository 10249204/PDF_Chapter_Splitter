from __future__ import annotations

from pathlib import Path

import pytest

from pdf_chapter_splitter.chapters import (
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterEvidenceType,
    ManualCandidateDetector,
    ManualChapterInput,
    OutlineCandidateDetector,
    sort_chapter_candidates,
    validate_chapter_candidates,
)


def test_outline_to_candidates_preserves_title_level_and_page_index(text_pdf_path: Path):
    from pdf_chapter_splitter.pdf import PyMuPDFReader

    with PyMuPDFReader(text_pdf_path) as reader:
        candidates = OutlineCandidateDetector().detect(reader.get_outline())

    assert len(candidates) == 2
    assert candidates[0].title == "Chapter 1"
    assert candidates[0].start_page_index == 0
    assert candidates[0].level == 1
    assert candidates[0].source is ChapterCandidateSource.OUTLINE
    assert candidates[0].confidence == pytest.approx(0.95)
    assert candidates[0].evidences[0].evidence_type is ChapterEvidenceType.OUTLINE
    assert candidates[0].evidences[0].page_index == 0


def test_manual_to_candidates_converts_one_based_page_numbers():
    candidates = ManualCandidateDetector().detect(
        [
            ManualChapterInput(title="第一章", start_page_number=20, level=1),
            ManualChapterInput(title="第二章", start_page_number=45, level=2),
        ]
    )

    assert candidates[0].start_page_index == 19
    assert candidates[0].source is ChapterCandidateSource.MANUAL
    assert candidates[0].confidence == pytest.approx(1.0)
    assert candidates[0].level == 1
    assert candidates[0].evidences[0].evidence_type is ChapterEvidenceType.MANUAL
    assert candidates[1].start_page_index == 44
    assert candidates[1].level == 2


def test_sort_chapter_candidates_orders_by_start_page_index():
    candidates = (
        ChapterCandidate.make(
            title="第三章",
            start_page_index=80,
            source=ChapterCandidateSource.MANUAL,
            confidence=1.0,
            level=1,
            evidence_page_index=80,
            evidence_type=ChapterEvidenceType.MANUAL,
        ),
        ChapterCandidate.make(
            title="第一章",
            start_page_index=20,
            source=ChapterCandidateSource.MANUAL,
            confidence=1.0,
            level=1,
            evidence_page_index=20,
            evidence_type=ChapterEvidenceType.MANUAL,
        ),
        ChapterCandidate.make(
            title="第二章",
            start_page_index=50,
            source=ChapterCandidateSource.MANUAL,
            confidence=1.0,
            level=1,
            evidence_page_index=50,
            evidence_type=ChapterEvidenceType.MANUAL,
        ),
    )

    sorted_candidates = sort_chapter_candidates(candidates)

    assert [candidate.start_page_index for candidate in sorted_candidates] == [20, 50, 80]


def test_validate_chapter_candidates_rejects_duplicate_start_page_index():
    candidates = (
        ChapterCandidate.make(
            title="第一章",
            start_page_index=20,
            source=ChapterCandidateSource.MANUAL,
            confidence=1.0,
            level=1,
            evidence_page_index=20,
            evidence_type=ChapterEvidenceType.MANUAL,
        ),
        ChapterCandidate.make(
            title="第一章 again",
            start_page_index=20,
            source=ChapterCandidateSource.OUTLINE,
            confidence=0.9,
            level=1,
            evidence_page_index=20,
            evidence_type=ChapterEvidenceType.OUTLINE,
        ),
    )

    with pytest.raises(ValueError):
        validate_chapter_candidates(candidates, page_count=100)


def test_validate_chapter_candidates_rejects_out_of_range_page_index():
    candidates = (
        ChapterCandidate.make(
            title="第一章",
            start_page_index=100,
            source=ChapterCandidateSource.MANUAL,
            confidence=1.0,
            level=1,
            evidence_page_index=100,
            evidence_type=ChapterEvidenceType.MANUAL,
        ),
    )

    with pytest.raises(ValueError):
        validate_chapter_candidates(candidates, page_count=100)

