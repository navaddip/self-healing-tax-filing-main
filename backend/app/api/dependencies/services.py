from functools import lru_cache

from app.agents.documentation.agent import DocumentationAgent
from app.agents.reading.agent import ReadingAgent
from app.agents.remediation.agent import RemediationAgent
from app.agents.tax_processing.agent import TaxProcessingAgent
from app.agents.tax_processing.tax_calculator import TaxCalculator
from app.agents.verification.agent import VerificationAgent
from app.core.config import get_settings
from app.services.documents.service import DocumentService
from app.services.chroma.service import ChromaService
from app.services.efile import get_backend
from app.services.ocr.service import OCRService
from app.services.ollama.client import OllamaClient
from app.services.pdf.professional_report import ProfessionalReportService
from app.services.storage.service import StorageService
from app.workflow.graph import TaxWorkflow


@lru_cache
def get_storage() -> StorageService:
    return StorageService(get_settings().storage_root)


@lru_cache
def get_workflow() -> TaxWorkflow:
    settings = get_settings()
    calculator = TaxCalculator()
    ollama = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_vision_model,
        settings.ollama_coder_model,
    )
    return TaxWorkflow(
        reading=ReadingAgent(
            DocumentService(),
            OCRService(settings.tesseract_cmd),
            0.0,
            ChromaService(settings.chroma_path),
            w2_extractor=None,
        ),
        processing=TaxProcessingAgent(calculator),
        verification=VerificationAgent(
            calculator, settings.verification_threshold
        ),
        remediation=RemediationAgent(ollama),
        documentation=DocumentationAgent(
            ProfessionalReportService(), get_backend(settings.efile_backend)
        ),
        max_attempts=settings.max_remediation_attempts,
    )
