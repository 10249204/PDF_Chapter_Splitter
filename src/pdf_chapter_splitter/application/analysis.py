"""Application-level analysis summary and candidate presentation policy."""

from __future__ import annotations

from dataclasses import dataclass

from pdf_chapter_splitter.chapters import (
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterStructureType,
)
from pdf_chapter_splitter.pdf import PDFTextQualityReport


_NON_PRIMARY_STRUCTURES = {
    ChapterStructureType.SECTION,
    ChapterStructureType.SUBSECTION,
    ChapterStructureType.PART,
    ChapterStructureType.FRONT_MATTER,
    ChapterStructureType.BACK_MATTER,
}

_SEVERE_QUALITY_FLAGS = {
    ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,
    ChapterCandidateQualityFlag.NON_PRIMARY_STRUCTURE,
    ChapterCandidateQualityFlag.POOR_TITLE_QUALITY,
    ChapterCandidateQualityFlag.DOI_OR_FILE_TITLE,
    ChapterCandidateQualityFlag.OCR_NOISE_SUSPECTED,
}

_DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.60


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
    """User-facing summary of an analysis result."""

    text_quality_report: PDFTextQualityReport | None
    candidate_count: int
    primary_chapter_candidate_count: int
    toc_suspected_candidate_count: int
    low_quality_candidate_count: int
    poor_title_candidate_count: int
    manual_candidate_count: int
    outline_candidate_count: int
    text_layout_candidate_count: int
    fused_candidate_count: int

    @classmethod
    def from_candidates(
        cls,
        candidates: tuple[ChapterCandidate, ...],
        *,
        text_quality_report: PDFTextQualityReport | None,
    ) -> "AnalysisSummary":
        """Build a display-friendly summary from fused candidates."""

        normalized_candidates = tuple(candidates)
        return cls(
            text_quality_report=text_quality_report,
            candidate_count=len(normalized_candidates),
            primary_chapter_candidate_count=sum(
                1
                for candidate in normalized_candidates
                if candidate.structure_type is ChapterStructureType.PRIMARY_CHAPTER
            ),
            toc_suspected_candidate_count=sum(
                1
                for candidate in normalized_candidates
                if ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED in candidate.quality_flags
            ),
            low_quality_candidate_count=sum(
                1 for candidate in normalized_candidates if _is_low_quality_candidate(candidate)
            ),
            poor_title_candidate_count=sum(
                1
                for candidate in normalized_candidates
                if ChapterCandidateQualityFlag.POOR_TITLE_QUALITY in candidate.quality_flags
            ),
            manual_candidate_count=_source_count(
                normalized_candidates,
                ChapterCandidateSource.MANUAL,
            ),
            outline_candidate_count=_source_count(
                normalized_candidates,
                ChapterCandidateSource.OUTLINE,
            ),
            text_layout_candidate_count=_source_count(
                normalized_candidates,
                ChapterCandidateSource.TEXT_LAYOUT,
            ),
            fused_candidate_count=len(normalized_candidates),
        )


@dataclass(frozen=True, slots=True)
class CandidatePresentation:
    """How one candidate should be shown without changing the candidate."""

    candidate: ChapterCandidate
    visible: bool
    collapsed: bool
    hidden_by_default: bool
    display_reason: str


@dataclass(frozen=True, slots=True)
class CandidatePresentationPolicy:
    """Default presentation strategy for chapter candidates."""

    high_confidence_threshold: float = 0.85
    low_confidence_threshold: float = _DEFAULT_LOW_CONFIDENCE_THRESHOLD

    def __post_init__(self) -> None:
        if not 0.0 <= self.high_confidence_threshold <= 1.0:
            raise ValueError("high_confidence_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.low_confidence_threshold <= 1.0:
            raise ValueError("low_confidence_threshold must be between 0.0 and 1.0")

    def present(
        self,
        candidates: tuple[ChapterCandidate, ...],
        *,
        show_all: bool = False,
    ) -> tuple[CandidatePresentation, ...]:
        """Return presentation records while preserving every original candidate."""

        return tuple(self._present_one(candidate, show_all=show_all) for candidate in candidates)

    def _present_one(
        self,
        candidate: ChapterCandidate,
        *,
        show_all: bool,
    ) -> CandidatePresentation:
        reasons = _presentation_reasons(candidate, self.low_confidence_threshold)
        primary = candidate.structure_type is ChapterStructureType.PRIMARY_CHAPTER
        manual = ChapterCandidateSource.MANUAL in candidate.sources
        high_confidence_without_severe_flags = (
            candidate.confidence >= self.high_confidence_threshold
            and not _has_severe_quality_flags(candidate)
            and not _has_non_primary_structure(candidate)
        )
        hidden_by_default = not (primary or manual or high_confidence_without_severe_flags)
        visible = show_all or not hidden_by_default

        return CandidatePresentation(
            candidate=candidate,
            visible=visible,
            collapsed=hidden_by_default,
            hidden_by_default=hidden_by_default,
            display_reason="; ".join(reasons),
        )


def _source_count(
    candidates: tuple[ChapterCandidate, ...],
    source: ChapterCandidateSource,
) -> int:
    return sum(1 for candidate in candidates if source in candidate.sources)


def _is_low_quality_candidate(candidate: ChapterCandidate) -> bool:
    return (
        _has_severe_quality_flags(candidate)
        or _has_non_primary_structure(candidate)
        or candidate.confidence < _DEFAULT_LOW_CONFIDENCE_THRESHOLD
    )


def _has_severe_quality_flags(candidate: ChapterCandidate) -> bool:
    return bool(set(candidate.quality_flags) & _SEVERE_QUALITY_FLAGS)


def _has_non_primary_structure(candidate: ChapterCandidate) -> bool:
    return candidate.structure_type in _NON_PRIMARY_STRUCTURES


def _presentation_reasons(
    candidate: ChapterCandidate,
    low_confidence_threshold: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if candidate.structure_type is ChapterStructureType.PRIMARY_CHAPTER:
        reasons.append("primary chapter")
    if ChapterCandidateSource.MANUAL in candidate.sources:
        reasons.append("manual candidate")
    if ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED in candidate.quality_flags:
        reasons.append("suspected table of contents page")
    if _has_non_primary_structure(candidate):
        reasons.append(f"non-primary structure: {candidate.structure_type.value}")
    if ChapterCandidateQualityFlag.POOR_TITLE_QUALITY in candidate.quality_flags:
        reasons.append("poor title quality")
    if ChapterCandidateQualityFlag.OCR_NOISE_SUSPECTED in candidate.quality_flags:
        reasons.append("OCR noise suspected")
    if candidate.confidence < low_confidence_threshold:
        reasons.append("low confidence")
    if not reasons:
        reasons.append("high confidence candidate")
    return tuple(reasons)


__all__ = [
    "AnalysisSummary",
    "CandidatePresentation",
    "CandidatePresentationPolicy",
]
