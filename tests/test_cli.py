from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from pdf_chapter_splitter.pdf import PyMuPDFReader


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pdf_chapter_splitter.cli", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_splits_pdf_with_multiple_segments(five_page_pdf_path: Path, tmp_path: Path):
    output_directory = tmp_path / "out"

    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--output",
        str(output_directory),
        "--segment",
        "Part1=1-2",
        "--segment",
        "Part2=3-5",
    )

    assert completed.returncode == 0
    assert (output_directory / "Part1.pdf").exists()
    assert (output_directory / "Part2.pdf").exists()
    with PyMuPDFReader(output_directory / "Part2.pdf") as reader:
        assert reader.page_count == 3
        assert "Page 3" in reader.get_page_text(0)


def test_cli_creates_zip_when_requested(five_page_pdf_path: Path, tmp_path: Path):
    output_directory = tmp_path / "out"

    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--output",
        str(output_directory),
        "--segment",
        "Part1=1-2",
        "--segment",
        "Part2=3-5",
        "--zip",
    )

    assert completed.returncode == 0
    assert (output_directory / "five-pages.zip").exists()
    with ZipFile(output_directory / "five-pages.zip") as archive:
        assert archive.namelist() == ["Part1.pdf", "Part2.pdf"]


def test_cli_requires_at_least_one_segment(five_page_pdf_path: Path, tmp_path: Path):
    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--output",
        str(tmp_path / "out"),
    )

    assert completed.returncode != 0
    assert "Error:" in completed.stderr
    assert "At least one --segment is required." in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_invalid_page_range(five_page_pdf_path: Path, tmp_path: Path):
    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--output",
        str(tmp_path / "out"),
        "--segment",
        "Part1=0-5",
    )

    assert completed.returncode != 0
    assert 'Invalid page range "0-5".' in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_overlapping_segments(five_page_pdf_path: Path, tmp_path: Path):
    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--output",
        str(tmp_path / "out"),
        "--segment",
        "Part1=1-3",
        "--segment",
        "Part2=3-5",
    )

    assert completed.returncode != 0
    assert "overlaps" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_missing_pdf(tmp_path: Path):
    completed = run_cli(
        "split",
        str(tmp_path / "missing.pdf"),
        "--segment",
        "Part1=1-2",
    )

    assert completed.returncode != 0
    assert "Unable to open PDF" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_uses_default_output_directory(five_page_pdf_path: Path):
    completed = run_cli(
        "split",
        str(five_page_pdf_path),
        "--segment",
        "Part1=1-2",
    )

    output_directory = five_page_pdf_path.with_name("five-pages_split")
    assert completed.returncode == 0
    assert (output_directory / "Part1.pdf").exists()


def test_cli_does_not_overwrite_existing_output_files(
    five_page_pdf_path: Path, tmp_path: Path
):
    output_directory = tmp_path / "out"
    args = (
        "split",
        str(five_page_pdf_path),
        "--output",
        str(output_directory),
        "--segment",
        "Part 1=1-1",
    )

    first = run_cli(*args)
    second = run_cli(*args)

    assert first.returncode == 0
    assert second.returncode == 0
    assert (output_directory / "Part 1.pdf").exists()
    assert (output_directory / "Part 1 (2).pdf").exists()
