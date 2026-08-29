from __future__ import annotations

import pytest

from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterConfirmationResult,
    ChapterConfirmationService,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterValidator,
    ConfirmationAction,
)


def test_confirmation_accepts_candidate_as_chapter_with_provenance():
    candidate = _candidate(
        "Chapter 3 File System",
        20,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.9,
    )

    chapter = ChapterConfirmationService().accept(candidate)

    assert chapter.title == "Chapter 3 File System"
    assert chapter.start_page_index == 20
    assert chapter.level == 1
    assert chapter.provenance is not None
    assert chapter.provenance.candidate_title == "Chapter 3 File System"
    assert chapter.provenance.candidate_sources == (ChapterCandidateSource.TEXT_LAYOUT,)


def test_confirmation_accepts_candidate_with_edited_title_and_keeps_original_title():
    candidate = _candidate(
        "Chapter 3: File System",
        20,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.9,
    )

    chapter = ChapterConfirmationService().accept(candidate, title="第三章 文件系统")

    assert chapter.title == "第三章 文件系统"
    assert chapter.provenance is not None
    assert chapter.provenance.candidate_title == "Chapter 3: File System"
    assert chapter.provenance.candidate_original_titles == ("Chapter 3: File System",)


def test_confirmation_accepts_candidate_with_edited_one_based_start_page():
    candidate = _candidate("Chapter 3", 127, ChapterCandidateSource.OUTLINE, 0.95)

    chapter = ChapterConfirmationService().accept(candidate, start_page_number=129)

    assert chapter.start_page_index == 128
    assert chapter.gui_page_number == 129


def test_confirmation_rejects_candidate_without_creating_chapter():
    candidate = _candidate("Chapter 3", 20, ChapterCandidateSource.OUTLINE, 0.95)

    result = ChapterConfirmationService().reject(candidate)

    assert result.chapter is None
    assert result.rejected_candidate == candidate
    assert result.action is ConfirmationAction.REJECT


def test_confirmation_creates_manual_chapter_without_candidate():
    chapter = ChapterConfirmationService().create_manual(
        title="附录 A",
        start_page_number=230,
        level=2,
    )

    assert chapter.title == "附录 A"
    assert chapter.start_page_index == 229
    assert chapter.level == 2
    assert chapter.provenance is not None
    assert chapter.provenance.confirmed_from_candidate is False
    assert chapter.provenance.candidate_sources == (ChapterCandidateSource.MANUAL,)


@pytest.mark.parametrize("title", ["", "   "])
def test_confirmation_rejects_invalid_title(title: str):
    candidate = _candidate("Chapter 3", 20, ChapterCandidateSource.OUTLINE, 0.95)

    with pytest.raises(ValueError):
        ChapterConfirmationService().accept(candidate, title=title)


@pytest.mark.parametrize("start_page_index", [-1])
def test_chapter_rejects_invalid_start_page_index(start_page_index: int):
    with pytest.raises(ValueError):
        Chapter(title="Chapter 3", start_page_index=start_page_index)


def test_confirmation_rejects_page_count_out_of_range():
    candidate = _candidate("Chapter 3", 99, ChapterCandidateSource.OUTLINE, 0.95)

    with pytest.raises(ValueError):
        ChapterConfirmationService().accept(candidate, page_count=99)


def test_confirmation_preserves_multiple_candidate_sources():
    candidate = _candidate(
        "Chapter 3",
        20,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.98,
        sources=(ChapterCandidateSource.TEXT_LAYOUT, ChapterCandidateSource.OUTLINE),
    )

    chapter = ChapterConfirmationService().accept(candidate)

    assert chapter.provenance is not None
    assert chapter.provenance.candidate_sources == (
        ChapterCandidateSource.TEXT_LAYOUT,
        ChapterCandidateSource.OUTLINE,
    )


def test_confirmation_preserves_candidate_evidence():
    outline_evidence = _evidence(ChapterEvidenceType.OUTLINE, 20, "Chapter 3")
    font_evidence = _evidence(ChapterEvidenceType.FONT_SIZE, 20, "Chapter 3")
    candidate = _candidate(
        "Chapter 3",
        20,
        ChapterCandidateSource.TEXT_LAYOUT,
        0.98,
        evidences=(outline_evidence, font_evidence),
    )

    chapter = ChapterConfirmationService().accept(candidate)

    assert chapter.provenance is not None
    assert chapter.provenance.candidate_evidences == (outline_evidence, font_evidence)


