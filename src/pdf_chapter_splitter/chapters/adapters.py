"""Adapters that turn explicit chapter inputs into candidates."""

from __future__ import annotations

from collections.abc import Iterable

from pdf_chapter_splitter.chapters.models import (
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
    ManualChapterInput,
)
from pdf_chapter_splitter.chapters.outline_quality import OutlineQualityClassifier
from pdf_chapter_splitter.pdf.models import OutlineItem


class OutlineCandidateDetector:
    """Convert PDF outline entries into chapter candidates."""

    def __init__(self, quality_classifier: OutlineQualityClassifier | None = None) -> None:
        self.quality_classifier = quality_classifier or OutlineQualityClassifier()

    def detect(self, outline_items: Iterable[OutlineItem]) -> tuple[ChapterCandidate, ...]:
        candidates: list[ChapterCandidate] = []
        for item in outline_items:
            if item.page_index is None:
                continue
            quality = self.quality_classifier.classify(item.title, page_index=item.page_index)
            outline_evidence = ChapterEvidence(
                evidence_type=ChapterEvidenceType.OUTLINE,
                description="PDF outline item points to this page",
                page_index=item.page_index,
                text=item.title,
            )
            candidates.append(
                ChapterCandidate(
                    title=item.title,
                    start_page_index=item.page_index,
                    source=ChapterCandidateSource.OUTLINE,
                    confidence=quality.confidence,
                    level=_semantic_level_for(quality.structure_type),
                    evidences=(outline_evidence, *quality.evidences),
                    structure_type=quality.structure_type,
                    quality_flags=quality.quality_flags,
                )
            )
        return tuple(candidates)


class ManualCandidateDetector:
    """Convert manual 1-based chapter inputs into 0-based candidates."""

    def detect(self, inputs: Iterable[ManualChapterInput]) -> tuple[ChapterCandidate, ...]:
        return tuple(
            ChapterCandidate.make(
                title=item.title,
                start_page_index=item.start_page_number - 1,
                source=ChapterCandidateSource.MANUAL,
                confidence=1.0,
                level=item.level,
                evidence_page_index=item.start_page_number - 1,
                evidence_type=ChapterEvidenceType.MANUAL,
                evidence_description="User supplied this chapter start page",
                evidence_text=item.title,
            )
            for item in inputs
        )


def sort_chapter_candidates(
    candidates: Iterable[ChapterCandidate],
) -> tuple[ChapterCandidate, ...]:
    """Return candidates ordered by 0-based start page index."""

    return tuple(sorted(candidates, key=lambda candidate: candidate.start_page_index))


def validate_chapter_candidates(
    candidates: Iterable[ChapterCandidate],
    page_count: int,
) -> None:
    """Validate candidate page indexes against a PDF page count."""

    if page_count < 1:
        raise ValueError("page_count must be 1 or greater")

    seen_page_indexes: set[int] = set()
    for candidate in candidates:
        if candidate.start_page_index >= page_count:
            raise ValueError("candidate start_page_index must be within PDF page range")
        if candidate.start_page_index in seen_page_indexes:
            raise ValueError("candidate start_page_index values must be unique")
        seen_page_indexes.add(candidate.start_page_index)


def _semantic_level_for(structure_type: ChapterStructureType) -> int:
    if structure_type is ChapterStructureType.SUBSECTION:
        return 3
    if structure_type is ChapterStructureType.SECTION:
        return 2
    return 1


__all__ = [
    "ManualCandidateDetector",
    "OutlineCandidateDetector",
    "sort_chapter_candidates",
    "validate_chapter_candidates",
]
