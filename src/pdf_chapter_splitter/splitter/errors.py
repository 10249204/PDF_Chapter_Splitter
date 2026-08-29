"""PDF split engine exception hierarchy."""

from __future__ import annotations


class PDFSplitError(Exception):
    """Base error for PDF splitting operations."""


class InvalidSegmentError(PDFSplitError):
    """Raised when a split segment is invalid for the input PDF."""


class SegmentOverlapError(InvalidSegmentError):
    """Raised when split segments overlap each other."""


class OutputFileError(PDFSplitError):
    """Raised when an output file or directory cannot be prepared."""
