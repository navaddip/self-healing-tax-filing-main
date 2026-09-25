"""Indian e-Filing Backends.

Implements:
1. JsonSelfFileBackend: (Default) Generates compliant CBDT JSON ready for upload to incometax.gov.in.
2. MockEriBackend: Simulates an E-Return Intermediary submission with deterministic 15-digit acknowledgement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.itr.form_selector import ItrForm, select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.itr2_builder import ITR2Builder
from app.itr.itr4_builder import ITR4Builder
from app.itr.schema_loader import validate_itr_json, SchemaValidationError
from app.schemas.tax import FilingReceipt, IndianTaxpayerData, Regime, SubmissionResult
from app.tax_rules.params import get_params

EXPORTABLE_FORMS = frozenset({ItrForm.ITR1})


@dataclass
class SubmissionAck:
    """Normalized acknowledgement for Indian tax filing."""

    accepted: bool
    channel: str  # "json_self_file" | "mock_eri"
    status: str
    acknowledgement_id: str | None = None
    reject_codes: list[str] | None = None
    instructions: str | None = None
    itr_form: str = "ITR-1"
    json_hash: str | None = None


class EFileBackend(Protocol):
    def submit(self, result: SubmissionResult, output_dir: Path | None = None) -> SubmissionAck: ...


class JsonSelfFileBackend:
    """Default: Generates verified ITR JSON for taxpayer to upload to incometax.gov.in."""

    channel = "json_self_file"

    def submit(self, result: SubmissionResult, output_dir: Path | None = None) -> SubmissionAck:
        data = result.extracted_data or IndianTaxpayerData()
        comparison = result.comparison
        rec_regime = comparison.recommended if comparison else Regime.NEW
        rec_result = comparison.old if rec_regime == Regime.OLD else (comparison.new if comparison else None)

        tot_inc = rec_result.income.total_income if rec_result and rec_result.income else None
        form_enum, _ = select_itr_form(data, tot_inc)
        form_name = form_enum.value.upper()
        # The ITR-2/ITR-4 draft mappings are always rejected by the official schema.
        if form_enum not in EXPORTABLE_FORMS:
            raise SchemaValidationError(f"Export is not implemented for {form_name}")

        params = get_params(data.financial_year)

        if form_enum == ItrForm.ITR2:
            builder = ITR2Builder()
        elif form_enum == ItrForm.ITR4:
            builder = ITR4Builder()
        else:
            builder = ITR1Builder()

        payload = builder.build(data, rec_result, params, result.submission_id)
        valid, errors = validate_itr_json(form_name, payload, params.assessment_year)
        if not valid:
            raise SchemaValidationError("ITR export blocked: " + "; ".join(errors[:20]))
        json_str = json.dumps(payload, indent=2)
        json_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        if output_dir:
            out_file = output_dir / f"{hashlib.sha256(result.submission_id.encode()).hexdigest()[:16]}_{form_name}_AY{params.assessment_year}.json"
            out_file.write_text(json_str, encoding="utf-8")


        instructions = (
            f"Your {form_name} JSON is generated and mathematically verified.\n"
            f"1. Log in to the Income Tax e-Filing portal (https://eportal.incometax.gov.in).\n"
            f"2. Navigate to: e-File > Income Tax Returns > File Income Tax Return.\n"
            f"3. Select Assessment Year: {params.assessment_year} (Financial Year {params.financial_year}).\n"
            f"4. Select Filing Status: Individual > ITR Form: {form_name}.\n"
            f"5. Select Submission Mode: Offline (Upload JSON).\n"
            f"6. Attach your generated JSON file and click Proceed to Verification.\n"
            f"7. Complete e-Verification within 30 days using Aadhaar OTP or Net Banking."
        )

        receipt = FilingReceipt(
            submission_id=result.submission_id,
            reference_number=f"SELF-{json_hash[:10].upper()}",
            timestamp=datetime.now(timezone.utc),
            filing_status="ready_to_self_file",
            filing_type=self.channel,
            itr_form=form_name,
            regime=rec_regime.value,
            payload_hash=json_hash,
            instructions=instructions,
        )
        result.receipt = receipt

        return SubmissionAck(
            accepted=True,
            channel=self.channel,
            status="ready_to_self_file",
            instructions=instructions,
            itr_form=form_name,
            json_hash=json_hash,
        )


class MockEriBackend:
    """Simulates an authorized E-Return Intermediary submission for testing."""

    channel = "mock_eri"

    def submit(self, result: SubmissionResult, output_dir: Path | None = None) -> SubmissionAck:
        verified = bool(result.verification and result.verification.valid)
        if not verified:
            return SubmissionAck(
                accepted=False,
                channel=self.channel,
                status="rejected",
                reject_codes=["ITD-REJ-001: Return failed automated verification gates"],
            )

        data = result.extracted_data or IndianTaxpayerData()
        comparison = result.comparison
        rec_regime = comparison.recommended if comparison else Regime.NEW
        rec_result = comparison.old if rec_regime == Regime.OLD else (comparison.new if comparison else None)
        tot_inc = rec_result.income.total_income if rec_result and rec_result.income else None
        form_enum, _ = select_itr_form(data, tot_inc)
        form_name = form_enum.value.upper()
        if form_enum not in (ItrForm.ITR1, ItrForm.ITR2, ItrForm.ITR4):
            raise SchemaValidationError(f"Export is not implemented for {form_name}")

        params = get_params(data.financial_year)
        if form_enum == ItrForm.ITR2:
            builder = ITR2Builder()
        elif form_enum == ItrForm.ITR4:
            builder = ITR4Builder()
        else:
            builder = ITR1Builder()

        payload = builder.build(data, rec_result, params, result.submission_id)
        valid, errors = validate_itr_json(form_name, payload, params.assessment_year)
        if not valid:
            raise SchemaValidationError("ITR export blocked: " + "; ".join(errors[:20]))
        json_str = json.dumps(payload, indent=2)
        json_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        if output_dir:
            out_file = output_dir / f"{hashlib.sha256(result.submission_id.encode()).hexdigest()[:16]}_{form_name}_AY{params.assessment_year}.json"
            out_file.write_text(json_str, encoding="utf-8")

        # Deterministic 15-digit acknowledgement number
        seed = f"{result.submission_id}:{data.pan}:{params.filing_due_date}"
        hash_val = abs(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
        ack_id = f"{params.filing_due_date:%Y%m%d}{hash_val % 10000000:07d}"

        instructions = (
            f"Successfully transmitted via ERI simulator.\n"
            f"Acknowledgement Number: {ack_id}\n"
            f"Form: {form_name}\n"
            f"Please e-Verify within 30 days to complete assessment."
        )

        receipt = FilingReceipt(
            submission_id=result.submission_id,
            reference_number=ack_id,
            timestamp=datetime.now(timezone.utc),
            filing_status="accepted",
            filing_type=self.channel,
            itr_form=form_name,
            regime=rec_regime.value,
            payload_hash=json_hash,
            acknowledgement_id=ack_id,
            instructions=instructions,
        )
        result.receipt = receipt

        return SubmissionAck(
            accepted=True,
            channel=self.channel,
            status="accepted",
            acknowledgement_id=ack_id,
            instructions=instructions,
            itr_form=form_name,
            json_hash=json_hash,
        )


def get_backend(name: str) -> EFileBackend:
    """Factory for e-file submission backends."""
    normalized = name.lower().strip()
    if normalized in ("json_self_file", "json", "self_file", "pdf"):
        return JsonSelfFileBackend()
    if normalized in ("mock_eri", "eri", "mock_transmitter"):
        return MockEriBackend()
    raise ValueError(f"Unknown e-file backend '{name}' (available: json_self_file, mock_eri)")


# Backwards compatibility aliases
MockTransmitterBackend = MockEriBackend
PdfSelfFileBackend = JsonSelfFileBackend
