from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".csv"}


@dataclass
class DocumentPage:
    number: int
    image: Image.Image
    embedded_text: str = ""
    embedded_words: list[tuple[float, float, float, float, str]] | None = None


class DocumentService:
    def load(self, path: Path, scale: int = 2) -> list[DocumentPage]:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported document type: {path.suffix}")
        if path.suffix.lower() == ".pdf":
            return self._load_pdf(path, scale)
        image = Image.open(path).convert("RGB")
        return [DocumentPage(number=1, image=image)]

    def _load_pdf(self, path: Path, scale: int = 2) -> list[DocumentPage]:
        pages: list[DocumentPage] = []
        with fitz.open(path) as document:
            for index, page in enumerate(document):
                matrix = fitz.Matrix(scale, scale)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                image = Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
                pages.append(
                    DocumentPage(
                        number=index + 1,
                        image=image,
                        embedded_text=page.get_text("text"),
                        embedded_words=[
                            (word[0], word[1], word[2], word[3], word[4])
                            for word in page.get_text("words")
                        ],
                    )
                )
        return pages
