from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.comparison.agent import RegimeComparisonAgent
from app.api.dependencies.auth import require_api_key
from app.api.dependencies.services import get_storage, get_workflow
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal, get_db
from app.models.submission import SubmissionRecord
from app.repositories.submissions import SubmissionRepository
from app.itr.form_selector import select_itr_form
from app.itr.requirements import missing_taxpayer_fields
from app.schemas import IndianTaxpayerData, SubmissionResult
from app.schemas.tax import FilingDetails, ITRForm
from app.services.documents.service import SUPPORTED_EXTENSIONS
from app.services.storage.service import StorageService
from app.tax_rules.params import get_params


logger = get_logger(__name__)
router = APIRouter(prefix="/submissions", tags=["submissions"])
REPORT_DOWNLOAD_CONFIDENCE_THRESHOLD = get_settings().verification_threshold


def _report_download_eligible(state: dict) -> bool:
    """Only verified reports at or above 97% confidence may be downloaded."""
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return False
    try:
        confidence = float(verification.get("confidence_score", 0))
    except (TypeError, ValueError):
        return False
    return (
        state.get("status") == "completed"
        and bool(verification.get("valid"))
        and confidence >= REPORT_DOWNLOAD_CONFIDENCE_THRESHOLD
    )


@router.post("", response_model=SubmissionResult, status_code=202)
async def create_submission(
    documents: list[UploadFile] = File(...),
    financial_year: str = Form("2025-26"),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: None = Depends(require_api_key),
):
    try:
        params = get_params(financial_year)
        if not params.verified:
            raise ValueError("Selected financial year is provisional and unavailable for verified reports")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if len(documents) > get_settings().max_upload_documents:
        raise HTTPException(413, "Too many documents in one submission")
    if not documents:
        raise HTTPException(422, "Upload at least one document")
    for doc in documents:
        if Path(doc.filename or "").suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(415, "Upload PDF, PNG, JPG, JPEG, or CSV documents")
    submission_id = str(uuid4())
    upload_paths = []
    try:
        for doc in documents:
            upload_paths.append(str(await storage.save_upload(submission_id, doc)))
    except Exception:
        for path in upload_paths:
            Path(path).unlink(missing_ok=True)
        raise
    original_filename = ", ".join(
        doc.filename or Path(p).name for doc, p in zip(documents, upload_paths)
    )
    report_path = storage.report_path(submission_id)
    from app.services.jobs import enqueue
    payload = {
        "submission_id": submission_id, "original_filename": original_filename,
        "financial_year": params.financial_year,
        "upload_path": upload_paths[0], "upload_paths": upload_paths,
        "report_path": str(report_path), "status": "parsing",
        "audit_trail": [], "remediation_attempts": 0,
    }
    # A concurrent upload can take the same next number; the unique index rejects it and we retry.
    for attempt in range(3):
        record = SubmissionRecord(
            id=submission_id,
            serial_no=(db.scalar(select(func.max(SubmissionRecord.serial_no))) or 0) + 1,
            original_filename=original_filename,
            upload_path=upload_paths[0],
            report_path=str(report_path),
            status="uploaded",
        )
        db.add(record)
        try:
            enqueue(db, submission_id, payload)
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
    return _to_result(record, {"status": "uploaded"})


@router.get("/{submission_id}", response_model=SubmissionResult)
def get_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    record = SubmissionRepository(db).get(submission_id)
    if not record:
        raise HTTPException(404, "Submission not found")
    state = json.loads(record.result_json) if record.result_json else {}
    return _to_result(record, state)


class SensitivityRequest(BaseModel):
    deltas: list[Decimal] = Field(default_factory=list)
    delta: Decimal | None = None



