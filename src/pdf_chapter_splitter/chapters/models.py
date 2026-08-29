"""Chapter domain models.

Chapter uses a 0-based start page index and does not model an end page.
Chapter-to-range conversion belongs to the dedicated boundary resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChapterCandidateSource(StrEnum):
    """Where a chapter candidate came from."""

    OUTLINE = "outline"
    TEXT_LAYOUT = "text_layout"
    OCR = "ocr"
    MANUAL = "manual"
    AI = "ai"


class ChapterEvidenceType(StrEnum):
    """Evidence category supporting a chapter candidate."""

    OUTLINE = "outline"
    OUTLINE_STRUCTURE = "outline_structure"
    OUTLINE_TITLE_QUALITY = "outline_title_quality"
    TEXT_PATTERN = "text_pattern"
    FONT_SIZE = "font_size"
    FONT_NAME = "font_name"
    POSITION = "position"
    PAGE_LAYOUT = "page_layout"
    TOC_PAGE_SUSPECTED = "toc_page_suspected"
    MANUAL = "manual"


class ChapterStructureType(StrEnum):
    """Lightweight structural classification for candidate governance."""

    PRIMARY_CHAPTER = "primary_chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    PART = "part"
    FRONT_MATTER = "front_matter"
    BACK_MATTER = "back_matter"
    UNKNOWN = "unknown"


class ChapterCandidateQualityFlag(StrEnum):
    """Quality flags that help users judge candidates without deleting them."""

    TOC_PAGE_SUSPECTED = "toc_page_suspected"
    NON_PRIMARY_STRUCTURE = "non_primary_structure"
    POOR_TITLE_QUALITY = "poor_title_quality"
    DOI_OR_FILE_TITLE = "doi_or_file_title"
    OCR_NOISE_SUSPECTED = "ocr_noise_suspected"


@dataclass(frozen=True, slots=True)
class ChapterProvenance:
    """A snapshot of where a confirmed chapter came from."""

    candidate_title: str | None
    candidate_start_page_index: int | None
    candidate_sources: tuple[ChapterCandidateSource, ...]
    candidate_confidence: float | None
    candidate_evidences: tuple["ChapterEvidence", ...]
    candidate_original_titles: tuple[str, ...]
    confirmed_from_candidate: bool

    def __post_init__(self) -> None:
        if self.candidate_title is not None:
            _validate_title(self.candidate_title)
        if self.candidate_start_page_index is not None and self.candidate_start_page_index < 0:
            raise ValueError("candidate_start_page_index must be 0 or greater when present")
        if self.candidate_confidence is not None and not 0.0 <= self.candidate_confidence <= 1.0:
            raise ValueError("candidate_confidence must be between 0.0 and 1.0 when present")

        sources = tuple(self.candidate_sources)
        if not sources:
            raise ValueError("candidate_sources must not be empty")
        for source in sources:
            if not isinstance(source, ChapterCandidateSource):
                raise ValueError("candidate_sources must contain ChapterCandidateSource items")
        object.__setattr__(self, "candidate_sources", sources)

        evidences = tuple(self.candidate_evidences)
        for evidence in evidences:
            if not isinstance(evidence, ChapterEvidence):
                raise ValueError("candidate_evidences must contain ChapterEvidence items")
        object.__setattr__(self, "candidate_evidences", evidences)

        original_titles = tuple(self.candidate_original_titles)
        if not original_titles:
            raise ValueError("candidate_original_titles must not be empty")
        for original_title in original_titles:
            _validate_title(original_title)
        object.__setattr__(self, "candidate_original_titles", original_titles)


@dataclass(frozen=True, slots=True)
class Chapter:
    """A user-confirmed chapter start."""

    title: str
    start_page_index: int
    level: int = 1
    provenance: ChapterProvenance | None = None

    @classmethod
    def from_page_number(
        cls,
        title: str,
        start_page_number: int,
        level: int = 1,
        provenance: ChapterProvenance | None = None,
    ) -> "Chapter":
        """Create a chapter from a user-facing 1-based page number."""

        if start_page_number < 1:
            raise ValueError("start_page_number must be 1 or greater")
        return cls(
            title=title,
            start_page_index=start_page_number - 1,
            level=level,
            provenance=provenance,
        )

    def __post_init__(self) -> None:
        _validate_title(self.title)
        if self.start_page_index < 0:
            raise ValueError("start_page_index must be 0 or greater")
        if self.level < 1:
            raise ValueError("level must be 1 or greater")
        if self.provenance is not None and not isinstance(self.provenance, ChapterProvenance):
            raise ValueError("provenance must be a ChapterProvenance when present")

    @property
    def gui_page_number(self) -> int:
        return self.start_page_index + 1

    def validate(self, page_count: int | None = None) -> None:
        """Validate this chapter against an optional PDF page count."""

        if page_count is None:
            return
        if page_count < 1:
            raise ValueError("page_count must be 1 or greater")
        if self.start_page_index >= page_count:
            raise ValueError("start_page_index must be within PDF page range")


@dataclass(frozen=True, slots=True)
class ChapterEvidence:
    """A single piece of evidence behind a chapter candidate."""

    evidence_type: ChapterEvidenceType
    description: str
    page_index: int
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_type, ChapterEvidenceType):
            raise ValueError("evidence_type must be a ChapterEvidenceType")
        _validate_non_blank(self.description, "description")
        if self.page_index < 0:
            raise ValueError("page_index must be 0 or greater")
        _validate_non_blank(self.text, "text")


@dataclass(frozen=True, slots=True)
class ChapterCandidate:
    """A possible chapter start, before user or algorithm confirmation."""

    title: str
    start_page_index: int
    source: ChapterCandidateSource
    confidence: float
    level: int
    evidences: tuple[ChapterEvidence, ...]
    sources: tuple[ChapterCandidateSource, ...] | None = None
    original_titles: tuple[str, ...] | None = None
    structure_type: ChapterStructureType = ChapterStructureType.UNKNOWN
    quality_flags: tuple[ChapterCandidateQualityFlag, ...] = ()

    @classmethod
    def make(
        cls,
        title: str,
        start_page_index: int,
        source: ChapterCandidateSource,
        confidence: float,
        level: int,
        evidence_page_index: int,
        evidence_type: ChapterEvidenceType,
        evidence_description: str = "Chapter candidate evidence",
        evidence_text: str | None = None,
    ) -> "ChapterCandidate":
        """Create a candidate with one evidence entry."""

        evidence = ChapterEvidence(
            evidence_type=evidence_type,
            description=evidence_description,
            page_index=evidence_page_index,
            text=title if evidence_text is None else evidence_text,
        )
        return cls(
            title=title,
            start_page_index=start_page_index,
            source=source,
            confidence=confidence,
            level=level,
            evidences=(evidence,),
        )

    def __post_init__(self) -> None:
        _validate_title(self.title)
        if self.start_page_index < 0:
            raise ValueError("start_page_index must be 0 or greater")
        if not isinstance(self.source, ChapterCandidateSource):
            raise ValueError("source must be a ChapterCandidateSource")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.level < 1:
            raise ValueError("level must be 1 or greater")
        if not isinstance(self.structure_type, ChapterStructureType):
            raise ValueError("structure_type must be a ChapterStructureType")

        evidences = tuple(self.evidences)
        if not evidences:
            raise ValueError("evidences must not be empty")
        for evidence in evidences:
            if not isinstance(evidence, ChapterEvidence):
                raise ValueError("evidences must contain ChapterEvidence items")
        object.__setattr__(self, "evidences", evidences)

        sources = (self.source,) if self.sources is None else tuple(self.sources)
        if not sources:
            raise ValueError("sources must not be empty")
        for source in sources:
            if not isinstance(source, ChapterCandidateSource):
                raise ValueError("sources must contain ChapterCandidateSource items")
        if self.source not in sources:
            raise ValueError("source must be included in sources")
        object.__setattr__(self, "sources", sources)

        original_titles = (self.title,) if self.original_titles is None else tuple(self.original_titles)
        if not original_titles:
            raise ValueError("original_titles must not be empty")
        for original_title in original_titles:
            _validate_title(original_title)
        object.__setattr__(self, "original_titles", original_titles)

        quality_flags = tuple(self.quality_flags)
        for quality_flag in quality_flags:
            if not isinstance(quality_flag, ChapterCandidateQualityFlag):
                raise ValueError("quality_flags must contain ChapterCandidateQualityFlag items")
        object.__setattr__(self, "quality_flags", quality_flags)


@dataclass(frozen=True, slots=True)
class ManualChapterInput:
    """User-facing manual chapter input using 1-based page numbers."""

    title: str
    start_page_number: int
    level: int = 1

    def __post_init__(self) -> None:
        _validate_title(self.title)
        if self.start_page_number < 1:
            raise ValueError("start_page_number must be 1 or greater")
        if self.level < 1:
            raise ValueError("level must be 1 or greater")


def _validate_title(title: str) -> None:
    _validate_non_blank(title, "title")


def _validate_non_blank(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


__all__ = [
    "Chapter",
    "ChapterCandidate",
    "ChapterCandidateQualityFlag",
    "ChapterCandidateSource",
    "ChapterEvidence",
    "ChapterEvidenceType",
    "ChapterProvenance",
    "ChapterStructureType",
    "ManualChapterInput",
]
