from __future__ import annotations

from pathlib import Path

import fitz
import pytest


@pytest.fixture
def text_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "text.pdf"
    document = fitz.open()

    page = document.new_page()
    page.insert_text((72, 72), "Chapter 1", fontsize=18, fontname="helv")
    page.insert_text((72, 104), "Hello World", fontsize=12, fontname="helv")

    page = document.new_page()
    page.insert_text((72, 72), "Chapter 2", fontsize=18, fontname="helv")
    page.insert_text((72, 104), "Hello PDF", fontsize=12, fontname="helv")

    document.set_toc(
        [
            [1, "Chapter 1", 1],
            [1, "Chapter 2", 2],
        ]
    )
    document.save(path)
    document.close()
    return path


@pytest.fixture
def image_only_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "image-only.pdf"
    document = fitz.open()
    page = document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), 0)
    pixmap.clear_with(255)
    page.insert_image(fitz.Rect(72, 72, 120, 120), pixmap=pixmap)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def partial_text_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "partial-text.pdf"
    document = fitz.open()

    page = document.new_page()
    page.insert_text((72, 72), "Chapter 1 Visible Text", fontsize=18, fontname="helv")
    page.insert_text((72, 104), "This page has enough readable text for diagnostics.", fontsize=12)

    for _ in range(4):
        document.new_page()

    document.save(path)
    document.close()
    return path


@pytest.fixture
def toc_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "toc.pdf"
    document = fitz.open()

    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "Contents", fontsize=18, fontname="helv")
    page.insert_text((72, 116), "Chapter 1 Introduction ........ 10", fontsize=12)
    page.insert_text((72, 140), "Chapter 2 Methods ............. 24", fontsize=12)
    page.insert_text((72, 164), "Chapter 3 Results ............. 39", fontsize=12)

    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "Chapter 1 Introduction", fontsize=18, fontname="helv")
    page.insert_text((72, 116), "This is a normal chapter page with readable body text.", fontsize=12)

    document.save(path)
    document.close()
    return path


@pytest.fixture
def ocr_like_text_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "ocr-like-text.pdf"
    document = fitz.open()

    noisy_text = "@@@ ### ~~~ ||| 000 111 ??? " * 12
    for _ in range(3):
        page = document.new_page(width=595, height=842)
        page.insert_text((72, 72), noisy_text, fontsize=12, fontname="helv")

    document.set_metadata({"producer": "Adobe Acrobat Paper Capture OCR"})
    document.save(path)
    document.close()
    return path


@pytest.fixture
def password_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "password.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Secret")
    document.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()
    return path


@pytest.fixture
def five_page_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "five-pages.pdf"
    document = fitz.open()

    for page_number in range(1, 6):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {page_number}", fontsize=14, fontname="helv")

    document.save(path)
    document.close()
    return path