def test_confirmation_does_not_modify_input_candidate():
    candidate = _candidate("Chapter 3", 20, ChapterCandidateSource.OUTLINE, 0.95)
    original_candidate = candidate

    ChapterConfirmationService().accept(candidate, title="第三章", start_page_number=22)

    assert candidate == original_candidate
    assert candidate.title == "Chapter 3"
    assert candidate.start_page_index == 20


def test_confirmation_batch_accepts_rejects_and_sorts_chapters():
    service = ChapterConfirmationService()
    first = _candidate("Chapter 1", 50, ChapterCandidateSource.OUTLINE, 0.95)
    second = _candidate("Chapter 2", 20, ChapterCandidateSource.TEXT_LAYOUT, 0.9)
    rejected = _candidate("Table 1", 5, ChapterCandidateSource.TEXT_LAYOUT, 0.6)

    result = service.apply_decisions(
        (
            ChapterConfirmationDecision.accept(first),
            ChapterConfirmationDecision.accept(second),
            ChapterConfirmationDecision.reject(rejected),
        )
    )

    assert isinstance(result, ChapterConfirmationResult)
    assert [chapter.start_page_index for chapter in result.accepted_chapters] == [20, 50]
    assert result.rejected_candidates == (rejected,)


def test_confirmation_batch_accepts_edited_candidate():
    candidate = _candidate("Chapter 3", 128, ChapterCandidateSource.OUTLINE, 0.95)

    result = ChapterConfirmationService().apply_decisions(
        (
            ChapterConfirmationDecision.accept(
                candidate,
                title="第三章 文件系统",
                start_page_number=129,
            ),
        )
    )

    assert result.accepted_chapters[0].title == "第三章 文件系统"
    assert result.accepted_chapters[0].start_page_index == 128


def test_chapter_validator_sorts_by_start_page_index_and_rejects_duplicates():
    chapters = (
        Chapter(title="Chapter 2", start_page_index=20),
        Chapter(title="Chapter 1", start_page_index=10),
    )

    sorted_chapters = ChapterValidator().validate(chapters, page_count=100)

    assert [chapter.start_page_index for chapter in sorted_chapters] == [10, 20]

    with pytest.raises(ValueError):
        ChapterValidator().validate(
            (
                Chapter(title="Part I", start_page_index=10),
                Chapter(title="Chapter 1", start_page_index=10),
            ),
            page_count=100,
        )


def test_chapter_model_does_not_have_end_page_semantics():
    chapter = Chapter(title="Chapter 3", start_page_index=20)

    assert not hasattr(chapter, "end_page_index")
    assert not hasattr(chapter, "gui_end_page_number")
    assert not hasattr(chapter, "page_count")


def _candidate(
    title: str,
    start_page_index: int,
    source: ChapterCandidateSource,
    confidence: float,
    *,
    sources: tuple[ChapterCandidateSource, ...] | None = None,
    evidences: tuple[ChapterEvidence, ...] | None = None,
) -> ChapterCandidate:
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=source,
        confidence=confidence,
        level=1,
        evidences=evidences or (_evidence(_default_evidence_type(source), start_page_index, title),),
        sources=sources,
    )


def _evidence(
    evidence_type: ChapterEvidenceType,
    page_index: int,
    text: str,
) -> ChapterEvidence:
    return ChapterEvidence(
        evidence_type=evidence_type,
        description=f"{evidence_type.value} evidence",
        page_index=page_index,
        text=text,
    )


def _default_evidence_type(source: ChapterCandidateSource) -> ChapterEvidenceType:
    if source is ChapterCandidateSource.MANUAL:
        return ChapterEvidenceType.MANUAL
    if source is ChapterCandidateSource.OUTLINE:
        return ChapterEvidenceType.OUTLINE
    return ChapterEvidenceType.TEXT_PATTERN
