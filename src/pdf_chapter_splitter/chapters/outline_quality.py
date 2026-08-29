"""Outline candidate quality and structure classification."""

from __future__ import annotations

from dataclasses import dataclass
import re

from pdf_chapter_splitter.chapters.models import (
    ChapterCandidateQualityFlag,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)


@dataclass(frozen=True, slots=True)
class OutlineCandidateQuality:
    """Quality metadata derived from one outline title."""

    structure_type: ChapterStructureType
    confidence: float
    quality_flags: tuple[ChapterCandidateQualityFlag, ...]
    evidences: tuple[ChapterEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.structure_type, ChapterStructureType):
            raise ValueError("structure_type must be a ChapterStructureType")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        for flag in self.quality_flags:
            if not isinstance(flag, ChapterCandidateQualityFlag):
                raise ValueError("quality_flags must contain ChapterCandidateQualityFlag items")


class OutlineQualityClassifier:
    """Classify outline titles without deleting user-visible information."""

    def classify(self, title: str, *, page_index: int = 0) -> OutlineCandidateQuality:
        normalized = " ".join(title.split())
        lowered = normalized.casefold()
        structure_type = _structure_type(normalized, lowered)
        flags = _quality_flags(normalized, lowered, structure_type)
        confidence = _confidence_for(structure_type, flags)

        evidences = [
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.OUTLINE_STRUCTURE,
                description=f"outline_structure={structure_type.value}",
                page_index=page_index,
                text=normalized,
            )
        ]
        if flags:
            evidences.append(
                ChapterEvidence(
                    evidence_type=ChapterEvidenceType.OUTLINE_TITLE_QUALITY,
                    description="quality_flags=" + ",".join(flag.value for flag in flags),
                    page_index=page_index,
                    text=normalized,
                )
            )

        return OutlineCandidateQuality(
            structure_type=structure_type,
            confidence=confidence,
            quality_flags=flags,
            evidences=tuple(evidences),
        )


_CHINESE_NUMBER = r"[0-9一二三四五六七八九十百千万零〇两]+"
_ROMAN_NUMBER = r"[IVXLCDMⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+"
_CHINESE_CHAPTER_RE = re.compile(rf"^第\s*{_CHINESE_NUMBER}\s*章(?:\s|[:：]|$).*$")
_CHINESE_SECTION_RE = re.compile(rf"^第\s*{_CHINESE_NUMBER}\s*节(?:\s|[:：]|$).*$")
_CHINESE_PART_RE = re.compile(rf"^第\s*(?:{_CHINESE_NUMBER}|{_ROMAN_NUMBER})\s*部分.*$")
_ENGLISH_CHAPTER_RE = re.compile(r"^chapter\s+\d+\b(?:\s*[:：.-]\s*|\s+|$).*$", re.IGNORECASE)
_ENGLISH_PART_RE = re.compile(r"^part\s+(?:\d+|[ivxlcdm]+)\b.*$", re.IGNORECASE)
_NUMERIC_PRIMARY_RE = re.compile(r"^\d{1,3}\s+[^\W\d_].*$", re.UNICODE)
_SECTION_RE = re.compile(r"^\d{1,3}\.\d{1,3}(?:\s|$).*$")
_SUBSECTION_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}(?:\s|$).*$")
_DOI_OR_FILE_RE = re.compile(
    r"^(?:10\.\d{4,}[_/.-].*|.*\.(?:pdf|epub|mobi)$|[\w.-]+_\d[\w.-]*)$",
    re.IGNORECASE,
)

_FRONT_MATTER_TITLES = {
    "cover",
    "title page",
    "contents",
    "table of contents",
    "preface",
    "foreword",
    "copyright",
    "版权",
    "版权信息",
    "封面",
    "封底",
    "目录",
    "前言",
    "推荐序",
}
_BACK_MATTER_TITLES = {
    "references",
    "reference",
    "bibliography",
    "index",
    "notes",
    "acknowledgments",
    "acknowledgements",
    "appendix",
    "appendices",
    "参考文献",
    "索引",
    "注释",
    "后记",
    "附录",
}


def _structure_type(title: str, lowered: str) -> ChapterStructureType:
    if _SUBSECTION_RE.match(title):
        return ChapterStructureType.SUBSECTION
    if _SECTION_RE.match(title) or _CHINESE_SECTION_RE.match(title):
        return ChapterStructureType.SECTION
    if _CHINESE_PART_RE.match(title) or _ENGLISH_PART_RE.match(title):
        return ChapterStructureType.PART
    if _is_front_matter(title, lowered):
        return ChapterStructureType.FRONT_MATTER
    if _is_back_matter(title, lowered):
        return ChapterStructureType.BACK_MATTER
    if (
        _CHINESE_CHAPTER_RE.match(title)
        or _ENGLISH_CHAPTER_RE.match(title)
        or _NUMERIC_PRIMARY_RE.match(title)
    ):
        return ChapterStructureType.PRIMARY_CHAPTER
    return ChapterStructureType.UNKNOWN


def _is_front_matter(title: str, lowered: str) -> bool:
    return lowered in _FRONT_MATTER_TITLES or any(title.startswith(value) for value in ("推荐序",))


def _is_back_matter(title: str, lowered: str) -> bool:
    return lowered in _BACK_MATTER_TITLES or any(
        lowered.startswith(prefix)
        for prefix in ("appendix ", "附录", "references", "bibliography", "index")
    )


def _quality_flags(
    title: str,
    lowered: str,
    structure_type: ChapterStructureType,
) -> tuple[ChapterCandidateQualityFlag, ...]:
    flags: list[ChapterCandidateQualityFlag] = []
    if structure_type is not ChapterStructureType.PRIMARY_CHAPTER:
        flags.append(ChapterCandidateQualityFlag.NON_PRIMARY_STRUCTURE)
    if _DOI_OR_FILE_RE.match(lowered):
        flags.extend(
            [
                ChapterCandidateQualityFlag.POOR_TITLE_QUALITY,
                ChapterCandidateQualityFlag.DOI_OR_FILE_TITLE,
            ]
        )
    return tuple(dict.fromkeys(flags))


def _confidence_for(
    structure_type: ChapterStructureType,
    flags: tuple[ChapterCandidateQualityFlag, ...],
) -> float:
    if ChapterCandidateQualityFlag.DOI_OR_FILE_TITLE in flags:
        return 0.55
    if structure_type is ChapterStructureType.PRIMARY_CHAPTER:
        return 0.95
    if structure_type in (ChapterStructureType.SECTION, ChapterStructureType.SUBSECTION):
        return 0.65
    if structure_type in (
        ChapterStructureType.FRONT_MATTER,
        ChapterStructureType.BACK_MATTER,
        ChapterStructureType.PART,
    ):
        return 0.70
    return 0.75


__all__ = ["OutlineCandidateQuality", "OutlineQualityClassifier"]
