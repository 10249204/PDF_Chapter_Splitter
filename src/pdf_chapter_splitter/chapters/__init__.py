"""Chapter domain package.

This package defines candidate and confirmed chapter contracts. Automatic
chapter recognition is intentionally outside the current phase.
"""

from pdf_chapter_splitter.chapters.adapters import (
    ManualCandidateDetector,
    OutlineCandidateDetector,
    sort_chapter_candidates,
    validate_chapter_candidates,
)
from pdf_chapter_splitter.chapters.boundaries import (
    BoundaryResolution,
    BoundaryResolutionResult,
    ChapterBoundaryResolver,
)
from pdf_chapter_splitter.chapters.confirmation import (
    ChapterConfirmationDecision,
    ChapterConfirmationOutcome,
    ChapterConfirmationResult,
    ChapterConfirmationService,
    ChapterValidator,
    ConfirmationAction,
)
from pdf_chapter_splitter.chapters.detectors import (
    TextLayoutCandidateDetector,
    TextLayoutDetectorConfig,
    TextLayoutFeatures,
)
from pdf_chapter_splitter.chapters.fusion import CandidateFusion, CandidateFusionConfig
from pdf_chapter_splitter.chapters.models import (
    Chapter,
    ChapterCandidate,
    ChapterCandidateQualityFlag,
    ChapterCandidateSource,
    ChapterEvidence,
    ChapterEvidenceType,
    ChapterProvenance,
    ChapterStructureType,
    ManualChapterInput,
)
from pdf_chapter_splitter.chapters.outline_quality import (
    OutlineCandidateQuality,
    OutlineQualityClassifier,
)
from pdf_chapter_splitter.chapters.toc import (
    TOCPageClassification,
    TOCPageDetector,
    TOCPageDetectorConfig,
    TOCPageEvidence,
    TOCPageEvidenceType,
)

__all__ = [
    "Chapter",
    "ChapterCandidate",
    "ChapterCandidateQualityFlag",
    "ChapterCandidateSource",
    "ChapterEvidence",
    "ChapterEvidenceType",
    "BoundaryResolution",
    "BoundaryResolutionResult",
    "CandidateFusion",
    "CandidateFusionConfig",
    "ChapterBoundaryResolver",
    "ChapterConfirmationDecision",
    "ChapterConfirmationOutcome",
    "ChapterConfirmationResult",
    "ChapterConfirmationService",
    "ChapterProvenance",
    "ChapterStructureType",
    "ChapterValidator",
    "ConfirmationAction",
    "ManualCandidateDetector",
    "ManualChapterInput",
    "OutlineCandidateQuality",
    "OutlineCandidateDetector",
    "OutlineQualityClassifier",
    "TOCPageClassification",
    "TOCPageDetector",
    "TOCPageDetectorConfig",
    "TOCPageEvidence",
    "TOCPageEvidenceType",
    "TextLayoutCandidateDetector",
    "TextLayoutDetectorConfig",
    "TextLayoutFeatures",
    "sort_chapter_candidates",
    "validate_chapter_candidates",
]
