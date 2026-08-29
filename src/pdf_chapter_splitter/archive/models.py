"""Public archive models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ZipResult:
    """Summary of a completed ZIP creation operation."""

    input_files: tuple[Path, ...]
    output_zip_path: Path
