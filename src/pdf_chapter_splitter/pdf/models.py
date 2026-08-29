"""Public PDF reading models.

These models intentionally avoid exposing PyMuPDF's raw dictionaries, tuples, or
document objects to higher-level business modules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageSize:
    """A PDF page size in PDF coordinate units."""

    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("width must be greater than 0")
        if self.height <= 0:
            raise ValueError("height must be greater than 0")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangular page area in PDF coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x1 < self.x0:
            raise ValueError("x1 must be greater than or equal to x0")
        if self.y1 < self.y0:
            raise ValueError("y1 must be greater than or equal to y0")


@dataclass(frozen=True, slots=True)
class TextSpan:
    """A span of text that usually shares one font style."""

    text: str
    bbox: BoundingBox
    font_size: float | None
    font_name: str | None
    block_index: int
    line_index: int
    span_index: int


@dataclass(frozen=True, slots=True)
class TextLine:
    """A line of text made of one or more spans."""

    bbox: BoundingBox
    block_index: int
    line_index: int
    spans: tuple[TextSpan, ...]

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass(frozen=True, slots=True)
class TextBlock:
    """A text block made of one or more lines."""

    bbox: BoundingBox
    block_index: int
    lines: tuple[TextLine, ...]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True, slots=True)
class OutlineItem:
    """A normalized PDF outline/bookmark entry."""

    title: str
    level: int
    page_index: int | None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if self.level < 1:
            raise ValueError("level must be 1 or greater")
        if self.page_index is not None and self.page_index < 0:
            raise ValueError("page_index must be 0 or greater when present")
