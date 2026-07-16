from dataclasses import dataclass
from pathlib import Path

import fitz

from ..config import settings


@dataclass
class PageText:
    page_number: int
    text: str


def extract_pdf(path: Path, ocr_enabled: bool = settings.ocr_enabled) -> tuple[list[PageText], bool]:
    pages: list[PageText] = []
    ocr_used = False
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            if not text and ocr_enabled:
                text_page = page.get_textpage_ocr(language=settings.ocr_languages, dpi=settings.ocr_dpi)
                text = page.get_text("text", textpage=text_page).strip()
                ocr_used = ocr_used or bool(text)
            if text:
                pages.append(PageText(page_number=index + 1, text=text))
    return pages, ocr_used


def chunk_pages(pages: list[PageText], max_chars: int = 1200, overlap: int = 150) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    for page in pages:
        text = " ".join(page.text.split())
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append((page.page_number, chunk))
            if end == len(text):
                break
            start = max(0, end - overlap)
    return chunks
