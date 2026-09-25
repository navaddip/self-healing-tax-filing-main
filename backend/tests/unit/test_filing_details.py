import json
from datetime import date
from decimal import Decimal as D

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.submissions import _missing_filing_fields
from app.itr.requirements import missing_taxpayer_fields, require_filing_data
from app.itr.schema_loader import MissingFilingData, SchemaValidationError
from app.models.submission import Base, SubmissionRecord, WorkflowJob
from app.repositories.submissions import _redact
from app.schemas.tax import (
    AgeBand, FilingDetails, Form16, IndianTaxpayerData, SubmissionResult, TaxesPaid, age_band_on,
)
from app.services.efile.backends import JsonSelfFileBackend
from app.tax_rules.params import get_params
from app.workflow.graph import TaxWorkflow

P = get_params("2025-26")
DETAILS = dict(
    date_of_birth="1990-05-01", employer_category="OTH", address="Flat 12", locality_or_area="HSR Layout",
    city="Bengaluru", state_code="15", pin_code="560102", mobile="9876543210", email="a@example.com",
    bank_ifsc="hdfc0001234", bank_name="HDFC Bank", bank_account_number="50100123456789",
    father_name="Test Father", verification_place="Bengaluru",
)


def salaried(salary="1500000", **kw):
    return IndianTaxpayerData(
        name="Asha Rao", pan="ABCPA1234E", financial_year="2025-26", assessment_year="2026-27",
        form16s=[Form16(employer_name="Acme", employer_tan="BLRA00123A", gross_salary_17_1=D(salary))], **kw,
    )


# --- validation --------------------------------------------------------------
def test_filing_details_accepts_valid_input_and_normalises_ifsc():
    details = FilingDetails(**DETAILS)
    assert details.bank_ifsc == "HDFC0001234"
    assert details.date_of_birth == date(1990, 5, 1)


@pytest.mark.parametrize("field, bad", [
    ("bank_ifsc", "HDFC123"), ("pin_code", "56010"), ("mobile", "12345"), ("email", "not-an-email"),
    ("bank_account_number", "12AB"), ("employer_category", "PRIVATE"), ("state_code", "Karnataka"), ("state_code", "45"),
    ("date_of_birth", "2999-01-01"),
])
def test_filing_details_rejects_bad_values(field, bad):
    with pytest.raises(ValidationError):
        FilingDetails(**{field: bad})


def test_filing_details_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        FilingDetails(pan="ABCPA1234E")


@pytest.mark.parametrize("dob, band", [
    (date(1990, 5, 1), AgeBand.BELOW_60),
    (date(1966, 3, 31), AgeBand.SENIOR_60_80),   # 60 on 31 Mar 2026
    (date(1966, 4, 2), AgeBand.BELOW_60),        # turns 60 after the FY ends
    (date(1946, 1, 1), AgeBand.SUPER_SENIOR_80_PLUS),
])
def test_age_band_from_date_of_birth(dob, band):
    assert age_band_on(dob, 2025) == band


# --- missing fields ----------------------------------------------------------
def test_missing_taxpayer_details_raise_missing_filing_data_with_keys():
    with pytest.raises(MissingFilingData) as err:
        require_filing_data(salaried(), None, P)
    assert err.value.fields == list(DETAILS)
    assert missing_taxpayer_fields(salaried().model_dump(mode="json")) == list(DETAILS)


def test_other_gaps_are_not_reported_as_fillable():
    data = salaried().model_copy(update=FilingDetails(**DETAILS).provided())
    data.form16s[0].employer_tan = ""
    with pytest.raises(SchemaValidationError) as err:
        require_filing_data(data, None, P)
    assert not isinstance(err.value, MissingFilingData)


def test_only_itr1_is_exported():
    from datetime import date as d
    from app.agents.comparison.agent import RegimeComparisonAgent
    from app.agents.income.computation import IncomeComputationService
    from app.agents.regimes.new_regime import NewRegimeCalculator
    from app.agents.regimes.old_regime import OldRegimeCalculator
    from app.schemas.tax import Regime

    def export(data):
        old = OldRegimeCalculator().calculate(data, IncomeComputationService().compute(data, Regime.OLD, P), P, d(2026, 7, 31))
        new = NewRegimeCalculator().calculate(data, IncomeComputationService().compute(data, Regime.NEW, P), P, d(2026, 7, 31))
        comparison, _ = RegimeComparisonAgent(P).run(data, old, new)
        return JsonSelfFileBackend().submit(SubmissionResult(
            submission_id="t", status="completed", original_filename="f.pdf", extracted_data=data, comparison=comparison))

    full = FilingDetails(**DETAILS).provided()
    assert export(salaried(**full)).itr_form == "ITR-1"
    with pytest.raises(SchemaValidationError, match="not implemented for ITR-2"):
        export(salaried("7500000", **full))


