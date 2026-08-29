"""PDF processing boundaries."""

from pdf_chapter_splitter.pdf.errors import (
    PDFClosedError,
    PDFOpenError,
    PDFPageIndexError,
    PDFPasswordError,
    PDFReaderError,
)
from pdf_chapter_splitter.pdf.models import (
    BoundingBox,
    OutlineItem,
    PageSize,
    TextBlock,
    TextLine,
    TextSpan,
)
from pdf_chapter_splitter.pdf.pymupdf_reader import PyMuPDFReader
from pdf_chapter_splitter.pdf.quality import (
    PDFTextQualityDiagnostic,
    PDFTextQualityDiagnosticConfig,
    PDFTextQualityLevel,
    PDFTextQualityReport,
)
from pdf_chapter_splitter.pdf.reader import PDFReader

__all__ = [
    "BoundingBox",
    "OutlineItem",
    "PDFClosedError",
    "PDFOpenError",
    "PDFPageIndexError",
    "PDFPasswordError",
    "PDFReader",
    "PDFReaderError",
    "PDFTextQualityDiagnostic",
    "PDFTextQualityDiagnosticConfig",
    "PDFTextQualityLevel",
    "PDFTextQualityReport",
    "PyMuPDFReader",
    "PageSize",
    "TextBlock",
    "TextLine",
    "TextSpan",
]
