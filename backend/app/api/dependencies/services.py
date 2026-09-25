from functools import lru_cache

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.documentation.agent import DocumentationAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.reading.agent import ReadingAgent
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.remediation.agent import RemediationAgent
from app.agents.verification.agent import VerificationAgent
from app.core.config import get_settings
from app.services.documents.service import DocumentService
from app.services.chroma.service import ChromaService
from app.services.efile import get_backend
from app.services.ocr.azure_di_service import AzureDocumentIntelligenceService
from app.services.ocr.service import OCRService
from app.services.ollama.client import OllamaClient
from app.services.pdf.comparison_report import ProfessionalReportService
from app.services.storage.service import StorageService
from app.workflow.graph import TaxWorkflow


@lru_cache
def get_storage() -> StorageService:
    return StorageService(get_settings().storage_root)


@lru_cache
def get_workflow() -> TaxWorkflow:
    settings = get_settings()
    ollama = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_vision_model,
        settings.ollama_coder_model,
    )
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    checkpoint_connection = sqlite3.connect(str(settings.storage_root / "checkpoints.db"), check_same_thread=False)
    checkpoint_connection.execute("PRAGMA journal_mode=WAL")
    serializer = None
    if settings.checkpoint_encryption_key:
        from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
        serializer = EncryptedSerializer.from_pycryptodome_aes(key=settings.checkpoint_encryption_key.encode())
    def cancelled(submission_id):
        from app.db.session import SessionLocal
        from app.models.submission import WorkflowJob
        with SessionLocal() as db:
            job = db.get(WorkflowJob, submission_id)
            return bool(job and job.status == "cancelled")
    def filing_details(submission_id):
        from app.db.session import SessionLocal
        from app.models.submission import SubmissionRecord
        from app.schemas.tax import FilingDetails
        with SessionLocal() as db:
            record = db.get(SubmissionRecord, submission_id)
            if record and record.filing_details_json:
                return FilingDetails.model_validate_json(record.filing_details_json)
        return None
    return TaxWorkflow(
        cancellation_check=cancelled,
        filing_details_loader=filing_details,
        checkpointer=SqliteSaver(checkpoint_connection, serde=serializer),
        reading=ReadingAgent(
            DocumentService(),
            OCRService(settings.tesseract_cmd),
            ollama=ollama if settings.enable_vision else None,
            azure_di=AzureDocumentIntelligenceService(
                settings.azure_di_endpoint, settings.azure_di_key
            )
            if settings.enable_azure_di
            else None,
        ),
        income_service=IncomeComputationService(),
        old_calculator=OldRegimeCalculator(),
        new_calculator=NewRegimeCalculator(),
        comparison_agent=RegimeComparisonAgent(),
        verification=VerificationAgent(
            threshold=settings.verification_threshold
        ),
        remediation=RemediationAgent(ollama),
        documentation=DocumentationAgent(
            ProfessionalReportService(), get_backend(settings.efile_backend)
        ),
        max_attempts=settings.max_remediation_attempts,
    )
