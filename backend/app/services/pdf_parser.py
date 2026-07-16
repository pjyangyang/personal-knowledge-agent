from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class PageText:
    page_number: int
    text: str


def extract_pdf(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            if text:
                pages.append(PageText(page_number=index + 1, text=text))
    return pages


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
