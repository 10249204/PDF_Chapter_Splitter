from __future__ import annotations

from pdf_chapter_splitter.application import ProgressEvent, WorkflowError, WorkflowStage
from pdf_chapter_splitter.chapters import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterStructureType,
)
from pdf_chapter_splitter.gui.presenters import (
    format_analysis_summary,
    format_application_error,
    format_candidate,
    format_chapter,
    format_progress_event,
    format_text_quality_report,
)
from pdf_chapter_splitter.pdf import PDFTextQualityLevel, PDFTextQualityReport


def test_candidate_view_model_uses_one_based_page_sources_confidence_and_evidence():
    candidate = ChapterCandidate(
        title="Chapter 1 Introduction",
        start_page_index=4,
        source=ChapterCandidateSource.TEXT_LAYOUT,
        sources=(ChapterCandidateSource.TEXT_LAYOUT, ChapterCandidateSource.OUTLINE),
        confidence=0.923,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.TEXT_PATTERN,
                description="Matched Chapter N heading",
                page_index=4,
                text="Chapter 1 Introduction",
            ),
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.FONT_SIZE,
                description="Large heading text",
                page_index=4,
                text="Chapter 1 Introduction",
            ),
        ),
    )

    view_model = format_candidate(candidate, accepted=True)

    assert view_model.title == "Chapter 1 Introduction"
    assert view_model.page_number == 5
    assert view_model.page_label == "Page 5"
    assert view_model.confidence_label == "92.3%"
    assert view_model.sources_label == "text_layout, outline"
    assert view_model.evidence_summary == "text_pattern: Matched Chapter N heading; font_size: Large heading text"
    assert view_model.accepted is True


def test_candidate_view_model_formats_structure_and_quality_flags():
    candidate = ChapterCandidate(
        title="Chapter 1 ........ 12",
        start_page_index=0,
        source=ChapterCandidateSource.TEXT_LAYOUT,
        confidence=0.45,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.TOC_PAGE_SUSPECTED,
                description="toc_page_suspected confidence=0.8",
                page_index=0,
                text="Chapter 1 ........ 12",
            ),
        ),
        structure_type=ChapterStructureType.PRIMARY_CHAPTER,
        quality_flags=(ChapterCandidateQualityFlag.TOC_PAGE_SUSPECTED,),
    )

    view_model = format_candidate(candidate)

    assert view_model.structure_label == "primary_chapter"
    assert view_model.quality_label == "toc_page_suspected"
    assert "toc_page_suspected" in view_model.evidence_summary


def test_text_quality_report_view_model_formats_user_visible_summary():
    report = PDFTextQualityReport(
        page_count=10,
        pages_with_text=2,
        text_coverage_ratio=0.2,
        total_characters=250,
        average_characters_per_text_page=125.0,
        readable_page_ratio=0.1,
        quality_level=PDFTextQualityLevel.LOW,
        likely_scanned=False,
        likely_ocr=True,
        warnings=("weak_text_layer", "ocr_noise_suspected"),
    )

    view_model = format_text_quality_report(report)

    assert view_model.quality_level_label == "LOW"
    assert view_model.text_coverage_label == "Text coverage: 20.0%"
    assert view_model.readable_pages_label == "Readable pages: 10.0%"
    assert view_model.ocr_risk_label == "OCR risk: suspected"
    assert "weak_text_layer" in view_model.warnings_label


def test_analysis_summary_view_model_formats_counts_without_hiding_original_data():
    from pdf_chapter_splitter.application import AnalysisSummary

    summary = AnalysisSummary.from_candidates(
        (
            ChapterCandidate(
                title="Chapter 1",
                start_page_index=0,
                source=ChapterCandidateSource.OUTLINE,
                confidence=0.9,
                level=1,
                evidences=(
                    ChapterEvidence(
                        evidence_type=ChapterEvidenceType.OUTLINE,
                        description="outline evidence",
                        page_index=0,
                        text="Chapter 1",
                    ),
                ),
                structure_type=ChapterStructureType.PRIMARY_CHAPTER,
            ),
        ),
        text_quality_report=None,
    )

    view_model = format_analysis_summary(summary)

    assert view_model.candidate_summary_label == "Candidates: 1 total, 1 primary"
    assert view_model.quality_level_label == "Quality: unknown"


def test_chapter_view_model_uses_one_based_page_level_and_provenance():
    chapter = Chapter.from_page_number(
        "Chapter 2 Methods",
        18,
        level=2,
        provenance=_manual_provenance(),
    )

    view_model = format_chapter(chapter)

    assert view_model.title == "Chapter 2 Methods"
    assert view_model.page_number == 18
    assert view_model.page_label == "Page 18"
    assert view_model.level_label == "Level 2"
    assert view_model.source_label == "manual"


def test_progress_event_view_model_formats_known_total():
    view_model = format_progress_event(
        ProgressEvent(
            WorkflowStage.SPLITTING,
            "Splitting PDF",
            current=2,
            total=5,
        )
    )

    assert view_model.stage_label == "splitting"
    assert view_model.message == "Splitting PDF"
    assert view_model.progress_label == "2 / 5"
    assert view_model.is_indeterminate is False


def test_progress_event_view_model_marks_missing_total_as_indeterminate():
    view_model = format_progress_event(ProgressEvent(WorkflowStage.ANALYZING, "Analyzing"))

    assert view_model.progress_label == ""
    assert view_model.is_indeterminate is True


def test_application_error_view_model_preserves_stage_and_cause_text():
    cause = RuntimeError("disk full")
    error = WorkflowError("Unable to create ZIP archive", stage=WorkflowStage.CREATING_ZIP, cause=cause)

    view_model = format_application_error(error)

    assert view_model.message == "Unable to create ZIP archive"
    assert view_model.stage_label == "creating_zip"
    assert view_model.cause_label == "disk full"


def _manual_provenance():
    from pdf_chapter_splitter.chapters import ChapterProvenance

    evidence = ChapterEvidence(
        evidence_type=ChapterEvidenceType.MANUAL,
        description="User created",
        page_index=17,
        text="Chapter 2 Methods",
    )
    return ChapterProvenance(
        candidate_title=None,
        candidate_start_page_index=None,
        candidate_sources=(ChapterCandidateSource.MANUAL,),
        candidate_confidence=None,
        candidate_evidences=(evidence,),
        candidate_original_titles=("Chapter 2 Methods",),
        confirmed_from_candidate=False,
    )
