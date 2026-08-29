"""Deterministic table-of-contents page detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from pdf_chapter_splitter.pdf.reader import PDFReader


class TOCPageEvidenceType(StrEnum):
    """Evidence categories for page-level TOC classification."""

    CONTENTS_HEADING = "detected_contents_heading"
    CHAPTER_ENTRY_DENSITY = "chapter_entry_density"
    DOTTED_LEADER_PATTERN = "dotted_leader_pattern"
    PAGE_NUMBER_PATTERN = "page_number_pattern"
    TITLE_CANDIDATE_DENSITY = "title_candidate_density"


@dataclass(frozen=True, slots=True)
class TOCPageEvidence:
    """One explainable reason a page looks like a table of contents."""

    evidence_type: TOCPageEvidenceType
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_type, TOCPageEvidenceType):
            raise ValueError("evidence_type must be a TOCPageEvidenceType")
        if not self.description.strip():
            raise ValueError("description must not be blank")


@dataclass(frozen=True, slots=True)
class TOCPageClassification:
    """Page-level TOC classification with evidence."""

    page_index: int
    is_toc_page: bool
    confidence: float
    evidences: tuple[TOCPageEvidence, ...]

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index must be 0 or greater")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        evidences = tuple(self.evidences)
        for evidence in evidences:
            if not isinstance(evidence, TOCPageEvidence):
                raise ValueError("evidences must contain TOCPageEvidence items")
        object.__setattr__(self, "evidences", evidences)


@dataclass(frozen=True, slots=True)
class TOCPageDetectorConfig:
    """Thresholds for lightweight TOC page detection."""

    min_chapter_entries: int = 3
    min_continued_chapter_entries: int = 2
    min_dotted_leaders: int = 2
    min_page_number_entries: int = 3
    min_title_candidate_density: float = 0.25


class TOCPageDetector:
    """Classify whether extracted page text resembles a table of contents."""

    def __init__(self, config: TOCPageDetectorConfig | None = None) -> None:
        self.config = config or TOCPageDetectorConfig()

    def classify_reader_page(self, reader: PDFReader, page_index: int) -> TOCPageClassification:
        if page_index < 0 or page_index >= reader.page_count:
            raise ValueError(f"page index {page_index} is outside valid range 0..{reader.page_count - 1}")
        return self.classify_text(reader.get_page_text(page_index), page_index=page_index)

    def classify_text(self, text: str, *, page_index: int) -> TOCPageClassification:
        lines = _nonblank_lines(text)
        if not lines:
            return TOCPageClassification(page_index, False, 0.0, ())

        evidence: list[TOCPageEvidence] = []
        contents_heading = _has_contents_heading(lines)
        chapter_entry_count = sum(1 for line in lines if _looks_like_chapter_entry(line))
        dotted_leader_count = sum(1 for line in lines if _DOTTED_LEADER_RE.search(line))
        page_number_entry_count = sum(1 for line in lines if _PAGE_NUMBER_ENTRY_RE.search(line))
        title_candidate_density = chapter_entry_count / len(lines)

        if contents_heading:
            evidence.append(
                TOCPageEvidence(
                    TOCPageEvidenceType.CONTENTS_HEADING,
                    "detected Contents/Table of Contents/目录 heading",
                )
            )
        continued_toc_structure = (
            chapter_entry_count >= self.config.min_continued_chapter_entries
            and page_number_entry_count >= self.config.min_page_number_entries
        )

        if chapter_entry_count >= self.config.min_chapter_entries or continued_toc_structure:
            evidence.append(
                TOCPageEvidence(
                    TOCPageEvidenceType.CHAPTER_ENTRY_DENSITY,
                    f"chapter_entry_count={chapter_entry_count}",
                )
            )
        if dotted_leader_count >= self.config.min_dotted_leaders:
            evidence.append(
                TOCPageEvidence(
                    TOCPageEvidenceType.DOTTED_LEADER_PATTERN,
                    f"dotted_leader_count={dotted_leader_count}",
                )
            )
        if page_number_entry_count >= self.config.min_page_number_entries:
            evidence.append(
                TOCPageEvidence(
                    TOCPageEvidenceType.PAGE_NUMBER_PATTERN,
                    f"page_number_entry_count={page_number_entry_count}",
                )
            )
        if title_candidate_density >= self.config.min_title_candidate_density:
            evidence.append(
                TOCPageEvidence(
                    TOCPageEvidenceType.TITLE_CANDIDATE_DENSITY,
                    f"title_candidate_density={title_candidate_density:.2f}",
                )
            )

        score = min(1.0, round(len(evidence) * 0.25, 2))
        is_toc_page = (
            contents_heading and len(evidence) >= 2
            or len(evidence) >= 3
            or continued_toc_structure
        )
        return TOCPageClassification(
            page_index=page_index,
            is_toc_page=is_toc_page,
            confidence=score if is_toc_page else 0.0,
            evidences=tuple(evidence) if is_toc_page else (),
        )


_DOTTED_LEADER_RE = re.compile(r"\.{3,}\s*\d{1,4}\s*$")
_PAGE_NUMBER_ENTRY_RE = re.compile(r"(?:^|\s|\.{2,})\d{1,4}\s*$")
_CHAPTER_ENTRY_RE = re.compile(
    r"^(?:chapter\s+\d+|第\s*[0-9一二三四五六七八九十百千万零〇两]+\s*章|\d{1,3}\s+[^\W\d_]).*",
    re.IGNORECASE,
)
_CONTENTS_RE = re.compile(r"^(?:contents|table\s+of\s+contents|目录)$", re.IGNORECASE)


def _nonblank_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if " ".join(line.split())]


def _has_contents_heading(lines: list[str]) -> bool:
    return any(_CONTENTS_RE.match(line) for line in lines[:8])


def _looks_like_chapter_entry(line: str) -> bool:
    return bool(_CHAPTER_ENTRY_RE.match(line))


__all__ = [
    "TOCPageClassification",
    "TOCPageDetector",
    "TOCPageDetectorConfig",
    "TOCPageEvidence",
    "TOCPageEvidenceType",
]
