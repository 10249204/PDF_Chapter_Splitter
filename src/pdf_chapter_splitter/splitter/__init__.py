"""PDF split engine boundaries."""

from pdf_chapter_splitter.splitter.errors import (
    InvalidSegmentError,
    OutputFileError,
    PDFSplitError,
    SegmentOverlapError,
)
from pdf_chapter_splitter.splitter.models import SplitOutput, SplitResult
from pdf_chapter_splitter.splitter.pdf_splitter import PDFSplitter

__all__ = [
    "InvalidSegmentError",
    "OutputFileError",
    "PDFSplitError",
    "PDFSplitter",
    "SegmentOverlapError",
    "SplitOutput",
    "SplitResult",
]
