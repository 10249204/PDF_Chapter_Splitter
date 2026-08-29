from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from pdf_chapter_splitter.archive import ArchiveInputError, ZipCreator
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.splitter import PDFSplitter


def segment(title: str, start_page_number: int, end_page_number: int) -> SplitSegment:
    return SplitSegment.from_page_numbers(
        title=title,
        start_page_number=start_page_number,
        end_page_number=end_page_number,
    )


def split_sample_pdf(five_page_pdf_path: Path, output_directory: Path):
    return PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[
            segment("Part 1", 1, 2),
            segment("Part 2", 3, 4),
            segment("Part 3", 5, 5),
        ],
        output_directory=output_directory,
    )


def test_zip_creator_creates_single_file_zip(five_page_pdf_path: Path, tmp_path: Path):
    split_result = PDFSplitter().split(
        input_path=five_page_pdf_path,
        segments=[segment("Part 1", 1, 2)],
        output_directory=tmp_path / "split",
    )

    zip_result = ZipCreator().create(split_result, tmp_path / "book.zip")

    assert zip_result.output_zip_path.name == "book.zip"
    with ZipFile(zip_result.output_zip_path) as archive:
        assert archive.namelist() == ["Part 1.pdf"]


def test_zip_creator_creates_multi_file_zip_with_split_output_names(
    five_page_pdf_path: Path, tmp_path: Path
):
    split_result = split_sample_pdf(five_page_pdf_path, tmp_path / "split")

    zip_result = ZipCreator().create(split_result, tmp_path / "book.zip")

    with ZipFile(zip_result.output_zip_path) as archive:
        assert archive.namelist() == ["Part 1.pdf", "Part 2.pdf", "Part 3.pdf"]


def test_zip_creator_writes_readable_pdf_content(five_page_pdf_path: Path, tmp_path: Path):
    split_result = split_sample_pdf(five_page_pdf_path, tmp_path / "split")

    zip_result = ZipCreator().create(split_result, tmp_path / "book.zip")

    extract_directory = tmp_path / "extracted"
    with ZipFile(zip_result.output_zip_path) as archive:
        archive.extractall(extract_directory)

    assert (extract_directory / "Part 1.pdf").read_bytes().startswith(b"%PDF")
    assert (extract_directory / "Part 2.pdf").read_bytes().startswith(b"%PDF")
    assert (extract_directory / "Part 3.pdf").read_bytes().startswith(b"%PDF")


def test_zip_creator_does_not_store_absolute_paths(
    five_page_pdf_path: Path, tmp_path: Path
):
    split_result = split_sample_pdf(five_page_pdf_path, tmp_path / "split")

    zip_result = ZipCreator().create(split_result, tmp_path / "book.zip")

    with ZipFile(zip_result.output_zip_path) as archive:
        for name in archive.namelist():
            assert ":" not in name
            assert "\\" not in name
            assert "/" not in name


def test_zip_creator_does_not_overwrite_existing_zip(
    five_page_pdf_path: Path, tmp_path: Path
):
    split_result = split_sample_pdf(five_page_pdf_path, tmp_path / "split")
    creator = ZipCreator()

    first = creator.create(split_result, tmp_path / "book.zip")
    second = creator.create(split_result, tmp_path / "book.zip")

    assert first.output_zip_path.name == "book.zip"
    assert second.output_zip_path.name == "book (2).zip"
    assert first.output_zip_path.exists()
    assert second.output_zip_path.exists()


def test_zip_creator_rejects_missing_input_file(tmp_path: Path):
    with pytest.raises(ArchiveInputError):
        ZipCreator().create([tmp_path / "missing.pdf"], tmp_path / "book.zip")


def test_zip_creator_rejects_empty_input(tmp_path: Path):
    with pytest.raises(ArchiveInputError):
        ZipCreator().create([], tmp_path / "book.zip")


def test_zip_creator_cleans_temporary_file_after_failure(
    five_page_pdf_path: Path, tmp_path: Path
):
    split_result = split_sample_pdf(five_page_pdf_path, tmp_path / "split")
    output_directory_as_file = tmp_path / "not-a-directory"
    output_directory_as_file.write_text("blocked", encoding="utf-8")

    with pytest.raises(Exception):
        ZipCreator().create(split_result, output_directory_as_file / "book.zip")

    assert not list(tmp_path.glob("*.tmp"))
