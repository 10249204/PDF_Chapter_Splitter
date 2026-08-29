from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pdf_chapter_splitter.pdf import PyMuPDFReader
from pdf_chapter_splitter.pdf.errors import (
    PDFClosedError,
    PDFOpenError,
    PDFPageIndexError,
    PDFPasswordError,
)
from pdf_chapter_splitter.pdf.models import OutlineItem, TextBlock


def test_reader_opens_real_pdf_and_reports_page_count(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        assert reader.page_count == 2


def test_reader_rejects_missing_file(tmp_path: Path):
    missing_path = tmp_path / "missing.pdf"

    with pytest.raises(PDFOpenError):
        PyMuPDFReader(missing_path)


def test_reader_rejects_directory_path(tmp_path: Path):
    with pytest.raises(PDFOpenError):
        PyMuPDFReader(tmp_path)


def test_reader_rejects_password_protected_pdf(password_pdf_path: Path):
    with pytest.raises(PDFPasswordError):
        PyMuPDFReader(password_pdf_path)


@pytest.mark.parametrize(
    ("page_index", "expected_text"),
    [
        (0, "Chapter 1\nHello World"),
        (1, "Chapter 2\nHello PDF"),
    ],
)
def test_reader_gets_page_text_with_zero_based_page_index(
    text_pdf_path: Path, page_index: int, expected_text: str
):
    with PyMuPDFReader(text_pdf_path) as reader:
        assert expected_text in reader.get_page_text(page_index)


@pytest.mark.parametrize("page_index", [-1, 2, 999])
def test_reader_rejects_out_of_range_page_indexes(
    text_pdf_path: Path, page_index: int
):
    with PyMuPDFReader(text_pdf_path) as reader:
        with pytest.raises(PDFPageIndexError):
            reader.get_page_text(page_index)


def test_reader_gets_all_page_text_without_reopening_pdf(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        all_text = reader.get_all_page_text()

    assert len(all_text) == 2
    assert "Chapter 1" in all_text[0]
    assert "Chapter 2" in all_text[1]


def test_reader_gets_structured_text_blocks(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        blocks = reader.get_page_text_blocks(0)

    assert blocks
    assert all(isinstance(block, TextBlock) for block in blocks)
    assert any("Chapter 1" in block.text for block in blocks)
    chapter_span = next(
        span
        for block in blocks
        for line in block.lines
        for span in line.spans
        if "Chapter 1" in span.text
    )
    assert chapter_span.bbox.x1 > chapter_span.bbox.x0
    assert chapter_span.bbox.y1 > chapter_span.bbox.y0
    assert chapter_span.font_size == pytest.approx(18.0)
    assert chapter_span.font_name


def test_reader_gets_page_size_with_zero_based_page_index(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        page_size = reader.get_page_size(0)

    assert page_size.width > 0
    assert page_size.height > 0


def test_reader_gets_outline_items_with_zero_based_page_indexes(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        outline = reader.get_outline()

    assert outline == [
        OutlineItem(title="Chapter 1", level=1, page_index=0),
        OutlineItem(title="Chapter 2", level=1, page_index=1),
    ]


def test_reader_detects_text_layer_when_any_page_has_text(text_pdf_path: Path):
    with PyMuPDFReader(text_pdf_path) as reader:
        assert reader.has_text_layer() is True


def test_reader_detects_missing_text_layer_for_image_only_pdf(
    image_only_pdf_path: Path,
):
    with PyMuPDFReader(image_only_pdf_path) as reader:
        assert reader.has_text_layer() is False


def test_reader_rejects_reads_after_close(text_pdf_path: Path):
    reader = PyMuPDFReader(text_pdf_path)
    reader.close()

    with pytest.raises(PDFClosedError):
        reader.get_page_text(0)


def test_reader_does_not_modify_original_pdf(text_pdf_path: Path):
    original_hash = hashlib.sha256(text_pdf_path.read_bytes()).hexdigest()

    with PyMuPDFReader(text_pdf_path) as reader:
        reader.page_count
        reader.get_page_text(0)
        reader.get_all_page_text()
        reader.get_page_text_blocks(0)
        reader.get_outline()
        reader.has_text_layer()

    final_hash = hashlib.sha256(text_pdf_path.read_bytes()).hexdigest()
    assert final_hash == original_hash
