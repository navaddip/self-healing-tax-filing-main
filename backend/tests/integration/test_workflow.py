"""Exercises the LangGraph Indian Tax self-healing loop with lightweight stub agents.

Validates routing: the verify -> remediate -> (re-extract | recalc) -> verify cycle
and its bounded escape to manual review across the 8-node Indian pipeline.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.schemas.tax import (
    AuditEntry,
    FilingReceipt,
    Form16,
    IndianTaxpayerData,
    TaxesPaid,
    VerificationCheck,
    VerificationResult,
    WorkflowStatus,
)
from app.workflow.graph import TaxWorkflow


def _stub_taxpayer():
    return IndianTaxpayerData(
        name="Workflow Test User",
        pan="ABCPA1234E",
        bank_ifsc="HDFC0001234",
        bank_account_last4="5678",
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Test Employer",
                gross_salary_17_1=Decimal("1500000"),
                tds_deducted=Decimal("145000"),
            )
        ],
        taxes_paid=TaxesPaid(tds_salary=Decimal("145000")),
    )


class StubReading:
    def __init__(self):
        self.calls = 0

    def run_many(self, paths, scale=2):
        self.calls += 1
        return _stub_taxpayer(), "raw text", [
            AuditEntry(agent="reading", action="extract", reason="stub")
        ]

    def run(self, paths):
        self.calls += 1
        return _stub_taxpayer(), "raw text", [
            AuditEntry(agent="reading", action="extract", reason="stub")
        ]


class StubVerifier:
    """Reports invalid for the first ``fail_times`` calls, then valid."""

    def __init__(self, fail_times: int, requires_reextraction: bool):
        self.calls = 0
        self.fail_times = fail_times
        self.requires_reextraction = requires_reextraction

    def run(self, data, comparison, transcript=None, **kwargs):
        self.calls += 1
        valid = self.calls > self.fail_times
        result = VerificationResult(
            valid=valid,
            confidence_score=0.99 if valid else 0.5,
            checks=[VerificationCheck(name="TDS Check", passed=valid, message="Reconciled" if valid else "Mismatch")],
            requires_reextraction=not valid and self.requires_reextraction,
            correctness_ok=valid,
            completeness_ok=valid,
        )
        return result, AuditEntry(agent="verify", action="verify", reason="stub")


class StubRemediation:
    def run(self, data, verification):
        return (
            data,
            verification.requires_reextraction,
            AuditEntry(agent="remediate", action="fix", reason="stub"),
        )


class StubDocumentation:
    def run(self, result, output: Path, preview=None):
        receipt = FilingReceipt(
            submission_id=result.submission_id,
            reference_number="ACK123456789012",
            timestamp=datetime.now(timezone.utc),
            filing_status="accepted",
        )
        return receipt, output, AuditEntry(
            agent="docs", action="generate", reason="stub"
        )


def _workflow(verifier, reading=None, max_attempts=2):
    return TaxWorkflow(
        reading=reading or StubReading(),
        verification=verifier,
        remediation=StubRemediation(),
        documentation=StubDocumentation(),
        max_attempts=max_attempts,
    )


def _state(sub_id="sub-1"):
    return {
        "submission_id": sub_id,
        "original_filename": "form16.pdf",
        "upload_path": Path("form16.pdf"),
        "report_path": Path("report.pdf"),
        "status": WorkflowStatus.PARSING,
        "audit_trail": [],
        "remediation_attempts": 0,
    }


def test_valid_return_completes_immediately():
    wf = _workflow(StubVerifier(fail_times=0, requires_reextraction=False))
    out = wf.run(_state())
    assert out["status"] == WorkflowStatus.COMPLETED or out["status"] == "completed"
    assert out["receipt"] is not None
    ref = out["receipt"].get("reference_number") if isinstance(out["receipt"], dict) else out["receipt"].reference_number
    assert ref == "ACK123456789012"


def test_remediation_then_success_recalculates_without_reextraction():
    reading = StubReading()
    wf = _workflow(
        StubVerifier(fail_times=1, requires_reextraction=False), reading=reading
    )
    out = wf.run(_state("sub-2"))
    assert out["status"] == WorkflowStatus.COMPLETED or out["status"] == "completed"
    assert reading.calls == 1  # recalc path, no re-extraction
    assert out["remediation_attempts"] == 1


def test_reextraction_loop_is_bounded_and_escapes_to_manual_review():
    reading = StubReading()
    wf = _workflow(
        StubVerifier(fail_times=99, requires_reextraction=True),
        reading=reading,
        max_attempts=2,
    )
    out = wf.run(_state("sub-3"))
    assert out["status"] == WorkflowStatus.MANUAL_REVIEW or out["status"] == "manual_review"
    assert reading.calls == 3
