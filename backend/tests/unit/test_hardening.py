from datetime import date
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4
import asyncio
import io
import json
import pytest
import fitz
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.agents.income.computation import apply_chapter_via
from app.agents.regimes.base import interest_and_fees
from app.itr.itr1_builder import ITR1Builder
from app.itr.itr2_builder import ITR2Builder
from app.itr.itr4_builder import ITR4Builder
from app.itr.schema_loader import ITRSchemaLoader, SchemaValidationError
from app.models.submission import Base, WorkflowJob, SubmissionRecord
from app.schemas.tax import IndianTaxpayerData, Regime, TaxesPaid, AgeBand, DonationClaim
from app.services.documents.validation import validate_document
from app.services.storage.service import StorageService
from app.tax_rules.params import get_params

P = get_params("2025-26")

def deductions(data, gti="1000000"):
    return apply_chapter_via(data.deduction_claims, D(gti), D(0), data, Regime.OLD, P)

@pytest.mark.parametrize("builder", [ITR1Builder, ITR2Builder, ITR4Builder])
def test_missing_identity_fails_before_payload(builder):
    with pytest.raises(SchemaValidationError, match="ITR export blocked.*PersonalInfo.DOB.*BankAccountNo"):
        builder().build(IndianTaxpayerData(), None, P)

@pytest.mark.parametrize("form", ["ITR1", "ITR2", "ITR4"])
def test_official_schema_rejects_simplified_mapping(form):
    payload = {"ITR": {form: {f"Form_{form}": {"AssessmentYear": "2026"}}}}
    valid, errors = ITRSchemaLoader().validate(form, payload)
    assert not valid and any("required" in error for error in errors)
    assert not any("unavailable" in error for error in errors)

def test_missing_schema_fails_closed(tmp_path):
    assert not ITRSchemaLoader(tmp_path).validate("ITR1", {}, "2026-27")[0]

def test_tta_actual_interest_and_component_cap():
    data = IndianTaxpayerData(savings_interest=3000, deduction_claims={"80TTA": 10000, "80C": 150000})
    applied, total, rejected, _ = deductions(data, "100000")
    assert total == sum(applied.values()) == D(100000)
    assert rejected["80C"] == D(50000)
    assert deductions(IndianTaxpayerData(savings_interest=3000, deduction_claims={"80TTA": 10000}))[0]["80TTA"] == 3000

def test_80d_separate_limits():
    data = IndianTaxpayerData(deduction_claims={"80D": 100000}, health_self_family=40000,
        health_parents=60000, health_parents_senior=True)
    assert deductions(data)[0]["80D"] == 75000

@pytest.mark.parametrize("first, expected", [(2017, 0), (2018, 25000), (2025, 25000), (2026, 0), (None, 0)])
def test_80e_window(first, expected):
    data = IndianTaxpayerData(deduction_claims={"80E": 25000}, education_loan_first_repayment_fy=first)
    assert deductions(data)[0]["80E"] == expected

def test_80g_percentage_adjusted_limit_and_cash():
    data = IndianTaxpayerData(deduction_claims={"80C": 100000, "80G": 200000}, donations=[
        DonationClaim(amount=200000, percentage=50, qualifying_limit=True, eligible=True),
        DonationClaim(amount=3000, percentage=100, cash=True, eligible=True),
        DonationClaim(amount=10000, percentage=100, qualifying_limit=False, eligible=True)])
    assert deductions(data)[0]["80G"] == 55000

def test_234b_234c_no_advance():
    result = interest_and_fees(D(100000), D(0), date(2026, 7, 31), P.filing_due_date, P,
        data=IndianTaxpayerData(), total_income=D(1500000))
    assert result["interest_234b"] == 4000
    assert result["interest_234c"] == 5050

