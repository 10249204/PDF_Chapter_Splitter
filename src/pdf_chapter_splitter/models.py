"""Shared domain models.

Internal page indexes are always 0-based. Presentation layers can use the
1-based GUI helpers when they need user-facing page numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdf_chapter_splitter.chapters.models import Chapter


@dataclass(frozen=True, slots=True)
class SplitSegment:
    """A half-open PDF page range planned for one output file."""

    title: str
    start_page_index: int
    end_page_index: int

    @classmethod
    def from_page_numbers(
        cls,
        title: str,
        start_page_number: int,
        end_page_number: int,
    ) -> "SplitSegment":
        """Create a segment from user-facing 1-based inclusive page numbers."""

        if start_page_number < 1:
            raise ValueError("start_page_number must be 1 or greater")
        if end_page_number < start_page_number:
            raise ValueError("end_page_number must be greater than or equal to start_page_number")
        return cls(
            title=title,
            start_page_index=start_page_number - 1,
            end_page_index=end_page_number,
        )

    def __post_init__(self) -> None:
        _validate_title(self.title)
        if self.start_page_index < 0:
            raise ValueError("start_page_index must be 0 or greater")
        if self.end_page_index <= self.start_page_index:
            raise ValueError("end_page_index must be greater than start_page_index")

    @property
    def page_count(self) -> int:
        return self.end_page_index - self.start_page_index

    @property
    def gui_start_page_number(self) -> int:
        return self.start_page_index + 1

    @property
    def gui_end_page_number(self) -> int:
        return self.end_page_index


def _validate_title(title: str) -> None:
    if not title.strip():
        raise ValueError("title must not be blank")


__all__ = ["Chapter", "SplitSegment"]
