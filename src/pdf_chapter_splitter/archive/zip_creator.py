"""ZIP archive creator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pdf_chapter_splitter.archive.errors import ArchiveInputError, ArchiveOutputError
from pdf_chapter_splitter.archive.filenames import unique_zip_output_path
from pdf_chapter_splitter.archive.models import ZipResult
from pdf_chapter_splitter.splitter.models import SplitResult


class ZipCreator:
    """Create ZIP archives from split PDF outputs."""

    def create(
        self,
        split_result: SplitResult | list[Path] | tuple[Path, ...],
        output_zip_path: str | Path,
    ) -> ZipResult:
        """Create a ZIP file from split PDFs or a list of PDF paths."""

        input_files = self._normalize_input_files(split_result)
        reserved_paths: set[Path] = set()
        final_zip_path = unique_zip_output_path(output_zip_path, reserved_paths)
        final_zip_path.parent.mkdir(parents=True, exist_ok=True)
        if final_zip_path.exists():
            raise ArchiveOutputError(f"ZIP file already exists: {final_zip_path}")

        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=final_zip_path.parent,
            suffix=".tmp",
        ) as temp_file:
            temp_zip_path = Path(temp_file.name)

        try:
            with ZipFile(temp_zip_path, "w", compression=ZIP_DEFLATED) as archive:
                for input_file in input_files:
                    archive.write(input_file, arcname=input_file.name)
            shutil.move(str(temp_zip_path), final_zip_path)
        except Exception as exc:
            if temp_zip_path.exists():
                temp_zip_path.unlink(missing_ok=True)
            raise ArchiveOutputError(f"Unable to create ZIP: {final_zip_path}") from exc

        return ZipResult(input_files=input_files, output_zip_path=final_zip_path)

    def _normalize_input_files(
        self,
        split_result: SplitResult | list[Path] | tuple[Path, ...],
    ) -> tuple[Path, ...]:
        if isinstance(split_result, SplitResult):
            files = tuple(output.output_path for output in split_result.outputs)
        else:
            files = tuple(Path(path) for path in split_result)

        if not files:
            raise ArchiveInputError("at least one input file is required")

        normalized_files: list[Path] = []
        for file_path in files:
            if not file_path.exists():
                raise ArchiveInputError(f"Input file does not exist: {file_path}")
            if not file_path.is_file():
                raise ArchiveInputError(f"Input path is not a file: {file_path}")
            normalized_files.append(file_path)
        return tuple(normalized_files)