def test_234c_timely_instalments_and_senior_exemption():
    payments = {"15 June": 15000, "15 September": 30000, "15 December": 30000, "15 March": 25000}
    data = IndianTaxpayerData(taxes_paid=TaxesPaid(advance_tax_instalments=payments))
    result = interest_and_fees(D(100000), D(100000), P.filing_due_date, P.filing_due_date, P, data=data)
    assert result["interest_234b"] == result["interest_234c"] == 0
    data = IndianTaxpayerData(age_band=AgeBand.SENIOR_60_80)
    result = interest_and_fees(D(100000), D(0), P.filing_due_date, P.filing_due_date, P, data=data)
    assert result["interest_234b"] == result["interest_234c"] == 0

def test_year_due_date_and_provisional_pack():
    assert get_params("2026-27").filing_due_date == date(2027, 7, 31)
    assert not get_params("2026-27").verified

def test_invalid_pdf_and_encrypted_pdf(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a PDF")
    with pytest.raises(HTTPException) as error:
        validate_document(path)
    assert error.value.status_code == 422
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    with pytest.raises(HTTPException) as error:
        validate_document(path)
    assert "Password-protected" in error.value.detail

def test_upload_size_failure_removes_file(tmp_path, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 10)
    upload = UploadFile(filename="test.csv", file=io.BytesIO(b"x" * 20))
    with pytest.raises(HTTPException) as error:
        asyncio.run(StorageService(tmp_path).save_upload(str(uuid4()), upload))
    assert error.value.status_code == 413
    assert not list((tmp_path / "uploads").rglob("*.csv"))

@pytest.fixture
def sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()

def test_queue_claim_recovery_and_exclusive_lease(sessions):
    from app.services.jobs import enqueue, claim
    with sessions() as db:
        enqueue(db, "test", {"submission_id": "test"})
        first = claim(db)
        assert first and claim(db) is None
        job = db.get(WorkflowJob, "test")
        job.lease_until = 0
        db.commit()
        second = claim(db)
        assert second[1] != first[1]
        assert db.get(WorkflowJob, "test").attempts == 2

def test_cancelled_jobs_are_never_claimed(sessions):
    from app.services.jobs import enqueue, claim
    with sessions() as db:
        enqueue(db, "test", {})
        db.get(WorkflowJob, "test").status = "cancelled"
        db.commit()
        assert claim(db) is None

def test_api_csv_upload_and_rejection(sessions, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import get_db
    from app.api.dependencies.auth import require_api_key
    from app.api.dependencies.services import get_storage
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_storage] = lambda: StorageService(tmp_path)
    app.dependency_overrides[require_api_key] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/submissions", files={"documents": ("broker.csv", b"isin,buy value,sell value\nABC,100,120", "text/csv")})
            assert response.status_code == 202, response.text
            job_id = response.json()["submission_id"]
            assert response.json()["serial_no"] == 1
            second = client.post("/api/v1/submissions", files={"documents": ("broker.csv", b"isin,buy value,sell value\nABC,100,130", "text/csv")})
            assert second.json()["serial_no"] == 2
            assert client.get(f"/api/v1/submissions/{job_id}").json()["serial_no"] == 1
            with sessions() as db:
                assert db.get(WorkflowJob, job_id).status == "queued"
            rejected = client.post("/api/v1/submissions", files={"documents": ("fake.pdf", b"bad", "application/pdf")})
            assert rejected.status_code == 422
            cancelled = client.post(f"/api/v1/submissions/{job_id}/cancel")
            assert cancelled.status_code == 200
            assert client.post(f"/api/v1/submissions/{job_id}/cancel").status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_worker_persists_result_and_retries(sessions, monkeypatch):
    from app.services import jobs
    from app.api.dependencies import services
    monkeypatch.setattr(jobs, "SessionLocal", sessions)
    class Workflow:
        calls = 0
        def run(self, payload):
            self.calls += 1
            return {"status": "failed" if self.calls == 1 else "completed"}
    workflow = Workflow()
    monkeypatch.setattr(services, "get_workflow", lambda: workflow)
    with sessions() as db:
        db.add(SubmissionRecord(id="retry", original_filename="test.csv", upload_path="test.csv", status="uploaded"))
        jobs.enqueue(db, "retry", {"submission_id": "retry"})
    assert jobs.process_one()
    with sessions() as db:
        job = db.get(WorkflowJob, "retry")
        assert job.status == "queued"
        job.lease_until = 0
        db.commit()
    assert jobs.process_one()
    with sessions() as db:
        assert db.get(WorkflowJob, "retry").status == "completed"
        assert db.get(SubmissionRecord, "retry").status == "completed"

def test_checkpoint_survives_connection_restart(tmp_path):
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict
    class State(TypedDict):
        value: int
    def make(connection):
        graph = StateGraph(State)
        graph.add_node("add", lambda state: {"value": state["value"] + 1})
        graph.add_edge(START, "add")
        graph.add_edge("add", END)
        return graph.compile(checkpointer=SqliteSaver(connection))
    config = {"configurable": {"thread_id": "persisted"}}
    with sqlite3.connect(tmp_path / "checkpoints.db", check_same_thread=False) as connection:
        assert make(connection).invoke({"value": 1}, config)["value"] == 2
    with sqlite3.connect(tmp_path / "checkpoints.db", check_same_thread=False) as connection:
        assert make(connection).get_state(config).values["value"] == 2

def test_report_package_includes_all_sources(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PIL import Image
    from app.services.pdf.comparison_report import ProfessionalReportService
    service = ProfessionalReportService()
    with fitz.open() as document:
        document.new_page()
        report_bytes = document.tobytes()
        document.save(tmp_path / "source.pdf")
    monkeypatch.setattr(service, "generate_pdf", lambda **kwargs: report_bytes)
    Image.new("RGB", (20, 20), "white").save(tmp_path / "image.png")
    (tmp_path / "source.csv").write_text("a,b\n1,2")
    result = SimpleNamespace(extracted_data=None, comparison=None, verification=None, submission_id="package")
    _, path, _ = service.run(result, tmp_path / "package.pdf", [tmp_path / "source.pdf", tmp_path / "image.png", tmp_path / "source.csv"])
    with fitz.open(path) as doc:
        assert doc.page_count == 3
        assert doc.embfile_count() == 1
        assert doc.embfile_get(0) == (tmp_path / "source.csv").read_bytes()

def test_documentation_keeps_advisory_on_blocked_export(tmp_path):
    from types import SimpleNamespace
    from app.agents.documentation.agent import DocumentationAgent
    from app.schemas.tax import FilingReceipt, AuditEntry
    from datetime import datetime, timezone
    class Reports:
        def run(self, result, output, preview):
            output.write_bytes(b"advisory")
            return FilingReceipt(submission_id="test", reference_number="advisory", filing_status="advisory_generated", timestamp=datetime.now(timezone.utc)), output, AuditEntry(agent="report", action="generate", reason="advisory")
    from app.itr.schema_loader import MissingFilingData

    class Export:
        def __init__(self, exc):
            self.exc = exc

        def submit(self, result, output_dir):
            raise self.exc

    def run(exc):
        result = SimpleNamespace(verification=SimpleNamespace(valid=True), receipt=None, audit_trail=[])
        return DocumentationAgent(Reports(), Export(exc)).run(result, tmp_path / "report.pdf")

    receipt, path, log = run(MissingFilingData("ITR export blocked: PersonalInfo.DOB", ["date_of_birth"]))
    assert path.exists() and receipt.filing_status == "advisory_only"
    assert receipt.export_supported is True
    assert "PersonalInfo" not in receipt.instructions and "personal details" in receipt.instructions
    assert "PersonalInfo.DOB" in log.details["filing_export_blocked"]

    receipt, _, _ = run(SchemaValidationError("/ITR/ITR2: additionalProperties constraint failed"))
    assert receipt.filing_status == "advisory_only"
    assert receipt.export_supported is False
    assert "isn't supported" in receipt.instructions
