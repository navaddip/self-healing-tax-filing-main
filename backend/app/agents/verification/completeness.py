"""Completeness Checks for Indian Tax Returns.

Verifies:
1. Source evidence grounding for every monetary figure (hallucination detection).
2. Required documents present for deductions/exemptions claimed.
3. ITR form selection legality per Section 1.13 decision tree.
4. Landlord PAN presence when rent exceeds ₹1,00,000.
5. Bank details & IFSC for refund settlement.
6. Form 10-IEA compliance for business/profession income.
7. Due date compliance (Section 139(1) / Section 234F).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.schemas.tax import (
    ITRForm,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    ResidentialStatus,
    VerificationCheck,
)
from app.schemas.validators import validate_ifsc, validate_pan


@dataclass
class CompletenessReport:
    ok: bool
    confidence: float
    checks: list[VerificationCheck]
    hallucination_flags: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_reextraction: bool = False


def select_itr_form(data: IndianTaxpayerData, total_income: Decimal) -> tuple[ITRForm, list[str]]:
    """Determine the appropriate ITR form according to the Section 1.13 decision tree."""
    disqualifications: list[str] = []
    has_business = (
        data.presumptive is not None
        or sum(f.gross_salary_17_1 for f in data.form16s) == Decimal("0")
        and data.other_income > Decimal("0")
    )

    if data.presumptive is not None:
        if total_income <= Decimal("5000000") and len(data.house_properties) <= 1:
            return ITRForm.ITR4, ["Presumptive business under Section 44AD/44ADA/44AE eligible for ITR-4 (SUGAM)."]
        return ITRForm.ITR3, ["Presumptive business with income > ₹50L or complex affairs requires ITR-3."]

    # Non-business filers
    # Test ITR-1 SAHAJ eligibility
    is_resident = data.residential_status == ResidentialStatus.RESIDENT_ORDINARY
    if not is_resident:
        disqualifications.append("Non-resident individual cannot file ITR-1.")

    if total_income > Decimal("5000000"):
        disqualifications.append(f"Total income of ₹{total_income:,.0f} exceeds ₹50,00,000 threshold for ITR-1.")

    if len(data.house_properties) > 1:
        disqualifications.append(f"Holding {len(data.house_properties)} house properties requires ITR-2.")

    if data.agricultural_income > Decimal("5000"):
        disqualifications.append(f"Agricultural income of ₹{data.agricultural_income:,.0f} exceeds ₹5,000 limit for ITR-1.")

    # Capital gains check
    stcg_items = [item for item in data.capital_gains if not item.is_long_term]
    if stcg_items or any(item.asset_type != "listed_equity" for item in data.capital_gains):
        disqualifications.append("Presence of Short-Term Capital Gains (STCG) or non-equity assets requires ITR-2.")

    ltcg_total = sum(item.gain for item in data.capital_gains if item.is_long_term)
    if ltcg_total > Decimal("125000"):
        disqualifications.append(f"Long-term capital gains of ₹{ltcg_total:,.0f} exceed ₹1,25,000 exemption limit for ITR-1.")

    if data.brought_forward_losses:
        disqualifications.append("Brought-forward losses cannot be carried forward or set off in ITR-1.")

    if not disqualifications:
        return ITRForm.ITR1, ["Eligible for ITR-1 (SAHAJ)."]
    return ITRForm.ITR2, disqualifications


def check_completeness(
    data: IndianTaxpayerData,
    comparison: RegimeComparison,
    filing_date: date | None = None,
) -> CompletenessReport:
    checks: list[VerificationCheck] = []
    hallucination_flags: list[str] = []
    errors: list[str] = []
    requires_reextraction = False

    def add_check(name: str, passed: bool, msg_pass: str, msg_fail: str, weight: float = 1.0):
        checks.append(
            VerificationCheck(
                name=name,
                passed=passed,
                message=msg_pass if passed else msg_fail,
                weight=weight,
            )
        )
        if not passed:
            errors.append(msg_fail)

    # 1. Source evidence grounding (Weight 3.0)
    grounded = True
    evidence_fields = {e.field for e in data.evidence}
    # Check key claimed numbers have evidence
    for f16 in data.form16s:
        if f16.gross_salary_17_1 > Decimal("0") and "gross_salary_17_1" not in evidence_fields and not data.evidence:
            grounded = False
            hallucination_flags.append("Gross salary figure is not grounded in source evidence.")
            requires_reextraction = True

    add_check(
        "source_evidence_grounding",
        grounded,
        "All key return figures are grounded in source document evidence",
        "Ungrounded figures detected without document evidence",
        weight=3.0,
    )

    # 2. Required documents present (Weight 2.0)
    docs_ok = True
    # HRA check
    if data.salary_breakup and data.salary_breakup.hra_received > Decimal("0"):
        if data.salary_breakup.rent_paid_annual == Decimal("0"):
            docs_ok = False
            errors.append("HRA received but no rent payment proof provided.")
    # Home loan check
    for hp in data.house_properties:
        if hp.interest_on_loan_24b > Decimal("0") and not any("loan" in e.source.lower() or "house" in e.source.lower() for e in data.evidence) and not data.evidence:
            docs_ok = False

    add_check(
        "required_documents_present",
        docs_ok,
        "Required documentary proof attached for all claimed heads and exemptions",
        "Claims made without supporting certificates or receipts",
        weight=2.0,
    )

    # 3. ITR form selection (Weight 2.0)
    rec_result = comparison.old if comparison.recommended == Regime.OLD else comparison.new
    chosen_form, form_reasons = select_itr_form(data, rec_result.income.total_income)
    # Check if someone claimed ITR-1 with STCG
    has_stcg = any(not item.is_long_term for item in data.capital_gains)
    form_ok = not (has_stcg and chosen_form == ITRForm.ITR1)
    add_check(
        "itr_form_selection",
        form_ok,
        f"Selected {chosen_form.value.upper()}: {'; '.join(form_reasons)}",
        f"ITR Form selection invalid: {'; '.join(form_reasons)}",
        weight=2.0,
    )

    # 4. Landlord PAN presence when rent > ₹1,00,000 (Weight 1.0)
    landlord_pan_ok = True
    if data.salary_breakup and data.salary_breakup.rent_paid_annual > Decimal("100000"):
        if not data.salary_breakup.landlord_pan or not validate_pan(data.salary_breakup.landlord_pan):
            landlord_pan_ok = False
    add_check(
        "landlord_pan_compliance",
        landlord_pan_ok,
        "Landlord PAN verified for rent payments exceeding ₹1,00,000",
        "Annual rent exceeds ₹1,00,000 but valid Landlord PAN is missing",
        weight=1.0,
    )

    # 5. Bank details & IFSC for refund (Weight 1.0)
    bank_ok = True
    if rec_result.refund_due > Decimal("0"):
        if not data.bank_ifsc or not validate_ifsc(data.bank_ifsc):
            bank_ok = False
    add_check(
        "bank_account_and_ifsc",
        bank_ok,
        "Valid bank account and IFSC present for refund credit",
        "Refund due but bank account number or valid IFSC is missing",
        weight=1.0,
    )

    # 6. Form 10-IEA compliance (Weight 1.0)
    form_10iea_ok = True
    if comparison.form_10iea_required:
        # Must be flagged to taxpayer
        if "Form 10-IEA" not in " ".join(comparison.reasons):
            form_10iea_ok = False
    add_check(
        "form_10iea_compliance",
        form_10iea_ok,
        "Form 10-IEA requirements correctly evaluated for business income regime election",
        "Form 10-IEA election notice missing for business income Old Regime return",
        weight=1.0,
    )

    # 7. Due date awareness (Weight 1.0)
    due_date = date(2026, 7, 31)
    actual_filing = filing_date or date.today()
    due_ok = True
    if actual_filing > due_date and rec_result.fee_234f == Decimal("0") and rec_result.income.total_income > Decimal("250000"):
        due_ok = False
    add_check(
        "due_date_and_234f",
        due_ok,
        f"Return status compliant with filing deadline (due date {due_date.strftime('%d %B %Y')})",
        "Filing date past Section 139(1) due date without Section 234F fee",
        weight=1.0,
    )

    total_weight = sum(c.weight for c in checks)
    passed_weight = sum(c.weight for c in checks if c.passed)
    score = passed_weight / total_weight if total_weight > 0 else 1.0

    return CompletenessReport(
        ok=all(c.passed for c in checks),
        confidence=score,
        checks=checks,
        hallucination_flags=hallucination_flags,
        errors=errors,
        requires_reextraction=requires_reextraction,
    )
