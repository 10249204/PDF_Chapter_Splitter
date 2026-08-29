"""Public models returned by the PDF splitter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdf_chapter_splitter.models import SplitSegment


@dataclass(frozen=True, slots=True)
class SplitOutput:
    """One PDF output file and the segment used to create it."""

    segment: SplitSegment
    output_path: Path


@dataclass(frozen=True, slots=True)
class SplitResult:
    """Summary of a completed PDF split operation."""

    input_path: Path
    output_directory: Path
    outputs: tuple[SplitOutput, ...]
