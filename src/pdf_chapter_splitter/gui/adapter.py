"""Thin GUI adapter over the application session."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pdf_chapter_splitter.application import (
    ManualSplitInput,
    ProgressEvent,
    WorkflowSession,
)


class GuiWorkflowAdapter:
    """Expose GUI actions through WorkflowSession only."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        progress_listener: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        self.progress_listener = progress_listener
        self.session = (
            WorkflowSession(progress_listener=self.handle_progress)
            if session is None
            else session
        )
        if session is not None and progress_listener is not None:
            setattr(self.session, "progress_listener", self.handle_progress)
            if hasattr(self.session, "workflow"):
                setattr(self.session.workflow, "progress_listener", self.handle_progress)

    def analyze(self, input_path: str | Path):
        return self.session.analyze(Path(input_path))

    def accept_candidate(
        self,
        candidate: Any,
        *,
        title: str | None = None,
        start_page_number: int | None = None,
    ):
        return self.session.accept_candidate(
            candidate,
            title=title,
            start_page_number=start_page_number,
        )

    def reject_candidate(self, candidate: Any):
        return self.session.reject_candidate(candidate)

    def accept_candidates(self, candidates: Iterable[Any]):
        return self.session.accept_candidates(tuple(candidates))

    def reject_candidates(self, candidates: Iterable[Any]):
        return self.session.reject_candidates(tuple(candidates))

    def add_manual_chapter(
        self,
        title: str,
        *,
        start_page_number: int,
        level: int = 1,
    ):
        return self.session.add_manual_chapter(
            title,
            start_page_number=start_page_number,
            level=level,
        )

    def update_confirmed_chapter(
        self,
        index: int,
        *,
        title: str,
        start_page_number: int,
        level: int = 1,
    ):
        return self.session.update_confirmed_chapter(
            index,
            title=title,
            start_page_number=start_page_number,
            level=level,
        )

    def remove_confirmed_chapter(self, index: int):
        return self.session.remove_confirmed_chapter(index)

    def confirm(self, decisions: Iterable[Any]):
        return self.session.confirm(tuple(decisions))

    def resolve_then_execute(
        self,
        output_directory: str | Path,
        *,
        zip_path: str | Path | None = None,
    ):
        self.session.resolve()
        return self.session.execute(
            output_directory=Path(output_directory),
            zip_path=None if zip_path is None else Path(zip_path),
        )

    def process_manual_ranges(
        self,
        input_path: str | Path,
        manual_inputs: Iterable[ManualSplitInput],
        output_directory: str | Path,
        *,
        zip_path: str | Path | None = None,
    ):
        return self.session.process_manual_ranges(
            Path(input_path),
            tuple(manual_inputs),
            Path(output_directory),
            zip_path=None if zip_path is None else Path(zip_path),
        )

    def handle_progress(self, event: ProgressEvent) -> None:
        if self.progress_listener is None:
            return
        self.progress_listener(event)


__all__ = ["GuiWorkflowAdapter"]
