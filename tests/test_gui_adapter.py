from __future__ import annotations

from pathlib import Path

from pdf_chapter_splitter.application import ManualSplitInput, ProgressEvent, WorkflowStage
from pdf_chapter_splitter.chapters import (
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterConfirmationDecision,
    ChapterEvidence,
    ChapterEvidenceType,
)
from pdf_chapter_splitter.gui.adapter import GuiWorkflowAdapter


def test_adapter_analyze_delegates_to_session(tmp_path: Path):
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)

    adapter.analyze(tmp_path / "book.pdf")

    assert session.calls == [("analyze", tmp_path / "book.pdf")]


def test_adapter_accept_candidate_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)
    candidate = _candidate("Chapter 1", 0)

    adapter.accept_candidate(candidate, title="Intro", start_page_number=2)

    assert session.calls == [("accept_candidate", candidate, "Intro", 2)]


def test_adapter_reject_candidate_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)
    candidate = _candidate("Preface", 0)

    adapter.reject_candidate(candidate)

    assert session.calls == [("reject_candidate", candidate)]


def test_adapter_confirm_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)
    decision = ChapterConfirmationDecision.accept(_candidate("Chapter 1", 0))

    adapter.confirm((decision,))

    assert session.calls == [("confirm", (decision,))]


def test_adapter_resolve_then_execute_delegates_to_session(tmp_path: Path):
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)

    adapter.resolve_then_execute(tmp_path / "out", zip_path=tmp_path / "book.zip")

    assert session.calls == [
        ("resolve",),
        ("execute", tmp_path / "out", tmp_path / "book.zip"),
    ]


def test_adapter_process_manual_ranges_delegates_to_session(tmp_path: Path):
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)
    manual_inputs = (ManualSplitInput("Part 1", 1, 5),)

    adapter.process_manual_ranges(
        tmp_path / "book.pdf",
        manual_inputs,
        tmp_path / "out",
        zip_path=tmp_path / "manual.zip",
    )

    assert session.calls == [
        (
            "process_manual_ranges",
            tmp_path / "book.pdf",
            manual_inputs,
            tmp_path / "out",
            tmp_path / "manual.zip",
        )
    ]


def test_adapter_add_manual_chapter_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)

    adapter.add_manual_chapter("Appendix", start_page_number=9, level=2)

    assert session.calls == [("add_manual_chapter", "Appendix", 9, 2)]


def test_adapter_update_confirmed_chapter_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)

    adapter.update_confirmed_chapter(0, title="Chapter 1 Edited", start_page_number=2, level=2)

    assert session.calls == [("update_confirmed_chapter", 0, "Chapter 1 Edited", 2, 2)]


def test_adapter_remove_confirmed_chapter_delegates_to_session():
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session)

    adapter.remove_confirmed_chapter(1)

    assert session.calls == [("remove_confirmed_chapter", 1)]


def test_adapter_progress_listener_receives_existing_progress_event():
    events: list[ProgressEvent] = []
    session = FakeSession()
    adapter = GuiWorkflowAdapter(session=session, progress_listener=events.append)

    adapter.handle_progress(ProgressEvent(WorkflowStage.ANALYZING, "Analyzing PDF"))

    assert events == [ProgressEvent(WorkflowStage.ANALYZING, "Analyzing PDF")]


def test_adapter_attaches_progress_listener_to_injected_session_workflow():
    events: list[ProgressEvent] = []
    session = FakeSession()
    session.workflow = FakeWorkflow()

    GuiWorkflowAdapter(session=session, progress_listener=events.append)
    session.workflow.progress_listener(ProgressEvent(WorkflowStage.ANALYZING, "Analyzing PDF"))

    assert events == [ProgressEvent(WorkflowStage.ANALYZING, "Analyzing PDF")]


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def analyze(self, input_path: Path):
        self.calls.append(("analyze", input_path))

    def accept_candidate(
        self,
        candidate,
        *,
        title: str | None = None,
        start_page_number: int | None = None,
    ):
        self.calls.append(("accept_candidate", candidate, title, start_page_number))

    def reject_candidate(self, candidate):
        self.calls.append(("reject_candidate", candidate))

    def confirm(self, decisions):
        self.calls.append(("confirm", tuple(decisions)))

    def resolve(self):
        self.calls.append(("resolve",))

    def execute(self, *, output_directory: Path, zip_path: Path | None = None):
        self.calls.append(("execute", output_directory, zip_path))

    def process_manual_ranges(
        self,
        input_path: Path,
        manual_inputs,
        output_directory: Path,
        *,
        zip_path: Path | None = None,
    ):
        self.calls.append(
            ("process_manual_ranges", input_path, tuple(manual_inputs), output_directory, zip_path)
        )

    def add_manual_chapter(
        self,
        title: str,
        *,
        start_page_number: int,
        level: int = 1,
    ):
        self.calls.append(("add_manual_chapter", title, start_page_number, level))

    def update_confirmed_chapter(
        self,
        index: int,
        *,
        title: str,
        start_page_number: int,
        level: int = 1,
    ):
        self.calls.append(("update_confirmed_chapter", index, title, start_page_number, level))

    def remove_confirmed_chapter(self, index: int):
        self.calls.append(("remove_confirmed_chapter", index))


class FakeWorkflow:
    def __init__(self) -> None:
        self.progress_listener = None


def _candidate(title: str, start_page_index: int) -> ChapterCandidate:
    return ChapterCandidate(
        title=title,
        start_page_index=start_page_index,
        source=ChapterCandidateSource.TEXT_LAYOUT,
        confidence=0.9,
        level=1,
        evidences=(
            ChapterEvidence(
                evidence_type=ChapterEvidenceType.TEXT_PATTERN,
                description="text layout evidence",
                page_index=start_page_index,
                text=title,
            ),
        ),
    )