@router.get("/{submission_id}/report")
def download_report(
    submission_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    record = SubmissionRepository(db).get(submission_id)
    state = json.loads(record.result_json) if record and record.result_json else {}
    if (
        not record
        or not record.report_path
        or not _report_download_eligible(state)
    ):
        raise HTTPException(404, "Completed report not found")
    path = Path(record.report_path)
    if not path.exists():
        raise HTTPException(404, "Report file not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"tax-filing-report-{submission_id}.pdf",
    )


@router.get("/{submission_id}/itr-json")
def download_itr_json(
    submission_id: str,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: None = Depends(require_api_key),
):
    record = SubmissionRepository(db).get(submission_id)
    if not record:
        raise HTTPException(404, "Submission not found")
    state = json.loads(record.result_json) if record.result_json else {}
    data = state.get("extracted_data") or {}
    assessment_year = get_params(data.get("financial_year", get_settings().tax_year)).assessment_year
    if (state.get("receipt") or {}).get("filing_status") != "ready_to_self_file":
        raise HTTPException(409, (state.get("receipt") or {}).get("instructions") or "Filing export has not passed official schema validation")

    path = storage.itr_json_path(submission_id)
    if not path.exists() and record.report_path:
        candidates = list(Path(record.report_path).parent.glob(f"*AY{assessment_year}.json"))
        if candidates:
            path = candidates[0]

    if not path.exists():
        raise HTTPException(
            404,
            "ITR JSON return file not found. Ensure verification completed successfully.",
        )

    return FileResponse(
        path,
        media_type="application/json",
        filename=f"Return_AY{assessment_year}.json",
    )


@router.get("/{submission_id}/audit")
def download_audit_trail(
    submission_id: str,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: None = Depends(require_api_key),
):
    record = SubmissionRepository(db).get(submission_id)
    if not record:
        raise HTTPException(404, "Submission not found")
    state = json.loads(record.result_json) if record.result_json else {}
    path = storage.audit_path(submission_id)
    if path.exists():
        return FileResponse(
            path,
            media_type="application/json",
            filename=f"audit-trail-{submission_id}.json",
        )
    return JSONResponse(state.get("audit_trail", []))


@router.post("/{submission_id}/sensitivity")
def compute_sensitivity(
    submission_id: str,
    payload: SensitivityRequest | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    record = SubmissionRepository(db).get(submission_id)
    if not record:
        raise HTTPException(404, "Submission not found")
    state = json.loads(record.result_json) if record.result_json else {}
    data_dict = state.get("extracted_data")
    if not data_dict:
        raise HTTPException(400, "Submission has no extracted taxpayer data")

    data = IndianTaxpayerData.model_validate(data_dict)
    params = get_params(data.financial_year)
    agent = RegimeComparisonAgent(params)

    deltas = payload.deltas if payload and payload.deltas else []
    if payload and payload.delta is not None and not deltas:
        deltas = [payload.delta]
    if not deltas:
        deltas = [
            Decimal("0"),
            Decimal("25000"),
            Decimal("50000"),
            Decimal("100000"),
            Decimal("150000"),
        ]

    results = agent.sensitivity(data, params, deltas)
    return {"submission_id": submission_id, "sensitivity": results}


def _to_result(record: SubmissionRecord, state: dict) -> SubmissionResult:
    assessment_year = get_params((state.get("extracted_data") or {}).get("financial_year", get_settings().tax_year)).assessment_year
    report_exists = (
        _report_download_eligible(state)
        and bool(record.report_path)
        and Path(record.report_path).exists()
    )
    itr_path = (
        Path(record.report_path).parent / "itr_return.json"
        if record.report_path
        else None
    )
    itr_exists = itr_path.exists() if itr_path else False
    if not itr_exists and record.report_path:
        itr_exists = (
            len(list(Path(record.report_path).parent.glob(f"*AY{assessment_year}.json")))
            > 0
        )

    itr_exists = itr_exists and (state.get("receipt") or {}).get("filing_status") == "ready_to_self_file"
    return SubmissionResult.model_validate(
        {
            "submission_id": record.id,
            "serial_no": record.serial_no,
            "status": state.get("status", record.status),
            "original_filename": record.original_filename,
            "extracted_data": state.get("extracted_data"),
            "comparison": state.get("comparison") or state.get("calculation"),
            "verification": state.get("verification"),
            "audit_trail": state.get("audit_trail", []),
            "receipt": state.get("receipt"),
            "report_url": (
                f"/api/v1/submissions/{record.id}/report"
                if report_exists
                else None
            ),
            "itr_json_url": (
                f"/api/v1/submissions/{record.id}/itr-json"
                if itr_exists
                else None
            ),
            "audit_url": f"/api/v1/submissions/{record.id}/audit",
            "error": state.get("error"),
            "missing_filing_fields": _missing_filing_fields(state),
        }
    )


BANK_FIELDS = ("bank_ifsc", "bank_name", "bank_account_number")


def _missing_filing_fields(state: dict) -> list[str]:
    """Details the taxpayer can still add: all ITR-1 gaps, or only bank details a refund needs."""
    data = state.get("extracted_data")
    receipt = state.get("receipt") or {}
    if (
        state.get("status") not in ("completed", "manual_review")
        or not data
        or receipt.get("filing_status") == "ready_to_self_file"
        or receipt.get("export_supported") is False
    ):
        return []
    missing = missing_taxpayer_fields(data)
    comparison = state.get("comparison") or {}
    rec = comparison.get(comparison.get("recommended", "new")) or {}
    total_income = Decimal(str((rec.get("income") or {}).get("total_income", "0")))
    form, _ = select_itr_form(IndianTaxpayerData.model_validate(data), total_income)
    if form == ITRForm.ITR1:
        return missing
    refund_blocked = any(
        c.get("name") == "bank_account_and_ifsc" and not c.get("passed")
        for c in (state.get("verification") or {}).get("checks", [])
    )
    return [f for f in missing if f in BANK_FIELDS] if refund_blocked else []


@router.post("/{submission_id}/filing-details", response_model=SubmissionResult)
def save_filing_details(
    submission_id: str,
    details: FilingDetails,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
):
    from app.models.submission import WorkflowJob
    record = SubmissionRepository(db).get(submission_id)
    job = db.get(WorkflowJob, submission_id)
    if not record or not job:
        raise HTTPException(404, "Submission not found")
    if job.status in ("queued", "running"):
        raise HTTPException(409, "This submission is still processing; try again when it finishes")
    if not details.provided():
        raise HTTPException(422, "Enter at least one detail")
    existing = FilingDetails.model_validate_json(record.filing_details_json).provided() if record.filing_details_json else {}
    record.filing_details_json = FilingDetails(**(existing | details.provided())).model_dump_json()

    # Re-run from the original uploads (stored results hold a masked PAN) on a fresh checkpoint thread.
    get_workflow().checkpointer.delete_thread(submission_id)
    job.status, job.attempts, job.lease_until, job.token = "queued", 0, 0, None
    state = json.loads(record.result_json) if record.result_json else {}
    state = {**state, "status": "uploaded", "error": None}
    SubmissionRepository(db).save_result(record, state)
    return _to_result(record, state)



@router.post("/{submission_id}/cancel")
def cancel_submission(submission_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)):
    from app.models.submission import WorkflowJob
    job = db.get(WorkflowJob, submission_id)
    if not job:
        raise HTTPException(404, "Submission job not found")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(409, "Processing already finished")
    job.status = "cancelled"
    record = db.get(SubmissionRecord, submission_id)
    if record:
        SubmissionRepository(db).save_result(record, {"status": "failed", "error": "Cancelled by user"})
    db.commit()
    return {"status": "cancelled"}
