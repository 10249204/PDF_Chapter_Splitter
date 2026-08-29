"""PDF text quality diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from pdf_chapter_splitter.pdf.reader import PDFReader


class PDFTextQualityLevel(StrEnum):
    """Overall quality of extractable PDF text."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class PDFTextQualityReport:
    """Read-only report describing whether extracted text is useful."""

    page_count: int
    pages_with_text: int
    text_coverage_ratio: float
    total_characters: int
    average_characters_per_text_page: float
    readable_page_ratio: float
    quality_level: PDFTextQualityLevel
    likely_scanned: bool
    likely_ocr: bool
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.page_count < 0:
            raise ValueError("page_count must be 0 or greater")
        if self.pages_with_text < 0:
            raise ValueError("pages_with_text must be 0 or greater")
        if self.pages_with_text > self.page_count:
            raise ValueError("pages_with_text must be less than or equal to page_count")
        if not 0.0 <= self.text_coverage_ratio <= 1.0:
            raise ValueError("text_coverage_ratio must be between 0.0 and 1.0")
        if self.total_characters < 0:
            raise ValueError("total_characters must be 0 or greater")
        if self.average_characters_per_text_page < 0:
            raise ValueError("average_characters_per_text_page must be 0 or greater")
        if not 0.0 <= self.readable_page_ratio <= 1.0:
            raise ValueError("readable_page_ratio must be between 0.0 and 1.0")
        if not isinstance(self.quality_level, PDFTextQualityLevel):
            raise ValueError("quality_level must be a PDFTextQualityLevel")
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class PDFTextQualityDiagnosticConfig:
    """Thresholds for deterministic text quality classification."""

    min_readable_characters_per_page: int = 12
    high_coverage_threshold: float = 0.80
    medium_coverage_threshold: float = 0.50
    low_coverage_threshold: float = 0.05
    readable_signal_threshold: float = 0.45
    noisy_page_ratio_threshold: float = 0.25

    def __post_init__(self) -> None:
        if self.min_readable_characters_per_page < 1:
            raise ValueError("min_readable_characters_per_page must be 1 or greater")
        for field_name in (
            "high_coverage_threshold",
            "medium_coverage_threshold",
            "low_coverage_threshold",
            "readable_signal_threshold",
            "noisy_page_ratio_threshold",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0.0 and 1.0")


class PDFTextQualityDiagnostic:
    """Analyze extractable text quality through the existing reader contract."""

    def __init__(self, config: PDFTextQualityDiagnosticConfig | None = None) -> None:
        self.config = config or PDFTextQualityDiagnosticConfig()

    def analyze(self, reader: PDFReader) -> PDFTextQualityReport:
        page_count = reader.page_count
        page_texts = reader.get_all_page_text()
        metadata = _safe_metadata(reader)

        pages_with_text = 0
        total_characters = 0
        readable_pages = 0
        noisy_pages = 0

        for text in page_texts:
            normalized = _normalize_text(text)
            character_count = len(normalized)
            if character_count == 0:
                continue
            pages_with_text += 1
            total_characters += character_count
            if _is_noisy_text(normalized, self.config):
                noisy_pages += 1
            if _is_readable_text(normalized, self.config):
                readable_pages += 1

        text_coverage_ratio = _ratio(pages_with_text, page_count)
        readable_page_ratio = _ratio(readable_pages, page_count)
        average_characters = _ratio(total_characters, pages_with_text)

        metadata_mentions_ocr = _metadata_mentions_ocr(metadata)
        likely_scanned = pages_with_text == 0 or (
            text_coverage_ratio < self.config.low_coverage_threshold and total_characters < 100
        )
        likely_ocr = pages_with_text > 0 and (
            metadata_mentions_ocr
            or _ratio(noisy_pages, pages_with_text) >= self.config.noisy_page_ratio_threshold
        )
        quality_level = _quality_level(
            text_coverage_ratio=text_coverage_ratio,
            readable_page_ratio=readable_page_ratio,
            pages_with_text=pages_with_text,
            likely_ocr=likely_ocr,
            config=self.config,
        )
        warnings = _warnings(
            pages_with_text=pages_with_text,
            text_coverage_ratio=text_coverage_ratio,
            readable_page_ratio=readable_page_ratio,
            likely_scanned=likely_scanned,
            likely_ocr=likely_ocr,
            metadata_mentions_ocr=metadata_mentions_ocr,
            config=self.config,
        )

        return PDFTextQualityReport(
            page_count=page_count,
            pages_with_text=pages_with_text,
            text_coverage_ratio=round(text_coverage_ratio, 4),
            total_characters=total_characters,
            average_characters_per_text_page=round(average_characters, 2),
            readable_page_ratio=round(readable_page_ratio, 4),
            quality_level=quality_level,
            likely_scanned=likely_scanned,
            likely_ocr=likely_ocr,
            warnings=warnings,
        )


def _safe_metadata(reader: PDFReader) -> dict[str, str]:
    get_metadata = getattr(reader, "get_metadata", None)
    if get_metadata is None:
        return {}
    return dict(get_metadata())


def _normalize_text(text: str) -> str:
    return "".join(character for character in text if not character.isspace())


def _is_readable_text(text: str, config: PDFTextQualityDiagnosticConfig) -> bool:
    if len(text) < config.min_readable_characters_per_page:
        return False
    return _readable_signal_ratio(text) >= config.readable_signal_threshold and bool(
        re.search(r"[A-Za-z]{3}|[\u4e00-\u9fff]{2}", text)
    )


def _is_noisy_text(text: str, config: PDFTextQualityDiagnosticConfig) -> bool:
    if len(text) < config.min_readable_characters_per_page:
        return False
    return _readable_signal_ratio(text) < config.readable_signal_threshold


def _readable_signal_ratio(text: str) -> float:
    if not text:
        return 0.0
    signal_count = sum(1 for character in text if character.isalnum() or _is_cjk(character))
    return signal_count / len(text)


def _is_cjk(character: str) -> bool:
    return "\u4e00" <= character <= "\u9fff"


def _metadata_mentions_ocr(metadata: dict[str, str]) -> bool:
    joined = " ".join(metadata.values()).casefold()
    return "ocr" in joined or "paper capture" in joined


def _quality_level(
    *,
    text_coverage_ratio: float,
    readable_page_ratio: float,
    pages_with_text: int,
    likely_ocr: bool,
    config: PDFTextQualityDiagnosticConfig,
) -> PDFTextQualityLevel:
    if pages_with_text == 0:
        return PDFTextQualityLevel.NONE
    if (
        text_coverage_ratio >= config.high_coverage_threshold
        and readable_page_ratio >= config.high_coverage_threshold
        and not likely_ocr
    ):
        return PDFTextQualityLevel.HIGH
    if (
        text_coverage_ratio >= config.medium_coverage_threshold
        and readable_page_ratio >= 0.40
        and not likely_ocr
    ):
        return PDFTextQualityLevel.MEDIUM
    return PDFTextQualityLevel.LOW


def _warnings(
    *,
    pages_with_text: int,
    text_coverage_ratio: float,
    readable_page_ratio: float,
    likely_scanned: bool,
    likely_ocr: bool,
    metadata_mentions_ocr: bool,
    config: PDFTextQualityDiagnosticConfig,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if pages_with_text == 0:
        warnings.append("no_extractable_text")
    elif text_coverage_ratio < config.medium_coverage_threshold:
        warnings.append("weak_text_layer")
    if readable_page_ratio < text_coverage_ratio:
        warnings.append("low_readable_text")
    if likely_scanned:
        warnings.append("likely_scanned")
    if likely_ocr:
        warnings.append("ocr_noise_suspected")
    if metadata_mentions_ocr:
        warnings.append("metadata_mentions_ocr")
    return tuple(warnings)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


__all__ = [
    "PDFTextQualityDiagnostic",
    "PDFTextQualityDiagnosticConfig",
    "PDFTextQualityLevel",
    "PDFTextQualityReport",
]
