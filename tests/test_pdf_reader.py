import inspect

from pdf_chapter_splitter.pdf.models import OutlineItem, PageSize, TextBlock
from pdf_chapter_splitter.pdf.reader import PDFReader


def test_pdf_reader_is_an_abstract_contract():
    assert inspect.isabstract(PDFReader)


def test_pdf_reader_contract_can_be_implemented_by_future_readers():
    class DummyReader(PDFReader):
        @property
        def page_count(self) -> int:
            return 2

        def get_page_text(self, page_index: int) -> str:
            return f"page {page_index}"

        def get_all_page_text(self) -> list[str]:
            return ["page 0", "page 1"]

        def get_page_text_blocks(self, page_index: int) -> list[TextBlock]:
            return []

        def get_page_size(self, page_index: int) -> PageSize:
            return PageSize(width=595, height=842)

        def get_outline(self) -> list[OutlineItem]:
            return []

        def has_text_layer(self) -> bool:
            return True

        def get_metadata(self) -> dict[str, str]:
            return {"title": "Fixture"}

        def close(self) -> None:
            return None

    reader = DummyReader()

    assert reader.page_count == 2
    assert reader.get_page_text(0) == "page 0"
    assert reader.get_page_size(0) == PageSize(width=595, height=842)
    assert reader.get_metadata() == {"title": "Fixture"}
