from __future__ import annotations

import pytest

from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterProvenance,
    ManualChapterInput,
)


def test_chapter_represents_confirmed_zero_based_start_page_only():
    chapter = Chapter(
        title="第三章 文件系统",
        start_page_index=10,
        level=2,
    )

    assert chapter.gui_page_number == 11
    assert chapter.level == 2
    assert not hasattr(chapter, "end_page_index")
    assert not hasattr(chapter, "gui_end_page_number")
    assert not hasattr(chapter, "page_count")


@pytest.mark.parametrize(
    ("title", "start_page_index", "level"),
    [
        ("", 0, 1),
        ("  ", 0, 1),
        ("Chapter", -1, 1),
        ("Chapter", 0, 0),
    ],
)
def test_chapter_rejects_invalid_values(title, start_page_index, level):
    with pytest.raises(ValueError):
        Chapter(
            title=title,
            start_page_index=start_page_index,
            level=level,
        )


def test_chapter_validates_optional_page_count_without_pdf_reader_dependency():
    chapter = Chapter(title="Chapter 1", start_page_index=99)

    chapter.validate(page_count=100)

    with pytest.raises(ValueError):
        chapter.validate(page_count=99)


def test_chapter_keeps_candidate_provenance_snapshot():
    evidence = ChapterEvidence(
        evidence_type=ChapterEvidenceType.OUTLINE,
        description="bookmark",
        page_index=10,
        text="Chapter 3",
    )
    provenance = ChapterProvenance(
        candidate_title="Chapter 3",
        candidate_start_page_index=10,
        candidate_sources=(ChapterCandidateSource.OUTLINE,),
        candidate_confidence=0.95,
        candidate_evidences=(evidence,),
        candidate_original_titles=("Chapter 3",),
        confirmed_from_candidate=True,
    )

    chapter = Chapter(title="第三章", start_page_index=10, provenance=provenance)

    assert chapter.provenance == provenance
    assert chapter.provenance.candidate_evidences == (evidence,)


def test_chapter_candidate_keeps_raw_title_source_confidence_and_multiple_evidence():
    evidences = (
        ChapterEvidence(
            evidence_type=ChapterEvidenceType.OUTLINE,
            description="PDF bookmark points to this page",
            page_index=10,
            text="第三章 文件系统",
        ),
        ChapterEvidence(
            evidence_type=ChapterEvidenceType.FONT_SIZE,
            description="Title uses larger font than body text",
            page_index=10,
            text="第三章 文件系统",
        ),
    )

    candidate = ChapterCandidate(
        title="第三章 文件系统",
        start_page_index=10,
        source=ChapterCandidateSource.OUTLINE,
        confidence=0.95,
        level=2,
        evidences=evidences,
    )

    assert candidate.title == "第三章 文件系统"
    assert candidate.start_page_index == 10
    assert candidate.source is ChapterCandidateSource.OUTLINE
    assert candidate.confidence == pytest.approx(0.95)
    assert candidate.level == 2
    assert candidate.evidences == evidences


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_chapter_candidate_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        ChapterCandidate(
            title="第三章 文件系统",
            start_page_index=10,
            source=ChapterCandidateSource.OUTLINE,
            confidence=confidence,
            level=1,
            evidences=(
                ChapterEvidence(
                    evidence_type=ChapterEvidenceType.OUTLINE,
                    description="bookmark",
                    page_index=10,
                    text="第三章 文件系统",
                ),
            ),
        )


@pytest.mark.parametrize(
    ("title", "start_page_index", "level"),
    [
        ("", 10, 1),
        ("  ", 10, 1),
        ("Chapter", -1, 1),
        ("Chapter", 10, 0),
    ],
)
def test_chapter_candidate_rejects_invalid_values(title, start_page_index, level):
    with pytest.raises(ValueError):
        ChapterCandidate(
            title=title,
            start_page_index=start_page_index,
            source=ChapterCandidateSource.OUTLINE,
            confidence=0.9,
            level=level,
            evidences=(
                ChapterEvidence(
                    evidence_type=ChapterEvidenceType.OUTLINE,
                    description="bookmark",
                    page_index=10,
                    text="第三章 文件系统",
                ),
            ),
        )


def test_manual_chapter_input_keeps_user_facing_one_based_page_number():
    manual = ManualChapterInput(title="第一章", start_page_number=20, level=1)

    assert manual.title == "第一章"
    assert manual.start_page_number == 20
    assert manual.level == 1


@pytest.mark.parametrize(
    ("title", "start_page_number", "level"),
    [
        ("", 20, 1),
        ("  ", 20, 1),
        ("第一章", 0, 1),
        ("第一章", 20, 0),
    ],
)
def test_manual_chapter_input_rejects_invalid_values(title, start_page_number, level):
    with pytest.raises(ValueError):
        ManualChapterInput(title=title, start_page_number=start_page_number, level=level)
