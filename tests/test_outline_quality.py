from __future__ import annotations

from pdf_chapter_splitter.chapters import (
    ChapterCandidateQualityFlag,
    ChapterEvidenceType,
    ChapterStructureType,
    OutlineCandidateDetector,
    OutlineQualityClassifier,
)
from pdf_chapter_splitter.pdf import OutlineItem


def test_outline_quality_classifier_marks_primary_chapters():
    classifier = OutlineQualityClassifier()

    assert classifier.classify("Chapter 1 Introduction").structure_type is (
        ChapterStructureType.PRIMARY_CHAPTER
    )
    assert classifier.classify("第 十二 章 咖啡").structure_type is (
        ChapterStructureType.PRIMARY_CHAPTER
    )
    assert classifier.classify("1 Introduction").structure_type is (
        ChapterStructureType.PRIMARY_CHAPTER
    )


def test_outline_quality_classifier_marks_non_primary_structures():
    classifier = OutlineQualityClassifier()

    assert classifier.classify("1.1 Motivation").structure_type is ChapterStructureType.SECTION
    assert classifier.classify("1.1.1 Detail").structure_type is ChapterStructureType.SUBSECTION
    assert classifier.classify("第一节 背景").structure_type is ChapterStructureType.SECTION
    assert classifier.classify("Preface").structure_type is ChapterStructureType.FRONT_MATTER
    assert classifier.classify("References").structure_type is ChapterStructureType.BACK_MATTER
    assert classifier.classify("Appendix A").structure_type is ChapterStructureType.BACK_MATTER
    assert classifier.classify("Part I Foundations").structure_type is ChapterStructureType.PART


def test_outline_quality_classifier_flags_doi_or_file_like_titles_as_poor_quality():
    quality = OutlineQualityClassifier().classify("10.1525_9780520386976-001")

    assert quality.structure_type is ChapterStructureType.UNKNOWN
    assert ChapterCandidateQualityFlag.POOR_TITLE_QUALITY in quality.quality_flags
    assert ChapterCandidateQualityFlag.DOI_OR_FILE_TITLE in quality.quality_flags


def test_outline_candidate_detector_preserves_all_items_with_quality_metadata():
    outline_items = [
        OutlineItem("Chapter 1 Introduction", 1, 0),
        OutlineItem("1.1 Motivation", 2, 3),
        OutlineItem("References", 1, 20),
        OutlineItem("10.1525_9780520386976-001", 1, 30),
    ]

    candidates = OutlineCandidateDetector().detect(outline_items)

    assert [candidate.title for candidate in candidates] == [
        "Chapter 1 Introduction",
        "1.1 Motivation",
        "References",
        "10.1525_9780520386976-001",
    ]
    assert [candidate.structure_type for candidate in candidates] == [
        ChapterStructureType.PRIMARY_CHAPTER,
        ChapterStructureType.SECTION,
        ChapterStructureType.BACK_MATTER,
        ChapterStructureType.UNKNOWN,
    ]
    assert candidates[0].confidence == 0.95
    assert candidates[1].confidence < candidates[0].confidence
    assert candidates[2].confidence < candidates[0].confidence
    assert ChapterCandidateQualityFlag.POOR_TITLE_QUALITY in candidates[3].quality_flags
    assert all(
        any(evidence.evidence_type is ChapterEvidenceType.OUTLINE_STRUCTURE for evidence in candidate.evidences)
        for candidate in candidates
    )