def _state(salary="1500000", status="completed", checks=(), **kw):
    data = salaried(salary, **kw).model_dump(mode="json")
    total = str(int(salary) - 75000)
    return {"status": status, "extracted_data": data,
            "comparison": {"recommended": "new", "new": {"income": {"total_income": total}}},
            "verification": {"checks": list(checks)}}


def test_result_lists_missing_fields_for_itr1_only():
    assert _missing_filing_fields(_state()) == list(DETAILS)
    # ITR-2 (income > 50L): nothing to fill unless a refund needs a bank account
    assert _missing_filing_fields(_state("7500000")) == []
    bank_check = {"name": "bank_account_and_ifsc", "passed": False}
    assert _missing_filing_fields(_state("7500000", "manual_review", [bank_check])) == [
        "bank_ifsc", "bank_name", "bank_account_number"]
    # Nothing to fill once exported, or before processing
    assert _missing_filing_fields({**_state(), "receipt": {"filing_status": "ready_to_self_file"}}) == []
    assert _missing_filing_fields({"status": "uploaded"}) == []


def test_bank_account_and_mobile_are_masked_when_stored():
    stored = _redact({"extracted_data": {"bank_account_number": "50100123456789", "mobile": "9876543210"}})
    assert stored["extracted_data"]["bank_account_number"] == "**********6789"
    assert stored["extracted_data"]["mobile"] == "******3210"


# --- workflow merge ----------------------------------------------------------
def test_parse_merges_details_and_sets_senior_age_band(tmp_path):
    class Reading:
        def run_many(self, paths, scale=2):
            return salaried(), "", []

    details = FilingDetails(**{**DETAILS, "date_of_birth": "1960-01-01"})
    workflow = TaxWorkflow(reading=Reading(), filing_details_loader=lambda sid: details)
    out = workflow._parse({"submission_id": "s", "upload_paths": [str(tmp_path / "f.pdf")], "financial_year": "2025-26"})
    data = out["extracted_data"]
    assert data["age_band"] == "senior_60_80"
    assert data["bank_ifsc"] == "HDFC0001234" and data["bank_account_last4"] == "6789"
    assert data["name"] == "Asha Rao"  # document facts are kept


# --- API ---------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import get_db
    from app.api.dependencies.auth import require_api_key
    from app.api.routes import submissions as routes

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def database():
        with sessions() as db:
            yield db

    deleted = []
    monkeypatch.setattr(routes, "get_workflow", lambda: type("W", (), {
        "checkpointer": type("C", (), {"delete_thread": staticmethod(deleted.append)})()})())
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[require_api_key] = lambda: None
    with sessions() as db:
        db.add(SubmissionRecord(id="s1", serial_no=1, original_filename="f.pdf", upload_path="x",
                                status="completed", result_json=json.dumps(
                                    {"status": "completed", "extracted_data": salaried().model_dump(mode="json")})))
        db.add(WorkflowJob(id="s1", payload="{}", status="completed", attempts=1, lease_until=0))
        db.commit()
    try:
        with TestClient(app) as test_client:
            yield test_client, sessions, deleted
    finally:
        app.dependency_overrides.clear()


def test_api_reports_missing_fields_and_saves_details(client):
    api, sessions, deleted = client
    assert api.get("/api/v1/submissions/s1").json()["missing_filing_fields"] == list(DETAILS)

    bad = api.post("/api/v1/submissions/s1/filing-details", json={"pin_code": "12"})
    assert bad.status_code == 422

    saved = api.post("/api/v1/submissions/s1/filing-details", json={"date_of_birth": "1990-05-01"})
    assert saved.status_code == 200 and saved.json()["status"] == "uploaded"
    assert deleted == ["s1"]
    with sessions() as db:
        assert db.get(WorkflowJob, "s1").status == "queued"
        assert db.get(WorkflowJob, "s1").attempts == 0

    # Busy while re-running
    assert api.post("/api/v1/submissions/s1/filing-details", json={"city": "Pune"}).status_code == 409

    # A later call adds to earlier details instead of replacing them
    with sessions() as db:
        db.get(WorkflowJob, "s1").status = "completed"
        db.commit()
    api.post("/api/v1/submissions/s1/filing-details", json={"city": "Pune"})
    with sessions() as db:
        stored = json.loads(db.get(SubmissionRecord, "s1").filing_details_json)
    assert stored["date_of_birth"] == "1990-05-01" and stored["city"] == "Pune"


def test_api_rejects_empty_and_unknown_submissions(client):
    api, _, _ = client
    assert api.post("/api/v1/submissions/s1/filing-details", json={}).status_code == 422
    assert api.post("/api/v1/submissions/nope/filing-details", json={"city": "Pune"}).status_code == 404
