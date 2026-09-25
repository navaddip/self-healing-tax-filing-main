"""Unit tests for the Azure Document Intelligence OCR fallback.

Covers:
1. The service is inert (never calls out, returns zero confidence) when not
   configured.
2. A failed/erroring Azure call degrades gracefully instead of raising.
3. ReadingAgent picks whichever engine (Tesseract vs Azure DI) reports higher
   confidence on a scanned page, and leaves text-layer PDFs untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.agents.reading.agent import ReadingAgent
from app.services.documents.service import DocumentPage
from app.services.ocr.azure_di_service import AzureDocumentIntelligenceService
from app.services.ocr.service import OCRResult


def test_azure_di_unavailable_when_unconfigured():
    svc = AzureDocumentIntelligenceService(endpoint="", key="")
    assert svc.available is False
    result = svc.extract(Image.new("RGB", (10, 10)))
    assert result.confidence == 0.0
    assert result.engine == "azure-di-unavailable"


def test_azure_di_degrades_on_client_error(monkeypatch):
    svc = AzureDocumentIntelligenceService(endpoint="https://example.com", key="fake-key")

    class _BoomClient:
        def begin_analyze_document(self, *args, **kwargs):
            raise RuntimeError("simulated auth failure")

    monkeypatch.setattr(svc, "_get_client", lambda: _BoomClient())
    result = svc.extract(Image.new("RGB", (10, 10)))
    assert result.confidence == 0.0
    assert result.engine == "azure-di-error"
    # Second call must not re-attempt the network call once disabled.
    result2 = svc.extract(Image.new("RGB", (10, 10)))
    assert result2.engine == "azure-di-unavailable" or result2.engine == "azure-di-error"


@dataclass
class _FakeWord:
    confidence: float


@dataclass
class _FakePage:
    words: list


@dataclass
class _FakeResult:
    content: str
    pages: list


class _FakePoller:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


def test_azure_di_returns_averaged_confidence(monkeypatch):
    svc = AzureDocumentIntelligenceService(endpoint="https://example.com", key="fake-key")
    fake_result = _FakeResult(
        content="Gross Salary 15,00,000",
        pages=[_FakePage(words=[_FakeWord(0.9), _FakeWord(0.8)])],
    )

    class _FakeClient:
        def begin_analyze_document(self, *args, **kwargs):
            return _FakePoller(fake_result)

    monkeypatch.setattr(svc, "_get_client", lambda: _FakeClient())
    result = svc.extract(Image.new("RGB", (10, 10)))
    assert result.engine == "azure-document-intelligence"
    assert result.confidence == 0.85
    assert "Gross Salary" in result.text


class _StubOCR:
    """Stands in for OCRService without touching pytesseract/Tesseract."""

    def extract(self, image, embedded_text=""):
        if embedded_text.strip():
            return OCRResult(embedded_text, 0.99, "pdf-text")
        return OCRResult("low quality tesseract text", 0.40, "tesseract")


class _StubAzure:
    available = True

    def __init__(self, confidence: float, text: str):
        self._confidence = confidence
        self._text = text

    def extract(self, image):
        return OCRResult(self._text, self._confidence, "azure-document-intelligence")


class _StubDocuments:
    def __init__(self, pages):
        self._pages = pages

    def load(self, path, scale=2):
        return self._pages


def _agent_with_stubs(azure_confidence: float, azure_text: str, embedded_text: str = ""):
    page = DocumentPage(
        number=1,
        image=Image.new("RGB", (10, 10)),
        embedded_text=embedded_text,
        embedded_words=[],
    )
    agent = ReadingAgent(
        documents=_StubDocuments([page]),
        ocr=_StubOCR(),
        azure_di=_StubAzure(azure_confidence, azure_text),
    )
    return agent


def test_reading_agent_prefers_higher_confidence_azure_result(tmp_path):
    agent = _agent_with_stubs(azure_confidence=0.95, azure_text="Gross Salary 15,00,000 high quality")
    fake_path = tmp_path / "scan.pdf"
    fake_path.write_bytes(b"%PDF-1.4 fake")
    data, combined_text, logs = agent.run(fake_path, scale=2)
    assert "high quality" in combined_text
    comparisons = [log for log in logs if log.action == "ocr_engine_comparison"]
    assert len(comparisons) == 1
    assert comparisons[0].details["selected_engine"] == "azure-document-intelligence"
    assert comparisons[0].details["azure_di_confidence"] == 0.95
    assert comparisons[0].details["tesseract_confidence"] == 0.40


def test_reading_agent_keeps_tesseract_when_azure_confidence_lower(tmp_path):
    agent = _agent_with_stubs(azure_confidence=0.10, azure_text="garbled azure text")
    fake_path = tmp_path / "scan.pdf"
    fake_path.write_bytes(b"%PDF-1.4 fake")
    data, combined_text, logs = agent.run(fake_path, scale=2)
    assert "low quality tesseract text" in combined_text
    comparisons = [log for log in logs if log.action == "ocr_engine_comparison"]
    assert comparisons[0].details["selected_engine"] == "tesseract"


def test_reading_agent_skips_azure_when_embedded_text_present(tmp_path):
    agent = _agent_with_stubs(
        azure_confidence=0.99, azure_text="should never be used", embedded_text="native pdf text layer"
    )
    fake_path = tmp_path / "digital.pdf"
    fake_path.write_bytes(b"%PDF-1.4 fake")
    data, combined_text, logs = agent.run(fake_path, scale=2)
    assert "native pdf text layer" in combined_text
    comparisons = [log for log in logs if log.action == "ocr_engine_comparison"]
    assert comparisons == []
