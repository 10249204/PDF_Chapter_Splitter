"""User confirmation workflow for chapter candidates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from pdf_chapter_splitter.chapters.models import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterProvenance,
)


class ConfirmationAction(StrEnum):
    """A user decision for a chapter candidate."""

    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ChapterConfirmationDecision:
    """A pending user decision for one candidate."""

    action: ConfirmationAction
    candidate: ChapterCandidate
    title: str | None = None
    start_page_index: int | None = None
    start_page_number: int | None = None

    @classmethod
    def accept(
        cls,
        candidate: ChapterCandidate,
        title: str | None = None,
        start_page_index: int | None = None,
        start_page_number: int | None = None,
    ) -> "ChapterConfirmationDecision":
        return cls(
            action=ConfirmationAction.ACCEPT,
            candidate=candidate,
            title=title,
            start_page_index=start_page_index,
            start_page_number=start_page_number,
        )

    @classmethod
    def reject(cls, candidate: ChapterCandidate) -> "ChapterConfirmationDecision":
        return cls(action=ConfirmationAction.REJECT, candidate=candidate)

    def __post_init__(self) -> None:
        if not isinstance(self.action, ConfirmationAction):
            raise ValueError("action must be a ConfirmationAction")
        if not isinstance(self.candidate, ChapterCandidate):
            raise ValueError("candidate must be a ChapterCandidate")
        if self.start_page_index is not None and self.start_page_number is not None:
            raise ValueError("start_page_index and start_page_number cannot both be provided")
        if self.start_page_index is not None and self.start_page_index < 0:
            raise ValueError("start_page_index must be 0 or greater")
        if self.start_page_number is not None and self.start_page_number < 1:
            raise ValueError("start_page_number must be 1 or greater")


@dataclass(frozen=True, slots=True)
class ChapterConfirmationOutcome:
    """Result of applying one confirmation action."""

    action: ConfirmationAction
    chapter: Chapter | None
    rejected_candidate: ChapterCandidate | None


@dataclass(frozen=True, slots=True)
class ChapterConfirmationResult:
    """Batch confirmation result for future UI or CLI consumers."""

    accepted_chapters: tuple[Chapter, ...]
    rejected_candidates: tuple[ChapterCandidate, ...]
    outcomes: tuple[ChapterConfirmationOutcome, ...]


class ChapterConfirmationService:
    """Apply explicit user decisions to chapter candidates."""

    def accept(
        self,
        candidate: ChapterCandidate,
        title: str | None = None,
        start_page_index: int | None = None,
        start_page_number: int | None = None,
        page_count: int | None = None,
    ) -> Chapter:
        """Create a confirmed chapter from a user-accepted candidate."""

        start_index = _resolve_start_page_index(candidate.start_page_index, start_page_index, start_page_number)
        chapter = Chapter(
            title=candidate.title if title is None else title,
            start_page_index=start_index,
            level=candidate.level,
            provenance=_provenance_from_candidate(candidate),
        )
        chapter.validate(page_count=page_count)
        return chapter

    def reject(self, candidate: ChapterCandidate) -> ChapterConfirmationOutcome:
        """Record a rejected candidate without creating a chapter."""

        return ChapterConfirmationOutcome(
            action=ConfirmationAction.REJECT,
            chapter=None,
            rejected_candidate=candidate,
        )

    def create_manual(
        self,
        title: str,
        start_page_number: int,
        level: int = 1,
        page_count: int | None = None,
    ) -> Chapter:
        """Create a confirmed chapter directly from user input."""

        chapter = Chapter.from_page_number(
            title=title,
            start_page_number=start_page_number,
            level=level,
            provenance=_manual_provenance(title, start_page_number - 1),
        )
        chapter.validate(page_count=page_count)
        return chapter

    def apply_decisions(
        self,
        decisions: Iterable[ChapterConfirmationDecision],
        page_count: int | None = None,
    ) -> ChapterConfirmationResult:
        """Apply multiple decisions and return sorted accepted chapters."""

        outcomes: list[ChapterConfirmationOutcome] = []
        accepted_chapters: list[Chapter] = []
        rejected_candidates: list[ChapterCandidate] = []

        for decision in decisions:
            if decision.action is ConfirmationAction.ACCEPT:
                chapter = self.accept(
                    decision.candidate,
                    title=decision.title,
                    start_page_index=decision.start_page_index,
                    start_page_number=decision.start_page_number,
                    page_count=page_count,
                )
                accepted_chapters.append(chapter)
                outcomes.append(
                    ChapterConfirmationOutcome(
                        action=ConfirmationAction.ACCEPT,
                        chapter=chapter,
                        rejected_candidate=None,
                    )
                )
            elif decision.action is ConfirmationAction.REJECT:
                outcome = self.reject(decision.candidate)
                rejected_candidates.append(decision.candidate)
                outcomes.append(outcome)
            else:
                raise ValueError(f"Unsupported confirmation action: {decision.action}")

        sorted_chapters = ChapterValidator().validate(accepted_chapters, page_count=page_count)
        return ChapterConfirmationResult(
            accepted_chapters=sorted_chapters,
            rejected_candidates=tuple(rejected_candidates),
            outcomes=tuple(outcomes),
        )


class ChapterValidator:
    """Validate and sort confirmed chapter starts."""

    def validate(
        self,
        chapters: Iterable[Chapter],
        page_count: int | None = None,
    ) -> tuple[Chapter, ...]:
        normalized_chapters = tuple(chapters)
        seen_pages: set[int] = set()

        for chapter in normalized_chapters:
            if not isinstance(chapter, Chapter):
                raise ValueError("chapters must contain Chapter items")
            chapter.validate(page_count=page_count)
            if chapter.start_page_index in seen_pages:
                raise ValueError("chapter start_page_index values must be unique")
            seen_pages.add(chapter.start_page_index)

        return tuple(
            sorted(
                normalized_chapters,
                key=lambda chapter: (chapter.start_page_index, chapter.title),
            )
        )


def _resolve_start_page_index(
    candidate_start_page_index: int,
    start_page_index: int | None,
    start_page_number: int | None,
) -> int:
    if start_page_index is not None and start_page_number is not None:
        raise ValueError("start_page_index and start_page_number cannot both be provided")
    if start_page_index is not None:
        if start_page_index < 0:
            raise ValueError("start_page_index must be 0 or greater")
        return start_page_index
    if start_page_number is not None:
        if start_page_number < 1:
            raise ValueError("start_page_number must be 1 or greater")
        return start_page_number - 1
    return candidate_start_page_index


def _provenance_from_candidate(candidate: ChapterCandidate) -> ChapterProvenance:
    return ChapterProvenance(
        candidate_title=candidate.title,
        candidate_start_page_index=candidate.start_page_index,
        candidate_sources=candidate.sources,
        candidate_confidence=candidate.confidence,
        candidate_evidences=candidate.evidences,
        candidate_original_titles=candidate.original_titles,
        confirmed_from_candidate=True,
    )


def _manual_provenance(title: str, start_page_index: int) -> ChapterProvenance:
    evidence = ChapterEvidence(
        evidence_type=ChapterEvidenceType.MANUAL,
        description="User directly created this confirmed chapter",
        page_index=start_page_index,
        text=title,
    )
    return ChapterProvenance(
        candidate_title=None,
        candidate_start_page_index=None,
        candidate_sources=(ChapterCandidateSource.MANUAL,),
        candidate_confidence=None,
        candidate_evidences=(evidence,),
        candidate_original_titles=(title,),
        confirmed_from_candidate=False,
    )


__all__ = [
    "ChapterConfirmationDecision",
    "ChapterConfirmationOutcome",
    "ChapterConfirmationResult",
    "ChapterConfirmationService",
    "ChapterValidator",
    "ConfirmationAction",
]
