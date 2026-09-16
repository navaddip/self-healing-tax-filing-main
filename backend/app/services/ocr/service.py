from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import pytesseract
    from pytesseract import Output
except Exception:  # pragma: no cover - optional runtime dependency
    pytesseract = None
    Output = None


@dataclass
class OCRResult:
    text: str
    confidence: float
    engine: str


class OCRService:
    def __init__(self, tesseract_cmd: str | None = None):
        detected = tesseract_cmd or shutil.which("tesseract")
        windows_default = Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        if not detected and windows_default.exists():
            detected = str(windows_default)
        self.available = bool(detected and pytesseract is not None and Output is not None)
        if detected and pytesseract is not None:
            pytesseract.pytesseract.tesseract_cmd = detected

    def preprocess(self, image: Image.Image) -> Image.Image:
        gray = ImageOps.grayscale(image)
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        return gray.filter(ImageFilter.SHARPEN)

    def extract(self, image: Image.Image, embedded_text: str = "") -> OCRResult:
        if embedded_text.strip():
            return OCRResult(embedded_text, 0.99, "pdf-text")
        if not self.available:
            return OCRResult("", 0.0, "unavailable")
        processed = self.preprocess(image)
        data = pytesseract.image_to_data(processed, output_type=Output.DICT)
        confidences = [
            float(value)
            for value in data["conf"]
            if str(value) not in {"-1", ""} and float(value) >= 0
        ]
        confidence = (
            sum(confidences) / len(confidences) / 100 if confidences else 0
        )
        text = pytesseract.image_to_string(processed)
        return OCRResult(text.strip(), round(confidence, 4), "tesseract")
