"""PyMuPDF-backed PDF reader implementation."""

from __future__ import annotations

import math
import os
import warnings
from pathlib import Path
from types import TracebackType
from typing import Any, Self

warnings.filterwarnings(
    "ignore",
    message="The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.",
)
os.environ.setdefault("PYMUPDF_MESSAGE", f"path:{os.devnull}")
os.environ.setdefault("PYMUPDF_LOG", f"path:{os.devnull}")
import fitz

from pdf_chapter_splitter.pdf.errors import (
    PDFClosedError,
    PDFOpenError,
    PDFPageIndexError,
    PDFPasswordError,
    PDFReaderError,
)
from pdf_chapter_splitter.pdf.models import (
    BoundingBox,
    OutlineItem,
    PageSize,
    TextBlock,
    TextLine,
    TextSpan,
)
from pdf_chapter_splitter.pdf.reader import PDFReader


class PyMuPDFReader(PDFReader):
    """Read PDF metadata, text, text layout, and outline with PyMuPDF."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._document: fitz.Document | None = None
        self._open()

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        document = self._ensure_open()
        return document.page_count

    def get_page_text(self, page_index: int) -> str:
        page = self._load_page(page_index)
        return page.get_text("text")

    def get_all_page_text(self) -> list[str]:
        self._ensure_open()
        return [self.get_page_text(page_index) for page_index in range(self.page_count)]

    def get_page_text_blocks(self, page_index: int) -> list[TextBlock]:
        page = self._load_page(page_index)
        raw_text = page.get_text("dict")
        blocks: list[TextBlock] = []

        for raw_block in raw_text.get("blocks", []):
            if raw_block.get("type") != 0:
                continue
            block_index = int(raw_block.get("number", len(blocks)))
            lines = self._parse_lines(raw_block.get("lines", []), block_index)
            blocks.append(
                TextBlock(
                    bbox=_bbox_from_raw(raw_block["bbox"]),
                    block_index=block_index,
                    lines=tuple(lines),
                )
            )

        return blocks

    def get_page_size(self, page_index: int) -> PageSize:
        page = self._load_page(page_index)
        return PageSize(width=float(page.rect.width), height=float(page.rect.height))

    def get_outline(self) -> list[OutlineItem]:
        document = self._ensure_open()
        outline: list[OutlineItem] = []

        for level, title, page_number in document.get_toc(simple=True):
            page_index = page_number - 1 if page_number > 0 else None
            outline.append(
                OutlineItem(
                    title=str(title),
                    level=int(level),
                    page_index=page_index,
                )
            )

        return outline

    def has_text_layer(self) -> bool:
        self._ensure_open()
        return any(self.get_page_text(page_index).strip() for page_index in range(self.page_count))

    def get_metadata(self) -> dict[str, str]:
        document = self._ensure_open()
        metadata: dict[str, str] = {}
        for key, value in document.metadata.items():
            if value is not None:
                metadata[str(key)] = str(value)
        return metadata

    def close(self) -> None:
        if self._document is not None:
            self._document.close()
            self._document = None

    def _open(self) -> None:
        if not self._path.exists():
            raise PDFOpenError(f"Unable to open PDF: {self._path}")
        if not self._path.is_file():
            raise PDFOpenError(f"Unable to open PDF: {self._path}")

        try:
            document = fitz.open(self._path)
        except Exception as exc:
            raise PDFOpenError(f"Unable to open PDF: {self._path}") from exc

        if document.needs_pass:
            document.close()
            raise PDFPasswordError(f"PDF requires a password: {self._path}")

        self._document = document

    def _ensure_open(self) -> fitz.Document:
        if self._document is None:
            raise PDFClosedError("PDF reader is closed")
        return self._document

    def _validate_page_index(self, page_index: int) -> None:
        if not isinstance(page_index, int):
            raise PDFPageIndexError("page_index must be an integer")
        if page_index < 0 or page_index >= self.page_count:
            raise PDFPageIndexError(
                f"page_index {page_index} is outside valid range 0..{self.page_count - 1}"
            )

    def _load_page(self, page_index: int) -> fitz.Page:
        document = self._ensure_open()
        self._validate_page_index(page_index)
        try:
            return document.load_page(page_index)
        except Exception as exc:
            raise PDFReaderError(f"Unable to load page {page_index}") from exc

    def _parse_lines(self, raw_lines: list[dict[str, Any]], block_index: int) -> list[TextLine]:
        lines: list[TextLine] = []
        for line_index, raw_line in enumerate(raw_lines):
            spans = self._parse_spans(raw_line.get("spans", []), block_index, line_index)
            lines.append(
                TextLine(
                    bbox=_bbox_from_raw(raw_line["bbox"]),
                    block_index=block_index,
                    line_index=line_index,
                    spans=tuple(spans),
                )
            )
        return lines

    def _parse_spans(
        self,
        raw_spans: list[dict[str, Any]],
        block_index: int,
        line_index: int,
    ) -> list[TextSpan]:
        spans: list[TextSpan] = []
        for span_index, raw_span in enumerate(raw_spans):
            spans.append(
                TextSpan(
                    text=str(raw_span.get("text", "")),
                    bbox=_bbox_from_raw(raw_span["bbox"]),
                    font_size=_float_or_none(raw_span.get("size")),
                    font_name=_str_or_none(raw_span.get("font")),
                    block_index=block_index,
                    line_index=line_index,
                    span_index=span_index,
                )
            )
        return spans


def _bbox_from_raw(raw_bbox: Any) -> BoundingBox:
    try:
        values = tuple(raw_bbox)
    except TypeError as exc:
        raise PDFReaderError("Invalid text bounding box: expected four coordinates") from exc

    if len(values) != 4:
        raise PDFReaderError("Invalid text bounding box: expected four coordinates")

    coordinates: list[float] = []
    for value in values:
        try:
            coordinate = float(value)
        except (TypeError, ValueError) as exc:
            raise PDFReaderError("Invalid text bounding box: coordinates must be numeric") from exc
        if not math.isfinite(coordinate):
            raise PDFReaderError("Invalid text bounding box: coordinates must be finite")
        coordinates.append(coordinate)

    x0, y0, x1, y1 = coordinates
    return BoundingBox(
        x0=min(x0, x1),
        y0=min(y0, y1),
        x1=max(x0, x1),
        y1=max(y0, y1),
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
