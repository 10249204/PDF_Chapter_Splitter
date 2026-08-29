"""Archive-related exception hierarchy."""

from __future__ import annotations


class ArchiveError(Exception):
    """Base error for archive operations."""


class ArchiveInputError(ArchiveError):
    """Raised when archive input is missing or invalid."""


class ArchiveOutputError(ArchiveError):
    """Raised when archive output cannot be created safely."""
