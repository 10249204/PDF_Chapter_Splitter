"""Fusion for chapter candidates from independent sources."""

from __future__ import annotations

from dataclasses import dataclass
import re

from pdf_chapter_splitter.chapters.models import (
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterStructureType,
)


_SOURCE_PRIORITY = (
    ChapterCandidateSource.MANUAL,
    ChapterCandidateSource.TEXT_LAYOUT,
    ChapterCandidateSource.OUTLINE,
    ChapterCandidateSource.OCR,
    ChapterCandidateSource.AI,
)

_PUNCTUATION_RE = re.compile(r"[:：,，.。;；!！?？\-_/\\()\[\]{}<>《》\"'“”‘’]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_CHINESE_CHAPTER_NUMBER_RE = re.compile(r"第\s*([0-9一二三四五六七八九十百千万零〇两]+)\s*[章节]")
_ENGLISH_CHAPTER_NUMBER_RE = re.compile(r"\bchapter\s+(\d{1,4})\b", re.IGNORECASE)
_NUMERIC_TITLE_NUMBER_RE = re.compile(r"^(\d{1,4})\s+")


@dataclass(frozen=True, slots=True)
class CandidateFusionConfig:
    """Configuration for grouping nearby chapter candidates."""

    max_page_distance: int = 1
    source_priority: tuple[ChapterCandidateSource, ...] = _SOURCE_PRIORITY
    multi_source_confidence_bonus: float = 0.05
    extra_candidate_confidence_bonus: float = 0.03

    def __post_init__(self) -> None:
        if self.max_page_distance < 0:
            raise ValueError("max_page_distance must be 0 or greater")
        if not 0.0 <= self.multi_source_confidence_bonus <= 1.0:
            raise ValueError("multi_source_confidence_bonus must be between 0.0 and 1.0")
        if not 0.0 <= self.extra_candidate_confidence_bonus <= 1.0:
            raise ValueError("extra_candidate_confidence_bonus must be between 0.0 and 1.0")
        if not self.source_priority:
            raise ValueError("source_priority must not be empty")
        for source in self.source_priority:
            if not isinstance(source, ChapterCandidateSource):
                raise ValueError("source_priority must contain ChapterCandidateSource items")


class CandidateFusion:
    """Fuse candidates that likely describe the same possible chapter start."""

    def __init__(self, config: CandidateFusionConfig | None = None) -> None:
        self.config = config or CandidateFusionConfig()

    def fuse(self, candidates: tuple[ChapterCandidate, ...]) -> tuple[ChapterCandidate, ...]:
        """Return new fused candidates without mutating the inputs."""

        candidate_list = tuple(candidates)
        if not candidate_list:
            return ()

        groups = self._group_candidates(candidate_list)
        fused = tuple(self._fuse_group(group) for group in groups)
        return tuple(
            sorted(
                fused,
                key=lambda candidate: (
                    candidate.start_page_index,
                    -candidate.confidence,
                    self._source_rank(candidate.source),
                    _canonical_title(candidate.title),
                    candidate.title,
                ),
            )
        )

    def _group_candidates(
        self,
        candidates: tuple[ChapterCandidate, ...],
    ) -> tuple[tuple[ChapterCandidate, ...], ...]:
        parents = list(range(len(candidates)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left_index, left in enumerate(candidates):
            for right_index in range(left_index + 1, len(candidates)):
                right = candidates[right_index]
                if self._should_group(left, right):
                    union(left_index, right_index)

        grouped: dict[int, list[ChapterCandidate]] = {}
        for index, candidate in enumerate(candidates):
            grouped.setdefault(find(index), []).append(candidate)

        groups = tuple(tuple(sorted(group, key=self._candidate_sort_key)) for group in grouped.values())
        return tuple(sorted(groups, key=lambda group: self._candidate_sort_key(group[0])))

    def _should_group(self, left: ChapterCandidate, right: ChapterCandidate) -> bool:
        if abs(left.start_page_index - right.start_page_index) > self.config.max_page_distance:
            return False

        left_number = _chapter_number(left.title)
        right_number = _chapter_number(right.title)
        if left_number is not None and right_number is not None and left_number != right_number:
            return False

        if _canonical_title(left.title) == _canonical_title(right.title):
            return True

        if _has_manual_source(left) or _has_manual_source(right):
            return True

        return False

    def _fuse_group(self, group: tuple[ChapterCandidate, ...]) -> ChapterCandidate:
        representative = min(group, key=self._candidate_sort_key)
        sources = _unique_sources(
            (source for candidate in group for source in candidate.sources),
            self._source_rank,
        )
        evidences = _unique_evidences(evidence for candidate in group for evidence in candidate.evidences)
        original_titles = _unique_titles(title for candidate in group for title in candidate.original_titles)
        confidence = self._fused_confidence(group, sources)
        quality_flags = _unique_quality_flags(
            quality_flag for candidate in group for quality_flag in candidate.quality_flags
        )
        structure_type = _representative_structure_type(group)

        return ChapterCandidate(
            title=representative.title,
            start_page_index=representative.start_page_index,
            source=representative.source,
            confidence=confidence,
            level=representative.level,
            evidences=evidences,
            sources=sources,
            original_titles=original_titles,
            structure_type=structure_type,
            quality_flags=quality_flags,
        )

    def _fused_confidence(
        self,
        group: tuple[ChapterCandidate, ...],
        sources: tuple[ChapterCandidateSource, ...],
    ) -> float:
        if ChapterCandidateSource.MANUAL in sources:
            return 1.0

        best_confidence = max(candidate.confidence for candidate in group)
        source_bonus = self.config.multi_source_confidence_bonus * max(0, len(sources) - 1)
        candidate_bonus = self.config.extra_candidate_confidence_bonus * max(0, len(group) - len(sources))
        return min(1.0, round(best_confidence + source_bonus + candidate_bonus, 2))

    def _candidate_sort_key(self, candidate: ChapterCandidate):
        return (
            self._source_rank(candidate.source),
            -candidate.confidence,
            candidate.start_page_index,
            _canonical_title(candidate.title),
            candidate.title,
        )

    def _source_rank(self, source: ChapterCandidateSource) -> int:
        try:
            return self.config.source_priority.index(source)
        except ValueError:
            return len(self.config.source_priority)


def _canonical_title(title: str) -> str:
    normalized = _PUNCTUATION_RE.sub(" ", title.casefold())
    normalized = " ".join(normalized.split())
    if _CJK_RE.search(normalized):
        return normalized.replace(" ", "")
    return normalized


def _chapter_number(title: str) -> str | None:
    for pattern in (
        _CHINESE_CHAPTER_NUMBER_RE,
        _ENGLISH_CHAPTER_NUMBER_RE,
        _NUMERIC_TITLE_NUMBER_RE,
    ):
        match = pattern.search(title)
        if match:
            return _normalize_chapter_number(match.group(1))
    return None


def _normalize_chapter_number(value: str) -> str:
    value = value.strip()
    if value.isdecimal():
        return str(int(value))
    chinese_number = _parse_simple_chinese_number(value)
    if chinese_number is not None:
        return str(chinese_number)
    return value


def _parse_simple_chinese_number(value: str) -> int | None:
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if all(character in digits for character in value):
        return int("".join(str(digits[character]) for character in value))
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = digits[left] if left else 1
        ones = digits[right] if right else 0
        return tens * 10 + ones
    return None


def _has_manual_source(candidate: ChapterCandidate) -> bool:
    return ChapterCandidateSource.MANUAL in candidate.sources


def _unique_sources(
    sources,
    source_rank,
) -> tuple[ChapterCandidateSource, ...]:
    unique = set(sources)
    return tuple(sorted(unique, key=lambda source: (source_rank(source), source.value)))


def _unique_evidences(evidences) -> tuple[ChapterEvidence, ...]:
    unique: dict[tuple[str, str, int, str], ChapterEvidence] = {}
    for evidence in evidences:
        key = (
            evidence.evidence_type.value,
            evidence.description,
            evidence.page_index,
            evidence.text,
        )
        unique.setdefault(key, evidence)
    return tuple(
        unique[key]
        for key in sorted(unique)
    )


def _unique_titles(titles) -> tuple[str, ...]:
    unique: dict[str, str] = {}
    for title in titles:
        unique.setdefault(_canonical_title(title), title)
    return tuple(unique[key] for key in sorted(unique))


def _unique_quality_flags(quality_flags) -> tuple[ChapterCandidateQualityFlag, ...]:
    return tuple(sorted(set(quality_flags), key=lambda quality_flag: quality_flag.value))


def _representative_structure_type(group: tuple[ChapterCandidate, ...]) -> ChapterStructureType:
    priority = (
        ChapterStructureType.PRIMARY_CHAPTER,
        ChapterStructureType.PART,
        ChapterStructureType.SECTION,
        ChapterStructureType.SUBSECTION,
        ChapterStructureType.FRONT_MATTER,
        ChapterStructureType.BACK_MATTER,
        ChapterStructureType.UNKNOWN,
    )
    structures = {candidate.structure_type for candidate in group}
    for structure_type in priority:
        if structure_type in structures:
            return structure_type
    return ChapterStructureType.UNKNOWN


__all__ = ["CandidateFusion", "CandidateFusionConfig"]
