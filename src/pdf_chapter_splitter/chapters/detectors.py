"""Text layout based chapter candidate detection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import re
from statistics import median

from pdf_chapter_splitter.chapters.adapters import sort_chapter_candidates
from pdf_chapter_splitter.chapters.models import (
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
)
from pdf_chapter_splitter.chapters.toc import TOCPageClassification, TOCPageDetector
from pdf_chapter_splitter.pdf.models import PageSize, TextBlock
from pdf_chapter_splitter.pdf.reader import PDFReader


_CHINESE_NUMBER = r"[0-9一二三四五六七八九十百千万零〇两]+"
_CHINESE_CHAPTER_RE = re.compile(rf"^第\s*{_CHINESE_NUMBER}\s*章(?:\s|[:：]|$).*$")
_CHINESE_SECTION_RE = re.compile(rf"^第\s*{_CHINESE_NUMBER}\s*节(?:\s|[:：]|$).*$")
_ENGLISH_CHAPTER_RE = re.compile(r"^chapter\s+\d+\b(?:\s*[:：.-]\s*|\s+|$).*$", re.IGNORECASE)
_NUMERIC_TITLE_RE = re.compile(r"^\d{1,3}\s+[^\W\d_].*$", re.UNICODE)


@dataclass(frozen=True, slots=True)
class TextLayoutDetectorConfig:
    """Tunable thresholds and weights for text layout detection."""

    min_confidence: float = 0.60
    include_sections: bool = False
    max_title_characters: int = 80
    min_title_characters: int = 2
    min_body_text_characters: int = 30
    font_size_ratio_threshold: float = 1.30
    top_region_ratio: float = 0.25
    pattern_weight: float = 0.40
    font_size_weight: float = 0.30
    position_weight: float = 0.15
    text_length_weight: float = 0.15
    toc_confidence_penalty: float = 0.30

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if self.max_title_characters < self.min_title_characters:
            raise ValueError("max_title_characters must be greater than or equal to min_title_characters")
        if self.min_title_characters < 1:
            raise ValueError("min_title_characters must be 1 or greater")
        if self.min_body_text_characters < 1:
            raise ValueError("min_body_text_characters must be 1 or greater")
        if self.font_size_ratio_threshold <= 0:
            raise ValueError("font_size_ratio_threshold must be greater than 0")
        if not 0.0 <= self.top_region_ratio <= 1.0:
            raise ValueError("top_region_ratio must be between 0.0 and 1.0")
        if not 0.0 <= self.toc_confidence_penalty <= 1.0:
            raise ValueError("toc_confidence_penalty must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class TextLayoutFeatures:
    """Observed layout facts for one text block."""

    text: str
    text_length: int
    page_index: int
    block_index: int
    font_size: float
    body_font_size: float
    font_size_ratio: float
    top_position_ratio: float
    pattern_name: str | None


class TextLayoutCandidateDetector:
    """Detect possible chapter starts from existing PDF text layout data."""

    def __init__(
        self,
        config: TextLayoutDetectorConfig | None = None,
        toc_detector: TOCPageDetector | None = None,
    ) -> None:
        self.config = config or TextLayoutDetectorConfig()
        self.toc_detector = toc_detector or TOCPageDetector()

    def detect(
        self,
        reader: PDFReader,
        pages: Iterable[int] | None = None,
    ) -> tuple[ChapterCandidate, ...]:
        page_indexes = _normalize_pages(pages, reader.page_count)
        page_layouts = tuple(
            _PageLayout(
                page_index=page_index,
                page_size=reader.get_page_size(page_index),
                blocks=tuple(reader.get_page_text_blocks(page_index)),
            )
            for page_index in page_indexes
        )
        body_font_size = _estimate_body_font_size(page_layouts, self.config)
        toc_classifications = {
            page_layout.page_index: self.toc_detector.classify_text(
                _page_text(page_layout),
                page_index=page_layout.page_index,
            )
            for page_layout in page_layouts
        }

        candidates: list[ChapterCandidate] = []
        seen_blocks: set[tuple[int, int, str]] = set()
        for page_layout in page_layouts:
            for block in page_layout.blocks:
                features = _extract_features(
                    block=block,
                    page_index=page_layout.page_index,
                    page_size=page_layout.page_size,
                    body_font_size=body_font_size,
                    config=self.config,
                )
                if features is None:
                    continue

                confidence, evidences = _score_features(features, self.config)
                if confidence < self.config.min_confidence:
                    continue
                quality_flags: tuple[ChapterCandidateQualityFlag, ...] = ()
                toc_classification = toc_classifications[features.page_index]
                if toc_classification.is_toc_page:
                    confidence = max(
                        0.0,
                        round(confidence - self.config.toc_confidence_penalty, 2),
                    )
                    evidences = [*evidences, _toc_page_evidence(features, toc_classification)]
                    quality_flags = (ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,)

                block_key = (features.page_index, features.block_index, features.text)
                if block_key in seen_blocks:
                    continue
                seen_blocks.add(block_key)
                candidates.append(
                    ChapterCandidate(
                        title=features.text,
                        start_page_index=features.page_index,
                        source=ChapterCandidateSource.TEXT_LAYOUT,
                        confidence=confidence,
                        level=1,
                        evidences=tuple(evidences),
                        quality_flags=quality_flags,
                    )
                )

        return sort_chapter_candidates(candidates)


@dataclass(frozen=True, slots=True)
class _PageLayout:
    page_index: int
    page_size: PageSize
    blocks: tuple[TextBlock, ...]


def _normalize_pages(pages: Iterable[int] | None, page_count: int) -> tuple[int, ...]:
    if pages is None:
        return tuple(range(page_count))

    page_indexes = tuple(pages)
    for page_index in page_indexes:
        if not isinstance(page_index, int):
            raise ValueError("pages must contain integer page indexes")
        if page_index < 0 or page_index >= page_count:
            raise ValueError(f"page index {page_index} is outside valid range 0..{page_count - 1}")
    return page_indexes


def _estimate_body_font_size(
    page_layouts: Sequence[_PageLayout],
    config: TextLayoutDetectorConfig,
) -> float:
    weighted_counts: defaultdict[float, int] = defaultdict(int)
    all_sizes: list[float] = []

    for page_layout in page_layouts:
        for block in page_layout.blocks:
            block_text = _normalize_text(block.text)
            if not block_text:
                continue
            for text, font_size in _iter_span_text_and_font_size(block):
                rounded_size = round(font_size, 1)
                all_sizes.append(rounded_size)
                if len(block_text) >= config.min_body_text_characters:
                    weighted_counts[rounded_size] += max(1, len(_normalize_text(text)))

    if weighted_counts:
        return max(weighted_counts.items(), key=lambda item: (item[1], -item[0]))[0]
    if all_sizes:
        return float(median(all_sizes))
    return 12.0


def _extract_features(
    block: TextBlock,
    page_index: int,
    page_size: PageSize,
    body_font_size: float,
    config: TextLayoutDetectorConfig,
) -> TextLayoutFeatures | None:
    text = _normalize_text(block.text)
    if not text:
        return None
    if _looks_like_common_non_chapter_label(text):
        return None

    font_size = _representative_font_size(block)
    if font_size is None:
        return None

    pattern_name = _match_pattern(text, config)
    font_size_ratio = font_size / body_font_size if body_font_size > 0 else 1.0
    top_position_ratio = block.bbox.y0 / page_size.height

    return TextLayoutFeatures(
        text=text,
        text_length=len(text),
        page_index=page_index,
        block_index=block.block_index,
        font_size=float(round(font_size, 1)),
        body_font_size=float(round(body_font_size, 1)),
        font_size_ratio=round(font_size_ratio, 2),
        top_position_ratio=round(top_position_ratio, 2),
        pattern_name=pattern_name,
    )


def _score_features(
    features: TextLayoutFeatures,
    config: TextLayoutDetectorConfig,
) -> tuple[float, list[ChapterEvidence]]:
    score = 0.0
    evidences: list[ChapterEvidence] = []

    if features.pattern_name is not None:
        score += config.pattern_weight
        evidences.append(
            _evidence(
                ChapterEvidenceType.TEXT_PATTERN,
                features,
                f"pattern={features.pattern_name}",
            )
        )

    title_length_is_reasonable = (
        config.min_title_characters <= features.text_length <= config.max_title_characters
    )
    if title_length_is_reasonable:
        score += config.text_length_weight
        evidences.append(
            _evidence(
                ChapterEvidenceType.PAGE_LAYOUT,
                features,
                f"text_length={features.text_length}",
            )
        )

    if features.font_size_ratio >= config.font_size_ratio_threshold:
        score += config.font_size_weight
        evidences.append(
            _evidence(
                ChapterEvidenceType.FONT_SIZE,
                features,
                (
                    f"font_size={features.font_size} "
                    f"body_font_size={features.body_font_size} "
                    f"font_size_ratio={features.font_size_ratio}"
                ),
            )
        )

    if features.top_position_ratio <= config.top_region_ratio:
        score += config.position_weight
        evidences.append(
            _evidence(
                ChapterEvidenceType.POSITION,
                features,
                f"top_position_ratio={features.top_position_ratio}",
            )
        )

    if features.pattern_name is None:
        return 0.0, []
    if features.pattern_name == "numeric" and features.font_size_ratio < config.font_size_ratio_threshold:
        return 0.0, []

    return min(1.0, round(score, 2)), evidences


def _toc_page_evidence(
    features: TextLayoutFeatures,
    classification: TOCPageClassification,
) -> ChapterEvidence:
    evidence_names = ",".join(evidence.evidence_type.value for evidence in classification.evidences)
    return ChapterEvidence(
        evidence_type=ChapterEvidenceType.TOC_PAGE_SUSPECTED,
        description=f"toc_page_suspected confidence={classification.confidence} evidence={evidence_names}",
        page_index=features.page_index,
        text=features.text,
    )


def _evidence(
    evidence_type: ChapterEvidenceType,
    features: TextLayoutFeatures,
    description: str,
) -> ChapterEvidence:
    return ChapterEvidence(
        evidence_type=evidence_type,
        description=description,
        page_index=features.page_index,
        text=features.text,
    )


def _match_pattern(text: str, config: TextLayoutDetectorConfig) -> str | None:
    if _CHINESE_CHAPTER_RE.match(text):
        return "chinese_chapter"
    if config.include_sections and _CHINESE_SECTION_RE.match(text):
        return "chinese_section"
    if _ENGLISH_CHAPTER_RE.match(text):
        return "english_chapter"
    if _NUMERIC_TITLE_RE.match(text):
        return "numeric"
    return None


def _representative_font_size(block: TextBlock) -> float | None:
    weighted_total = 0.0
    character_count = 0
    for text, font_size in _iter_span_text_and_font_size(block):
        weight = max(1, len(_normalize_text(text)))
        weighted_total += font_size * weight
        character_count += weight
    if character_count == 0:
        return None
    return weighted_total / character_count


def _iter_span_text_and_font_size(block: TextBlock):
    for line in block.lines:
        for span in line.spans:
            if span.font_size is None:
                continue
            if not _normalize_text(span.text):
                continue
            yield span.text, span.font_size


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _page_text(page_layout: _PageLayout) -> str:
    return "\n".join(block.text for block in page_layout.blocks)


def _looks_like_common_non_chapter_label(text: str) -> bool:
    lower_text = text.casefold()
    return lower_text.startswith(
        (
            "table ",
            "figure ",
            "fig. ",
            "example ",
            "copyright ",
            "references",
            "reference",
        )
    )


__all__ = [
    "TextLayoutCandidateDetector",
    "TextLayoutDetectorConfig",
    "TextLayoutFeatures",
]
