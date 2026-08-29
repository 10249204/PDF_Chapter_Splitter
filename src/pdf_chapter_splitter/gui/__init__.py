"""PySide6 GUI package."""

from pdf_chapter_splitter.gui.adapter import GuiWorkflowAdapter
from pdf_chapter_splitter.gui.app import PDFChapterSplitterWindow, run_app
from pdf_chapter_splitter.gui.presenters import (
    CandidateViewModel,
    ChapterViewModel,
    ErrorViewModel,
    ProgressViewModel,
    format_application_error,
    format_candidate,
    format_chapter,
    format_progress_event,
)

__all__ = [
    "CandidateViewModel",
    "ChapterViewModel",
    "ErrorViewModel",
    "GuiWorkflowAdapter",
    "PDFChapterSplitterWindow",
    "ProgressViewModel",
    "format_application_error",
    "format_candidate",
    "format_chapter",
    "format_progress_event",
    "run_app",
]
