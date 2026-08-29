"""PyMuPDF-backed PDF split engine."""

from __future__ import annotations

from pathlib import Path
import warnings
import os

warnings.filterwarnings(
    "ignore",
    message="The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.",
)
os.environ.setdefault("PYMUPDF_MESSAGE", f"path:{os.devnull}")
os.environ.setdefault("PYMUPDF_LOG", f"path:{os.devnull}")
import fitz

from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf.errors import PDFOpenError, PDFPasswordError
from pdf_chapter_splitter.splitter.errors import (
    InvalidSegmentError,
    OutputFileError,
    PDFSplitError,
    SegmentOverlapError,
)
from pdf_chapter_splitter.splitter.filenames import (
    sanitize_pdf_filename,
    unique_output_path,
)
from pdf_chapter_splitter.splitter.models import SplitOutput, SplitResult


class PDFSplitter:
    """Create independent PDF files from validated split segments."""

    def split(
        self,
        input_path: str | Path,
        segments: list[SplitSegment] | tuple[SplitSegment, ...],
        output_directory: str | Path,
    ) -> SplitResult:
        """Split a PDF into independent files without modifying the source PDF."""

        normalized_input_path = Path(input_path)
        normalized_output_directory = Path(output_directory)
        normalized_segments = tuple(segments)

        self._prepare_output_directory(normalized_output_directory)

        try:
            source = fitz.open(normalized_input_path)
        except Exception as exc:
            raise PDFOpenError(f"Unable to open PDF: {normalized_input_path}") from exc

        try:
            if source.needs_pass:
                raise PDFPasswordError(f"PDF requires a password: {normalized_input_path}")

            self._validate_segments(normalized_segments, source.page_count)
            outputs = self._write_outputs(
                source=source,
                input_path=normalized_input_path,
                segments=normalized_segments,
                output_directory=normalized_output_directory,
            )
        finally:
            source.close()

        return SplitResult(
            input_path=normalized_input_path,
            output_directory=normalized_output_directory,
            outputs=tuple(outputs),
        )

    def _prepare_output_directory(self, output_directory: Path) -> None:
        if output_directory.exists() and not output_directory.is_dir():
            raise OutputFileError(f"Output path is not a directory: {output_directory}")
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise OutputFileError(f"Unable to create output directory: {output_directory}") from exc

    def _validate_segments(self, segments: tuple[SplitSegment, ...], page_count: int) -> None:
        if not segments:
            raise InvalidSegmentError("at least one split segment is required")

        previous_end = 0
        for index, segment in enumerate(segments):
            if segment.start_page_index < 0:
                raise InvalidSegmentError("segment start page must be 1 or greater")
            if segment.end_page_index <= segment.start_page_index:
                raise InvalidSegmentError("segment must contain at least one page")
            if segment.end_page_index > page_count:
                raise InvalidSegmentError(
                    f"segment '{segment.title}' ends after PDF page count {page_count}"
                )
            if index > 0 and segment.start_page_index < segments[index - 1].start_page_index:
                raise InvalidSegmentError("segments must be sorted by start page")
            if index > 0 and segment.start_page_index < previous_end:
                raise SegmentOverlapError(f"segment '{segment.title}' overlaps a previous segment")
            previous_end = segment.end_page_index

    def _write_outputs(
        self,
        source: fitz.Document,
        input_path: Path,
        segments: tuple[SplitSegment, ...],
        output_directory: Path,
    ) -> list[SplitOutput]:
        outputs: list[SplitOutput] = []
        reserved_paths: set[Path] = set()

        for segment in segments:
            output_path = unique_output_path(
                output_directory=output_directory,
                filename=sanitize_pdf_filename(segment.title),
                reserved_paths=reserved_paths,
            )
            if output_path.resolve() == input_path.resolve():
                raise OutputFileError("output path cannot overwrite the input PDF")
            self._write_segment(source, segment, output_path)
            outputs.append(SplitOutput(segment=segment, output_path=output_path))

        return outputs

    def _write_segment(
        self,
        source: fitz.Document,
        segment: SplitSegment,
        output_path: Path,
    ) -> None:
        output = fitz.open()
        try:
            output.insert_pdf(
                source,
                from_page=segment.start_page_index,
                to_page=segment.end_page_index - 1,
            )
            output.save(output_path)
        except Exception as exc:
            raise PDFSplitError(f"Unable to write output PDF: {output_path}") from exc
        finally:
            output.close()
