"""Deterministic chapter-to-segment boundary resolution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pdf_chapter_splitter.chapters.models import Chapter

if TYPE_CHECKING:
    from pdf_chapter_splitter.models import SplitSegment


@dataclass(frozen=True, slots=True)
class BoundaryResolution:
    """One confirmed chapter and its resolved split segment."""

    chapter: Chapter
    segment: SplitSegment


@dataclass(frozen=True, slots=True)
class BoundaryResolutionResult:
    """Resolved split segments with their source chapters."""

    resolutions: tuple[BoundaryResolution, ...]

    @property
    def segments(self) -> tuple[SplitSegment, ...]:
        return tuple(resolution.segment for resolution in self.resolutions)

    @property
    def source_chapters(self) -> tuple[Chapter, ...]:
        return tuple(resolution.chapter for resolution in self.resolutions)


class ChapterBoundaryResolver:
    """Resolve confirmed chapter starts into half-open split segments."""

    def resolve(
        self,
        chapters: Iterable[Chapter],
        page_count: int,
    ) -> BoundaryResolutionResult:
        """Resolve chapters into SplitSegment ranges using PDF physical pages."""

        from pdf_chapter_splitter.models import SplitSegment

        _validate_page_count(page_count)
        sorted_chapters = _validate_and_sort_chapters(chapters, page_count)
        if not sorted_chapters:
            return BoundaryResolutionResult(resolutions=())

        resolutions: list[BoundaryResolution] = []
        for index, chapter in enumerate(sorted_chapters):
            end_page_index = (
                sorted_chapters[index + 1].start_page_index
                if index + 1 < len(sorted_chapters)
                else page_count
            )
            segment = SplitSegment(
                title=chapter.title,
                start_page_index=chapter.start_page_index,
                end_page_index=end_page_index,
            )
            resolutions.append(BoundaryResolution(chapter=chapter, segment=segment))

        return BoundaryResolutionResult(resolutions=tuple(resolutions))


def _validate_page_count(page_count: int) -> None:
    if not isinstance(page_count, int):
        raise ValueError("page_count must be an integer")
    if page_count <= 0:
        raise ValueError("page_count must be greater than 0")


def _validate_and_sort_chapters(
    chapters: Iterable[Chapter],
    page_count: int,
) -> tuple[Chapter, ...]:
    normalized_chapters = tuple(chapters)
    seen_start_pages: set[int] = set()

    for chapter in normalized_chapters:
        if not isinstance(chapter, Chapter):
            raise ValueError("chapters must contain Chapter items")
        chapter.validate(page_count=page_count)
        if chapter.start_page_index in seen_start_pages:
            raise ValueError("chapter start_page_index values must be unique")
        seen_start_pages.add(chapter.start_page_index)

    return tuple(
        sorted(
            normalized_chapters,
            key=lambda chapter: (chapter.start_page_index, chapter.title),
        )
    )


__all__ = [
    "BoundaryResolution",
    "BoundaryResolutionResult",
    "ChapterBoundaryResolver",
]
