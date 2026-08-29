"""PDF reader exception hierarchy."""

from __future__ import annotations


class PDFReaderError(Exception):
    """Base error for PDF reader operations."""


class PDFOpenError(PDFReaderError):
    """Raised when a PDF path cannot be opened as a readable PDF file."""


class PDFPasswordError(PDFOpenError):
    """Raised when a PDF requires a password before it can be read."""


class PDFPageIndexError(PDFReaderError, IndexError):
    """Raised when a 0-based page index is outside the PDF page range."""


class PDFClosedError(PDFReaderError):
    """Raised when reading is attempted after the PDF reader is closed."""
