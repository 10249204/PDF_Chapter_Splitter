import pytest

from pdf_chapter_splitter.models import Chapter, SplitSegment


def test_split_segment_uses_zero_based_half_open_page_indexes():
    segment = SplitSegment(
        title="Introduction",
        start_page_index=0,
        end_page_index=3,
    )

    assert segment.page_count == 3
    assert segment.gui_start_page_number == 1
    assert segment.gui_end_page_number == 3


@pytest.mark.parametrize(
    ("start_page_index", "end_page_index"),
    [
        (-1, 1),
        (0, 0),
        (2, 1),
    ],
)
def test_split_segment_rejects_invalid_page_ranges(start_page_index, end_page_index):
    with pytest.raises(ValueError):
        SplitSegment(
            title="Invalid",
            start_page_index=start_page_index,
            end_page_index=end_page_index,
        )


def test_chapter_keeps_zero_based_start_index_and_exposes_gui_page_number():
    chapter = Chapter(title="Chapter 1", start_page_index=0, level=1)

    assert chapter.gui_page_number == 1
    assert not hasattr(chapter, "end_page_index")


@pytest.mark.parametrize(
    ("title", "start_page_index", "level"),
    [
        ("", 0, 1),
        ("   ", 0, 1),
        ("Chapter", -1, 1),
        ("Chapter", 0, 0),
    ],
)
def test_chapter_rejects_invalid_values(title, start_page_index, level):
    with pytest.raises(ValueError):
        Chapter(title=title, start_page_index=start_page_index, level=level)
