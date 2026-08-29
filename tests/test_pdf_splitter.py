from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PyMuPDFReader
from pdf_chapter_splitter.splitter import PDFSplitter
from pdf_chapter_splitter.splitter.errors import (
    InvalidSegmentError,
    OutputFileError,
    SegmentOverlapError,
)


def segment(title: str, start_page_number: int, end_page_number: int) -> SplitSegment:
    return SplitSegment.from_page_numbers(
        title=title,
        start_page_number=start_page_number,
        end_page_number=end_page_number,
    )


def read_output_text(path: Path) -> list[str]:
    with PyMuPDFReader(path) as reader:
        return reader.get_all_page_text()


def test_split_segment_from_page_numbers_converts_once_to_zero_based_range():
    converted = segment("Part 1", 1, 5)

    assert converted.start_page_index == 0
    assert converted.end_page_index == 5
    assert converted.gui_start_page_number == 1
    assert converted.gui_end_page_number == 5


def test_splitter_creates_single_output_pdf_with_all_pages(
    five_page_pdf_path: Path, tmp_path: Path
):
    output_directory = tmp_path / "output"

    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[segment("All Pages", 1, 5)],
        output_directory=output_directory,
    )

    assert result.input_path == five_page_pdf_path
    assert len(result.outputs) == 1
    assert result.outputs[0].segment == segment("All Pages", 1, 5)
    assert result.outputs[0].output_path.name == "All Pages.pdf"

    with PyMuPDFReader(result.outputs[0].output_path) as reader:
        assert reader.page_count == 5


def test_splitter_creates_multiple_output_pdfs_with_correct_page_counts(
    five_page_pdf_path: Path, tmp_path: Path
):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[
            segment("Part 1", 1, 2),
            segment("Part 2", 3, 4),
            segment("Part 3", 5, 5),
        ],
        output_directory=tmp_path / "output",
    )

    page_counts = []
    for output in result.outputs:
        with PyMuPDFReader(output.output_path) as reader:
            page_counts.append(reader.page_count)

    assert page_counts == [2, 2, 1]


def test_splitter_preserves_expected_page_content(
    five_page_pdf_path: Path, tmp_path: Path
):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[
            segment("Part 1", 1, 2),
            segment("Part 2", 3, 4),
        ],
        output_directory=tmp_path / "output",
    )

    assert read_output_text(result.outputs[0].output_path) == [
        "Page 1\n",
        "Page 2\n",
    ]
    assert read_output_text(result.outputs[1].output_path) == [
        "Page 3\n",
        "Page 4\n",
    ]


def test_splitter_creates_single_page_output_pdf(
    five_page_pdf_path: Path, tmp_path: Path
):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[segment("Single Page", 3, 3)],
        output_directory=tmp_path / "output",
    )

    with PyMuPDFReader(result.outputs[0].output_path) as reader:
        assert reader.page_count == 1
        assert "Page 3" in reader.get_page_text(0)


@pytest.mark.parametrize(
    ("start_page_number", "end_page_number"),
    [
        (4, 2),
        (0, 2),
        (-1, 2),
    ],
)
def test_split_segment_rejects_invalid_user_page_numbers(
    start_page_number: int, end_page_number: int
):
    with pytest.raises(ValueError):
        segment("Invalid", start_page_number, end_page_number)


def test_splitter_rejects_segment_past_pdf_page_count(
    five_page_pdf_path: Path, tmp_path: Path
):
    with pytest.raises(InvalidSegmentError):
        PDFSplitter().split(
            input_path=five_page_pdf_path,
            segments=[segment("Too Long", 1, 10)],
            output_directory=tmp_path / "output",
        )


def test_splitter_rejects_overlapping_segments(
    five_page_pdf_path: Path, tmp_path: Path
):
    with pytest.raises(SegmentOverlapError):
        PDFSplitter().split(
            input_path=five_page_pdf_path,
            segments=[
                segment("Part 1", 1, 3),
                segment("Part 2", 3, 5),
            ],
            output_directory=tmp_path / "output",
        )


def test_splitter_rejects_unsorted_segments(five_page_pdf_path: Path, tmp_path: Path):
    with pytest.raises(InvalidSegmentError):
        PDFSplitter().split(
            input_path=five_page_pdf_path,
            segments=[
                segment("Part 2", 4, 5),
                segment("Part 1", 1, 3),
            ],
            output_directory=tmp_path / "output",
        )


def test_splitter_allows_gaps_between_segments(five_page_pdf_path: Path, tmp_path: Path):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[
            segment("Part 1", 1, 2),
            segment("Part 2", 4, 5),
        ],
        output_directory=tmp_path / "output",
    )

    assert read_output_text(result.outputs[0].output_path) == ["Page 1\n", "Page 2\n"]
    assert read_output_text(result.outputs[1].output_path) == ["Page 4\n", "Page 5\n"]


def test_splitter_sanitizes_windows_unsafe_file_names(
    five_page_pdf_path: Path, tmp_path: Path
):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[segment('第1章：C/C++？"<>|*', 1, 1)],
        output_directory=tmp_path / "output",
    )

    assert result.outputs[0].output_path.name == "第1章_C_C++______.pdf"
    assert result.outputs[0].output_path.exists()


def test_splitter_does_not_silently_overwrite_existing_output(
    five_page_pdf_path: Path, tmp_path: Path
):
    splitter = PDFSplitter()
    output_directory = tmp_path / "output"
    segments = [segment("Part 1", 1, 1)]

    first_result = splitter.split(five_page_pdf_path, segments, output_directory)
    second_result = splitter.split(five_page_pdf_path, segments, output_directory)

    assert first_result.outputs[0].output_path.name == "Part 1.pdf"
    assert second_result.outputs[0].output_path.name == "Part 1 (2).pdf"
    assert first_result.outputs[0].output_path.exists()
    assert second_result.outputs[0].output_path.exists()


def test_splitter_handles_name_conflicts_within_one_run(
    five_page_pdf_path: Path, tmp_path: Path
):
    result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[
            segment("Part", 1, 1),
            segment("Part", 2, 2),
        ],
        output_directory=tmp_path / "output",
    )

    assert [output.output_path.name for output in result.outputs] == [
        "Part.pdf",
        "Part (2).pdf",
    ]


def test_splitter_does_not_modify_original_pdf(five_page_pdf_path: Path, tmp_path: Path):
    original_hash = hashlib.sha256(five_page_pdf_path.read_bytes()).hexdigest()

    PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[segment("Part", 1, 2)],
        output_directory=tmp_path / "output",
    )

    final_hash = hashlib.sha256(five_page_pdf_path.read_bytes()).hexdigest()
    assert final_hash == original_hash


def test_splitter_rejects_output_directory_when_path_is_file(
    five_page_pdf_path: Path, tmp_path: Path
):
    output_path = tmp_path / "not-a-directory"
    output_path.write_text("already a file", encoding="utf-8")

    with pytest.raises(OutputFileError):
        PDFSplitter().split(
            input_path=five_page_pdf_path,
            segments=[segment("Part", 1, 1)],
            output_directory=output_path,
        )
