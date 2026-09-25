"""Bounded parsing and content checks before a document enters the queue."""
import csv
import io
import warnings
from pathlib import Path
import fitz
from PIL import Image
from fastapi import HTTPException

MIME = {".pdf": {"application/pdf"}, ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
        ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}}

def validate_document(path: Path, content_type: str | None = None):
    suffix = path.suffix.lower()
    if suffix not in MIME:
        raise HTTPException(415, "Unsupported document type")
    if content_type and content_type.split(";")[0] not in MIME[suffix] | {"application/octet-stream"}:
        raise HTTPException(415, "MIME type does not match document extension")
    try:
        if not path.stat().st_size:
            raise ValueError("Empty document")
        if suffix == ".pdf":
            with path.open("rb") as stream:
                if not stream.read(8).startswith(b"%PDF-"):
                    raise ValueError("Invalid PDF signature")
            with fitz.open(path) as doc:
                if doc.needs_pass:
                    raise ValueError("Password-protected PDF: upload an unlocked copy")
                if not 1 <= len(doc) <= 100:
                    raise ValueError("PDF must contain 1 to 100 pages")
                if doc.embfile_count():
                    raise ValueError("PDF attachments are not accepted")
                for page in doc:
                    if page.rect.width * page.rect.height > 20_000_000:
                        raise ValueError("PDF page dimensions exceed processing limit")
                for xref in range(1, doc.xref_length()):
                    obj = doc.xref_object(xref)
                    if any(token in obj for token in ("/JavaScript", "/JS", "/Launch", "/RichMedia", "/AA")):
                        raise ValueError("Active PDF content is not accepted")
                    if "/OpenAction" in obj and ("/S " in obj or "/S/" in obj or "<< " in obj):
                        raise ValueError("Active PDF content is not accepted")
        elif suffix == ".csv":
            text = path.read_text(encoding="utf-8-sig")
            if "\x00" in text:
                raise ValueError("CSV contains binary content")
            rows = csv.reader(io.StringIO(text), strict=True)
            count = 0
            for row in rows:
                count += 1
                if count > 100000 or len(row) > 200:
                    raise ValueError("CSV dimensions exceed processing limit")
            if not count:
                raise ValueError("CSV is empty")
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    expected = "PNG" if suffix == ".png" else "JPEG"
                    if image.format != expected or image.width * image.height > 25_000_000:
                        raise ValueError("Image content or dimensions are invalid")
                    image.verify()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Document rejected: " + str(exc)) from exc
