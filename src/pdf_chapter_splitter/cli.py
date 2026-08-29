"""Command line interface for PDF Chapter Splitter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf_chapter_splitter.archive import ArchiveError, ZipCreator
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFOpenError, PDFPasswordError, PyMuPDFReader
from pdf_chapter_splitter.splitter import PDFSplitter
from pdf_chapter_splitter.splitter.errors import InvalidSegmentError, OutputFileError, PDFSplitError


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "split":
            return _run_split(args)
        parser.error("a command is required")
    except (PDFOpenError, PDFPasswordError, InvalidSegmentError, OutputFileError, PDFSplitError, ArchiveError) as exc:
        print("Error:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-chapter-splitter")
    subparsers = parser.add_subparsers(dest="command")

    split_parser = subparsers.add_parser("split", help="Split a PDF into multiple PDF files")
    split_parser.add_argument("input_pdf", type=Path)
    split_parser.add_argument("--output", type=Path)
    split_parser.add_argument("--segment", action="append", default=[])
    split_parser.add_argument("--zip", action="store_true")
    return parser


def _run_split(args: argparse.Namespace) -> int:
    if not args.segment:
        raise InvalidSegmentError("At least one --segment is required.")

    input_pdf: Path = args.input_pdf
    output_directory = args.output or input_pdf.with_name(f"{input_pdf.stem}_split")

    segments = tuple(_parse_segment(segment_text) for segment_text in args.segment)

    with PyMuPDFReader(input_pdf) as reader:
        page_count = reader.page_count

    print("PDF Chapter Splitter")
    print(f"\nInput:\n  {input_pdf}")

    splitter = PDFSplitter()
    split_result = splitter.split(input_pdf, segments, output_directory)

    print(f"\nPages:\n  {page_count}")
    print("\nSegments:")
    for output in split_result.outputs:
        segment = output.segment
        print(
            f"  {segment.title:<12} {segment.gui_start_page_number}-{segment.gui_end_page_number}"
        )

    print("\nSplitting...")
    for output in split_result.outputs:
        print(f"  OK {output.output_path.name}")

    if args.zip:
        print("\nCreating ZIP...")
        zip_path = output_directory / f"{input_pdf.stem}.zip"
        zip_result = ZipCreator().create(split_result, zip_path)
        print(f"  OK {zip_result.output_zip_path.name}")

    print("\nDone.")
    print(f"\nOutput:\n  {output_directory}")
    return 0


def _parse_segment(segment_text: str) -> SplitSegment:
    if "=" not in segment_text:
        raise InvalidSegmentError(f'Invalid segment "{segment_text}". Expected Title=1-5.')
    title, page_range = segment_text.split("=", 1)
    if "-" not in page_range:
        raise InvalidSegmentError(f'Invalid page range "{page_range}".')
    start_text, end_text = page_range.split("-", 1)
    try:
        start_page = int(start_text)
        end_page = int(end_text)
    except ValueError as exc:
        raise InvalidSegmentError(f'Invalid page range "{page_range}".') from exc
    if start_page < 1:
        raise InvalidSegmentError(f'Invalid page range "{page_range}". Page numbers must start from 1.')
    return SplitSegment.from_page_numbers(title=title.strip(), start_page_number=start_page, end_page_number=end_page)


if __name__ == "__main__":
    raise SystemExit(main())
