from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pdf_chapter_splitter.pdf import (
    PDFTextQualityDiagnostic,
    PDFTextQualityLevel,
    PyMuPDFReader,
)


def test_text_quality_diagnostic_reports_high_quality_text_pdf(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        report = PDFTextQualityDiagnostic().analyze(reader)

    assert report.page_count == 2
    assert report.pages_with_text == 2
    assert report.text_coverage_ratio == pytest.approx(1.0)
    assert report.total_characters > 0
    assert report.average_characters_per_text_page > 0
    assert report.readable_page_ratio == pytest.approx(1.0)
    assert report.quality_level is PDFTextQualityLevel.HIGH
    assert report.likely_scanned is False
    assert report.likely_ocr is False
    assert report.warnings == ()


def test_text_quality_diagnostic_reports_low_quality_partial_text_layer(
    partial_text_pdf_path: Path,
):
    with PyMuPDFReader(partial_text_pdf_path) as reader:
        report = PDFTextQualityDiagnostic().analyze(reader)

    assert report.page_count == 5
    assert report.pages_with_text == 1
    assert report.text_coverage_ratio == pytest.approx(0.2)
    assert report.readable_page_ratio == pytest.approx(0.2)
    assert report.quality_level is PDFTextQualityLevel.LOW
    assert report.likely_scanned is False
    assert "weak_text_layer" in report.warnings


def test_text_quality_diagnostic_reports_none_for_image_only_pdf(image_only_pdf_path: Path):
    with PyMuPDFReader(image_only_pdf_path) as reader:
        report = PDFTextQualityDiagnostic().analyze(reader)

    assert report.pages_with_text == 0
    assert report.text_coverage_ratio == pytest.approx(0.0)
    assert report.total_characters == 0
    assert report.average_characters_per_text_page == pytest.approx(0.0)
    assert report.readable_page_ratio == pytest.approx(0.0)
    assert report.quality_level is PDFTextQualityLevel.NONE
    assert report.likely_scanned is True
    assert "no_extractable_text" in report.warnings


def test_text_quality_diagnostic_flags_ocr_like_noise(ocr_like_text_pdf_path: Path):
    with PyMuPDFReader(ocr_like_text_pdf_path) as reader:
        report = PDFTextQualityDiagnostic().analyze(reader)

    assert report.pages_with_text == 3
    assert report.likely_scanned is False
    assert report.likely_ocr is True
    assert report.quality_level is PDFTextQualityLevel.LOW
    assert "ocr_noise_suspected" in report.warnings


def test_text_quality_report_is_immutable(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        report = PDFTextQualityDiagnostic().analyze(reader)

    with pytest.raises(FrozenInstanceError):
        report.page_count = 99
