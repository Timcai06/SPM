"""Load PDFs for RAG."""

import os
from typing import Iterator
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class PDFChunk:
    content: str
    metadata: dict


def load_pdf(pdf_path: str, chunk_size: int = 500) -> Iterator[PDFChunk]:
    """Load PDF and split into chunks."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue

            chunks = _split_into_chunks(text, chunk_size)
            for chunk_idx, chunk in enumerate(chunks):
                yield PDFChunk(
                    content=chunk,
                    metadata={
                        "type": "pdf",
                        "source": os.path.basename(pdf_path),
                        "page": page_num,
                        "chunk": chunk_idx,
                    },
                )


def load_pdfs_from_dir(pdf_dir: str, chunk_size: int = 500) -> Iterator[PDFChunk]:
    """Load all PDFs from a directory."""
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        return

    for pdf_path in pdf_dir.glob("*.pdf"):
        yield from load_pdf(str(pdf_path), chunk_size)


def _split_into_chunks(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks of approximately chunk_size chars."""
    lines = text.split("\n")
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        line_len = len(line)
        if current_len + line_len > chunk_size and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks