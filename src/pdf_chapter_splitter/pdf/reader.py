"""Abstract PDF reader contract.

Concrete readers should use PyMuPDF for PDF access, but Phase 1 intentionally
does not include an implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from pdf_chapter_splitter.pdf.models import OutlineItem, PageSize, TextBlock


class PDFReader(ABC):
    """Read-only interface for PDF metadata, page count, and page text."""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    @abstractmethod
    def page_count(self) -> int:
        """Return the number of pages in the PDF."""

    @abstractmethod
    def get_page_text(self, page_index: int) -> str:
        """Return text for a 0-based page index."""

    @abstractmethod
    def get_all_page_text(self) -> list[str]:
        """Return text for all pages without reopening the PDF."""

    @abstractmethod
    def get_page_text_blocks(self, page_index: int) -> list[TextBlock]:
        """Return structured text blocks for a 0-based page index."""

    @abstractmethod
    def get_page_size(self, page_index: int) -> PageSize:
        """Return page width and height for a 0-based page index."""

    @abstractmethod
    def get_outline(self) -> list[OutlineItem]:
        """Return normalized PDF outline/bookmark entries."""

    @abstractmethod
    def has_text_layer(self) -> bool:
        """Return whether at least one page has non-blank extractable text."""

    @abstractmethod
    def get_metadata(self) -> dict[str, str]:
        """Return PDF metadata as string key-value pairs."""

    @abstractmethod
    def close(self) -> None:
        """Release any underlying PDF resources."""
