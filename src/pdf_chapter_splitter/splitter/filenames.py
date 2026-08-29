"""Filename helpers for PDF outputs."""

from __future__ import annotations

from pathlib import Path

from pdf_chapter_splitter.splitter.errors import OutputFileError

WINDOWS_UNSAFE_FILENAME_CHARS = frozenset('\\/:*?"<>|：？')


def sanitize_pdf_filename(title: str) -> str:
    """Return a Windows-safe PDF filename derived from a segment title."""

    sanitized = "".join("_" if char in WINDOWS_UNSAFE_FILENAME_CHARS else char for char in title)
    sanitized = sanitized.strip().strip(".")
    if not sanitized:
        raise OutputFileError("segment title cannot produce a valid output filename")
    return f"{sanitized}.pdf"


def unique_output_path(output_directory: Path, filename: str, reserved_paths: set[Path]) -> Path:
    """Return a non-overwriting output path, adding numeric suffixes as needed."""

    candidate = output_directory / filename
    if _path_is_available(candidate, reserved_paths):
        reserved_paths.add(candidate)
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = output_directory / f"{stem} ({counter}){suffix}"
        if _path_is_available(candidate, reserved_paths):
            reserved_paths.add(candidate)
            return candidate
        counter += 1


def _path_is_available(path: Path, reserved_paths: set[Path]) -> bool:
    return path not in reserved_paths and not path.exists()
