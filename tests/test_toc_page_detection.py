from __future__ import annotations

from pathlib import Path

from pdf_chapter_splitter.chapters import (
    ChapterCandidateQualityFlag,
    ChapterEvidenceType,
    TOCPageDetector,
    TOCPageEvidenceType,
    TextLayoutCandidateDetector,
)
from pdf_chapter_splitter.pdf import PyMuPDFReader


def test_toc_page_detector_classifies_contents_page_with_explanatory_evidence(
    toc_pdf_path: Path,
):
    with PyMuPDFReader(toc_pdf_path) as reader:
        classification = TOCPageDetector().classify_reader_page(reader, 0)

    assert classification.page_index == 0
    assert classification.is_toc_page is True
    assert classification.confidence >= 0.7
    evidence_types = {evidence.evidence_type for evidence in classification.evidences}
    assert TOCPageEvidenceType.CONTENTS_HEADING in evidence_types
    assert TOCPageEvidenceType.CHAPTER_ENTRY_DENSITY in evidence_types
    assert TOCPageEvidenceType.DOTTED_LEADER_PATTERN in evidence_types
    assert TOCPageEvidenceType.PAGE_NUMBER_PATTERN in evidence_types


def test_toc_page_detector_does_not_mark_normal_chapter_page(toc_pdf_path: Path):
    with PyMuPDFReader(toc_pdf_path) as reader:
        classification = TOCPageDetector().classify_reader_page(reader, 1)

    assert classification.page_index == 1
    assert classification.is_toc_page is False
    assert classification.evidences == ()


def test_toc_page_detector_classifies_continued_toc_page_without_contents_heading():
    text = """
    CHAPTER 4
    Understanding coffee brew control charts
    046
    CHAPTER 5
    Coffee extraction science
    062
    CHAPTER 6
    Automatic drippers
    078
    CHAPTER 7
    Hand brewing variables
    094
    """

    classification = TOCPageDetector().classify_text(text, page_index=4)

    assert classification.is_toc_page is True
    evidence_types = {evidence.evidence_type for evidence in classification.evidences}
    assert TOCPageEvidenceType.CHAPTER_ENTRY_DENSITY in evidence_types
    assert TOCPageEvidenceType.PAGE_NUMBER_PATTERN in evidence_types
    assert TOCPageEvidenceType.TITLE_CANDIDATE_DENSITY in evidence_types


def test_toc_page_detector_classifies_sparse_continued_toc_page_with_dense_page_numbers():
    text = """
    CHAPTER 4
    Understanding coffee brew control charts
    046
    Original brew control chart
    048
    Extraction analysis
    051
    CHAPTER 5
    Coffee extraction science
    062
    Ideal coffee bed shape
    065
    Fresh coffee grounds
    066
    """

    classification = TOCPageDetector().classify_text(text, page_index=5)

    assert classification.is_toc_page is True
    evidence_types = {evidence.evidence_type for evidence in classification.evidences}
    assert TOCPageEvidenceType.CHAPTER_ENTRY_DENSITY in evidence_types
    assert TOCPageEvidenceType.PAGE_NUMBER_PATTERN in evidence_types


def test_text_layout_candidates_from_toc_page_are_flagged_but_not_removed(
    toc_pdf_path: Path,
):
    with PyMuPDFReader(toc_pdf_path) as reader:
        candidates = TextLayoutCandidateDetector().detect(reader)

    toc_candidates = [candidate for candidate in candidates if candidate.start_page_index == 0]
    assert toc_candidates
    assert all(
        ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED in candidate.quality_flags
        for candidate in toc_candidates
    )
    assert all(candidate.confidence < 0.7 for candidate in toc_candidates)
    assert all(
        any(
            evidence.evidence_type is ChapterEvidenceType.TOC_PAGE_SUSPECTED
            for evidence in candidate.evidences
        )
        for candidate in toc_candidates
    )
    assert any(candidate.start_page_index == 1 for candidate in candidates)
