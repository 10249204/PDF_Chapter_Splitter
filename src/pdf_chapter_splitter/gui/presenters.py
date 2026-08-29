"""Presentation helpers for the desktop GUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pdf_chapter_splitter.application import ApplicationError, ProgressEvent


@dataclass(frozen=True, slots=True)
class CandidateViewModel:
    """GUI-ready chapter candidate text."""

    title: str
    page_number: int
    page_label: str
    confidence_label: str
    structure_label: str
    sources_label: str
    quality_label: str
    evidence_summary: str
    accepted: bool = False


@dataclass(frozen=True, slots=True)
class ChapterViewModel:
    """GUI-ready confirmed chapter text."""

    title: str
    page_number: int
    page_label: str
    level_label: str
    source_label: str


@dataclass(frozen=True, slots=True)
class ProgressViewModel:
    """GUI-ready progress text."""

    stage_label: str
    message: str
    progress_label: str
    is_indeterminate: bool


@dataclass(frozen=True, slots=True)
class TextQualityReportViewModel:
    """GUI-ready PDF text quality summary."""

    quality_level_label: str
    text_coverage_label: str
    readable_pages_label: str
    ocr_risk_label: str
    warnings_label: str


@dataclass(frozen=True, slots=True)
class AnalysisSummaryViewModel:
    """GUI-ready analysis summary text."""

    quality_level_label: str
    candidate_summary_label: str
    quality_signal_label: str


@dataclass(frozen=True, slots=True)
class ErrorViewModel:
    """GUI-ready application error text."""

    message: str
    stage_label: str
    cause_label: str


def format_candidate(candidate: Any, *, accepted: bool = False) -> CandidateViewModel:
    """Convert a ChapterCandidate-like object into GUI display text."""

    page_number = candidate.start_page_index + 1
    return CandidateViewModel(
        title=candidate.title,
        page_number=page_number,
        page_label=f"Page {page_number}",
        confidence_label=f"{candidate.confidence:.1%}",
        structure_label=getattr(candidate.structure_type, "value", str(candidate.structure_type)),
        sources_label=", ".join(source.value for source in candidate.sources),
        quality_label=_quality_label(candidate),
        evidence_summary="; ".join(
            f"{evidence.evidence_type.value}: {evidence.description}"
            for evidence in candidate.evidences
        ),
        accepted=accepted,
    )


def format_text_quality_report(report: Any | None) -> TextQualityReportViewModel:
    """Convert a PDFTextQualityReport-like object into GUI display text."""

    if report is None:
        return TextQualityReportViewModel(
            quality_level_label="unknown",
            text_coverage_label="Text coverage: -",
            readable_pages_label="Readable pages: -",
            ocr_risk_label="OCR risk: unknown",
            warnings_label="",
        )

    return TextQualityReportViewModel(
        quality_level_label=getattr(report.quality_level, "name", str(report.quality_level)).upper(),
        text_coverage_label=f"Text coverage: {report.text_coverage_ratio:.1%}",
        readable_pages_label=f"Readable pages: {report.readable_page_ratio:.1%}",
        ocr_risk_label="OCR risk: suspected" if report.likely_ocr else "OCR risk: none",
        warnings_label=", ".join(report.warnings),
    )


def format_analysis_summary(summary: Any | None) -> AnalysisSummaryViewModel:
    """Convert an AnalysisSummary-like object into GUI display text."""

    if summary is None:
        return AnalysisSummaryViewModel(
            quality_level_label="Quality: unknown",
            candidate_summary_label="Candidates: 0 total, 0 primary",
            quality_signal_label="Quality signals: -",
        )

    quality = format_text_quality_report(summary.text_quality_report)
    return AnalysisSummaryViewModel(
        quality_level_label=f"Quality: {quality.quality_level_label}",
        candidate_summary_label=(
            f"Candidates: {summary.candidate_count} total, "
            f"{summary.primary_chapter_candidate_count} primary"
        ),
        quality_signal_label=(
            f"Signals: {summary.toc_suspected_candidate_count} TOC suspected, "
            f"{summary.low_quality_candidate_count} low quality, "
            f"{summary.poor_title_candidate_count} poor title"
        ),
    )


def format_chapter(chapter: Any) -> ChapterViewModel:
    """Convert a Chapter-like object into GUI display text."""

    sources = ()
    if chapter.provenance is not None:
        sources = chapter.provenance.candidate_sources
    source_label = ", ".join(source.value for source in sources) if sources else "manual"
    return ChapterViewModel(
        title=chapter.title,
        page_number=chapter.gui_page_number,
        page_label=f"Page {chapter.gui_page_number}",
        level_label=f"Level {chapter.level}",
        source_label=source_label,
    )


def format_progress_event(event: ProgressEvent) -> ProgressViewModel:
    """Convert a ProgressEvent into GUI display text."""

    if event.current is None or event.total is None:
        progress_label = ""
        is_indeterminate = True
    else:
        progress_label = f"{event.current} / {event.total}"
        is_indeterminate = False

    return ProgressViewModel(
        stage_label=event.stage.value,
        message=event.message,
        progress_label=progress_label,
        is_indeterminate=is_indeterminate,
    )


def format_application_error(error: ApplicationError) -> ErrorViewModel:
    """Convert an ApplicationError into GUI display text."""

    cause_label = "" if error.cause is None else str(error.cause)
    return ErrorViewModel(
        message=error.message,
        stage_label=error.stage.value,
        cause_label=cause_label,
    )


def _quality_label(candidate: Any) -> str:
    flags = tuple(getattr(candidate, "quality_flags", ()))
    if not flags:
        return "Good"
    return ", ".join(getattr(flag, "value", str(flag)) for flag in flags)


__all__ = [
    "AnalysisSummaryViewModel",
    "CandidateViewModel",
    "ChapterViewModel",
    "ErrorViewModel",
    "ProgressViewModel",
    "TextQualityReportViewModel",
    "format_analysis_summary",
    "format_application_error",
    "format_candidate",
    "format_chapter",
    "format_progress_event",
    "format_text_quality_report",
]
