from __future__ import annotations

import pytest

from pdf_chapter_splitter.chapters import (
    BoundaryResolutionResult,
    Chapter,
    ChapterBoundaryResolver,
)
from pdf_chapter_splitter.models import SplitSegment


def test_boundary_resolver_converts_multiple_chapters_to_half_open_segments():
    chapters = (
        Chapter.from_page_number("Chapter 1", 10),
        Chapter.from_page_number("Chapter 2", 45),
        Chapter.from_page_number("Chapter 3", 83),
        Chapter.from_page_number("Chapter 4", 126),
    )

    result = ChapterBoundaryResolver().resolve(chapters, page_count=300)

    assert _ranges(result.segments) == [
        ("Chapter 1", 9, 44),
        ("Chapter 2", 44, 82),
        ("Chapter 3", 82, 125),
        ("Chapter 4", 125, 300),
    ]


def test_boundary_resolver_accepts_unsorted_chapters_and_returns_sorted_segments():
    chapters = (
        Chapter.from_page_number("Chapter 3", 83),
        Chapter.from_page_number("Chapter 1", 10),
        Chapter.from_page_number("Chapter 4", 126),
        Chapter.from_page_number("Chapter 2", 45),
    )

    result = ChapterBoundaryResolver().resolve(chapters, page_count=300)

    assert [segment.title for segment in result.segments] == [
        "Chapter 1",
        "Chapter 2",
        "Chapter 3",
        "Chapter 4",
    ]
    assert _ranges(result.segments) == [
        ("Chapter 1", 9, 44),
        ("Chapter 2", 44, 82),
        ("Chapter 3", 82, 125),
        ("Chapter 4", 125, 300),
    ]


def test_boundary_resolver_handles_single_chapter_to_pdf_end():
    result = ChapterBoundaryResolver().resolve(
        (Chapter.from_page_number("Chapter 1", 20),),
        page_count=300,
    )

    assert _ranges(result.segments) == [("Chapter 1", 19, 300)]
    assert result.segments[0].gui_start_page_number == 20
    assert result.segments[0].gui_end_page_number == 300


def test_boundary_resolver_does_not_create_implicit_prefix_segment():
    result = ChapterBoundaryResolver().resolve(
        (
            Chapter.from_page_number("Chapter 1", 10),
            Chapter.from_page_number("Chapter 2", 45),
        ),
        page_count=100,
    )

    assert result.segments[0].start_page_index == 9
    assert all(segment.start_page_index != 0 for segment in result.segments)


def test_boundary_resolver_returns_empty_result_for_empty_chapters():
    result = ChapterBoundaryResolver().resolve((), page_count=300)

    assert result == BoundaryResolutionResult(resolutions=())
    assert result.segments == ()
    assert result.source_chapters == ()


def test_boundary_resolver_rejects_duplicate_chapter_start_pages():
    chapters = (
        Chapter.from_page_number("Part I", 50),
        Chapter.from_page_number("Chapter 3", 50),
    )

    with pytest.raises(ValueError):
        ChapterBoundaryResolver().resolve(chapters, page_count=100)


def test_boundary_resolver_rejects_invalid_chapter_page_index():
    invalid_chapter = object.__new__(Chapter)
    object.__setattr__(invalid_chapter, "title", "Invalid")
    object.__setattr__(invalid_chapter, "start_page_index", -1)
    object.__setattr__(invalid_chapter, "level", 1)
    object.__setattr__(invalid_chapter, "provenance", None)

    with pytest.raises(ValueError):
        ChapterBoundaryResolver().resolve((invalid_chapter,), page_count=100)


def test_boundary_resolver_rejects_chapter_start_at_or_after_page_count():
    chapter = Chapter.from_page_number("Chapter 100", 100)

    with pytest.raises(ValueError):
        ChapterBoundaryResolver().resolve((chapter,), page_count=99)


@pytest.mark.parametrize("page_count", [0, -1])
def test_boundary_resolver_rejects_invalid_page_count(page_count: int):
    with pytest.raises(ValueError):
        ChapterBoundaryResolver().resolve(
            (Chapter.from_page_number("Chapter 1", 1),),
            page_count=page_count,
        )


def test_boundary_resolver_passes_chapter_title_to_split_segment_title():
    result = ChapterBoundaryResolver().resolve(
        (Chapter.from_page_number("第三章 文件系统", 10),),
        page_count=20,
    )

    assert result.segments[0].title == "第三章 文件系统"


def test_boundary_resolver_does_not_modify_original_chapters():
    chapter = Chapter.from_page_number("Chapter 1", 10)
    original = chapter

    ChapterBoundaryResolver().resolve((chapter,), page_count=20)

    assert chapter == original
    assert chapter.title == "Chapter 1"
    assert chapter.start_page_index == 9
    assert not hasattr(chapter, "end_page_index")


def test_boundary_resolver_preserves_chapter_to_segment_mapping():
    chapter = Chapter.from_page_number("Chapter 1", 10)

    result = ChapterBoundaryResolver().resolve((chapter,), page_count=20)

    assert result.source_chapters == (chapter,)
    assert result.resolutions[0].chapter == chapter
    assert result.resolutions[0].segment == SplitSegment(
        title="Chapter 1",
        start_page_index=9,
        end_page_index=20,
    )


def test_boundary_resolver_outputs_contiguous_non_empty_segments_within_pdf_range():
    result = ChapterBoundaryResolver().resolve(
        (
            Chapter.from_page_number("Chapter 1", 10),
            Chapter.from_page_number("Chapter 2", 45),
            Chapter.from_page_number("Chapter 3", 83),
        ),
        page_count=100,
    )

    segments = result.segments
    assert all(0 <= segment.start_page_index < segment.end_page_index <= 100 for segment in segments)
    assert all(
        left.end_page_index == right.start_page_index
        for left, right in zip(segments, segments[1:])
    )
    assert segments[-1].end_page_index == 100


def test_boundary_resolver_result_is_stable_for_different_input_order():
    chapters = (
        Chapter.from_page_number("Chapter 1", 10),
        Chapter.from_page_number("Chapter 2", 45),
        Chapter.from_page_number("Chapter 3", 83),
    )

    left = ChapterBoundaryResolver().resolve(chapters, page_count=100)
    right = ChapterBoundaryResolver().resolve(tuple(reversed(chapters)), page_count=100)

    assert left.segments == right.segments
    assert left.source_chapters == right.source_chapters


def test_boundary_resolver_does_not_add_level_to_split_segment():
    chapter = Chapter.from_page_number("Chapter 1", 10, level=2)

    result = ChapterBoundaryResolver().resolve((chapter,), page_count=20)

    assert chapter.level == 2
    assert not hasattr(result.segments[0], "level")


def _ranges(segments: tuple[SplitSegment, ...]) -> list[tuple[str, int, int]]:
    return [
        (segment.title, segment.start_page_index, segment.end_page_index)
        for segment in segments
    ]
