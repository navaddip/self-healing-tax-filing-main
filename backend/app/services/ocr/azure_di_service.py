"""Azure Document Intelligence OCR fallback.

Runs alongside Tesseract on scanned pages (no embedded PDF text layer). Azure's
prebuilt-layout model is table/form-aware, which handles the digit and column
confusions plain OCR makes on low-quality scans (e.g. "0" vs "O", merged table
cells). Results are returned in the same shape as OCRService.extract so the
ReadingAgent can compare and pick whichever output is better-grounded, without
either engine's output bypassing the normal evidence/cross-foot verification.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from app.services.ocr.service import OCRResult


@dataclass
class AzureDIResult(OCRResult):
    pass


class AzureDocumentIntelligenceService:
    def __init__(self, endpoint: str, key: str, model_id: str = "prebuilt-layout"):
        self.endpoint = endpoint.rstrip("/")
        self.key = key
        self.model_id = model_id
        self.available = bool(endpoint and key)
        self._client = None
        self._disabled_reason: str | None = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from app.services.extraction.azure_client import build_azure_client

        self._client = build_azure_client(self.endpoint, self.key)
        return self._client

    def extract(self, image: Image.Image) -> OCRResult:
        """Analyze a page image and return text with an aggregate confidence score.

        Returns a zero-confidence OCRResult (never raises) when Azure DI is not
        configured or the call fails, so a caller can always fall back to
        Tesseract's result without special-casing exceptions.
        """
        if not self.available or self._disabled_reason:
            return OCRResult("", 0.0, "azure-di-unavailable")

        try:
            client = self._get_client()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            poller = client.begin_analyze_document(
                self.model_id, body=buffer.getvalue(), content_type="application/octet-stream"
            )
            result = poller.result()
        except Exception as exc:  # noqa: BLE001 - any SDK/auth/network failure disables this pass
            self._disabled_reason = str(exc)[:500]
            return OCRResult("", 0.0, "azure-di-error")

        text = result.content or ""

        # Aggregate confidence from per-word confidence scores, mirroring
        # OCRService's averaging so the two engines are comparable.
        confidences: list[float] = []
        for page in result.pages or []:
            for word in page.words or []:
                if word.confidence is not None:
                    confidences.append(float(word.confidence))
        confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        return OCRResult(text.strip(), confidence, "azure-document-intelligence")
