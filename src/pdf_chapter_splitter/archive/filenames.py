"""Filename helpers for archive outputs."""

from __future__ import annotations

from pathlib import Path

from pdf_chapter_splitter.splitter.filenames import unique_output_path


def unique_zip_output_path(output_zip_path: str | Path, reserved_paths: set[Path]) -> Path:
    """Return a non-overwriting ZIP path using the shared suffix policy."""

    path = Path(output_zip_path)
    return unique_output_path(path.parent, path.name, reserved_paths)
