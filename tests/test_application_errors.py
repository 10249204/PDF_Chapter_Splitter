from __future__ import annotations

from pathlib import Path

import pytest

from pdf_chapter_splitter.application import (
    ApplicationError,
    PDFChapterWorkflow,
    WorkflowError,
    WorkflowStage,
)
from pdf_chapter_splitter.archive import ArchiveOutputError
from pdf_chapter_splitter.chapters import Chapter
from pdf_chapter_splitter.models import SplitSegment
from pdf_chapter_splitter.pdf import PDFOpenError
from pdf_chapter_splitter.splitter import PDFSplitError, SplitResult


def test_missing_pdf_error_keeps_pdf_open_error_for_existing_api(tmp_path: Path):
    with pytest.raises(PDFOpenError):
        PDFChapterWorkflow().analyze(tmp_path / "missing.pdf")


def test_boundary_error_is_not_hidden_by_workflow():
    with pytest.raises(ValueError):
        PDFChapterWorkflow().resolve(
            (Chapter.from_page_number("Chapter 1", 11),),
            page_count=10,
        )


def test_execute_without_segments_raises_application_error_with_stage(tmp_path: Path):
    with pytest.raises(WorkflowError) as exc_info:
        PDFChapterWorkflow().execute(tmp_path / "book.pdf", (), tmp_path / "out")

    error = exc_info.value
    assert isinstance(error, ApplicationError)
    assert error.stage is WorkflowStage.SPLITTING
    assert str(error).strip()
    assert error.cause is None


def test_split_error_is_wrapped_with_stage_and_cause(tmp_path: Path):
    cause = PDFSplitError("split failed")
    workflow = PDFChapterWorkflow(splitter=FailingSplitter(cause))

    with pytest.raises(WorkflowError) as exc_info:
        workflow.execute(
            tmp_path / "book.pdf",
            (SplitSegment("Part 1", 0, 3),),
            tmp_path / "out",
        )

    error = exc_info.value
    assert error.stage is WorkflowStage.SPLITTING
    assert error.cause is cause
    assert error.__cause__ is cause
    assert str(error).strip()


def test_zip_error_is_wrapped_with_stage_and_cause(tmp_path: Path):
    cause = ArchiveOutputError("zip failed")
    workflow = PDFChapterWorkflow(
        splitter=SuccessfulSplitter(),
        zip_creator=FailingZipCreator(cause),
    )

    with pytest.raises(WorkflowError) as exc_info:
        workflow.execute(
            tmp_path / "book.pdf",
            (SplitSegment("Part 1", 0, 3),),
            tmp_path / "out",
            zip_path=tmp_path / "book.zip",
        )

    error = exc_info.value
    assert error.stage is WorkflowStage.CREATING_ZIP
    assert error.cause is cause
    assert error.__cause__ is cause
    assert str(error).strip()


def test_split_programming_error_is_not_wrapped(tmp_path: Path):
    workflow = PDFChapterWorkflow(splitter=FailingSplitter(AttributeError("bug")))

    with pytest.raises(AttributeError):
        workflow.execute(
            tmp_path / "book.pdf",
            (SplitSegment("Part 1", 0, 3),),
            tmp_path / "out",
        )


def test_zip_programming_error_is_not_wrapped(tmp_path: Path):
    workflow = PDFChapterWorkflow(
        splitter=SuccessfulSplitter(),
        zip_creator=FailingZipCreator(TypeError("bug")),
    )

    with pytest.raises(TypeError):
        workflow.execute(
            tmp_path / "book.pdf",
            (SplitSegment("Part 1", 0, 3),),
            tmp_path / "out",
            zip_path=tmp_path / "book.zip",
        )


def test_application_error_preserves_cause_when_created_directly():
    cause = RuntimeError("lower layer")

    error = ApplicationError(
        stage=WorkflowStage.FAILED,
        message="Workflow failed",
        cause=cause,
    )

    assert error.stage is WorkflowStage.FAILED
    assert error.message == "Workflow failed"
    assert error.cause is cause
    assert str(error) == "Workflow failed"


class FailingSplitter:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def split(self, input_path: Path, segments, output_directory: Path):
        raise self.error


class SuccessfulSplitter:
    def split(self, input_path: Path, segments, output_directory: Path) -> SplitResult:
        return SplitResult(input_path=input_path, output_directory=output_directory, outputs=())


class FailingZipCreator:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def create(self, split_result: SplitResult, output_zip_path: Path):
        raise self.error
