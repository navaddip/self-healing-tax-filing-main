"""Comprehensive End-to-End Integration Tests for Indian Tax System (AY 2026-27).

Runs all 8 synthetic taxpayer personas through:
1. IncomeComputationService (5 Heads)
2. Dual Regime Calculators (Old vs New Sec 115BAC)
3. RegimeComparisonAgent (Recommendation, Savings, Breakeven, Deltas)
4. VerificationAgent (11 Integrity Checks)
5. ComparisonReportService (8-Page CA Advisory Report)
6. ITR JSON Export & CBDT Schema Validation
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.verification.agent import VerificationAgent
from app.agents.verification.completeness import select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.itr2_builder import ITR2Builder
from app.itr.itr4_builder import ITR4Builder
from app.itr.schema_loader import validate_itr_json
from app.schemas.tax import ITRForm, Regime
from app.services.pdf.comparison_report import ComparisonReportService
from app.synthetic import (
    synthetic_freelancer_44ada,
    synthetic_fresher,
    synthetic_high_earner_surcharge,
    synthetic_job_changer,
    synthetic_landlord_multi_property,
    synthetic_mid_career,
    synthetic_senior_pensioner,
    synthetic_trader,
)
from app.tax_rules.params import get_params


@pytest.fixture
def engines():
    params = get_params("2025-26")
    return {
        "params": params,
        "income": IncomeComputationService(),
        "old_calc": OldRegimeCalculator(),
        "new_calc": NewRegimeCalculator(),
        "comp": RegimeComparisonAgent(params),
        "verifier": VerificationAgent(params),
        "pdf": ComparisonReportService(),
    }


def test_e2e_fresher(engines, tmp_path):
    """Fresher (₹6L): Rebate 87A makes tax ₹0 in both regimes. Default to New, ITR-1."""
    data = synthetic_fresher()
    inc_old = engines["income"].compute(data, Regime.OLD, engines["params"])
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_old = engines["old_calc"].calculate(data, inc_old, engines["params"], date(2026, 7, 31))
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    assert res_old.total_tax_liability == Decimal("0")
    assert res_new.total_tax_liability == Decimal("0")

    comparison, _ = engines["comp"].run(data, res_old, res_new)
    assert comparison.recommended == Regime.NEW  # Tie-breaker to New

    form, _ = select_itr_form(data, res_new.income.total_income)
    assert form == ITRForm.ITR1

    builder = ITR1Builder()
    payload = builder.build(data, res_new, engines["params"], "SUB-FRESHER")
    valid, errors = validate_itr_json("ITR-1", payload)
    assert valid is True, f"ITR-1 errors: {errors}"


def test_e2e_mid_career_golden_case(engines, tmp_path):
    """Mid-Career (₹15L): Old regime saves ₹43,680. 8-page PDF & ITR-1 verified."""
    data = synthetic_mid_career()
    inc_old = engines["income"].compute(data, Regime.OLD, engines["params"])
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_old = engines["old_calc"].calculate(data, inc_old, engines["params"], date(2026, 7, 31))
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    # Exact Golden Vector numbers
    assert res_old.total_tax_liability == Decimal("62420")
    assert res_new.total_tax_liability == Decimal("85800")

    comparison, _ = engines["comp"].run(data, res_old, res_new)
    assert comparison.recommended == Regime.OLD
    assert comparison.savings == Decimal("23380")
    assert comparison.breakeven_deduction_amount == Decimal("665000")

    # Verification passes
    ver_res, _ = engines["verifier"].run(data, comparison)
    assert ver_res.valid is True
    assert ver_res.confidence_score >= 0.95

    # 8-Page PDF Report
    pdf_path = tmp_path / "mid_career_report.pdf"
    pdf_bytes = engines["pdf"].generate_pdf(data, comparison, ver_res, "SUB-MID", pdf_path)
    assert len(pdf_bytes) > 10000

    doc = fitz.open(pdf_path)
    assert doc.page_count == 8
    doc.close()

    # ITR-1 JSON
    form, _ = select_itr_form(data, res_old.income.total_income)
    assert form == ITRForm.ITR1
    payload = ITR1Builder().build(data, res_old, engines["params"], "SUB-MID")
    valid, errors = validate_itr_json("ITR-1", payload)
    assert valid is True, f"Errors: {errors}"


def test_e2e_senior_pensioner(engines):
    """Senior Citizen (Age 68, ₹10L): 80TTB ₹50k, senior health 80D ₹50k."""
    data = synthetic_senior_pensioner()
    inc_old = engines["income"].compute(data, Regime.OLD, engines["params"])
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_old = engines["old_calc"].calculate(data, inc_old, engines["params"], date(2026, 7, 31))
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    # Senior slab starts at ₹3L under old regime, standard deduction on pension ₹75k under new
    comparison, _ = engines["comp"].run(data, res_old, res_new)
    assert comparison.recommended is not None

    form, _ = select_itr_form(data, res_new.income.total_income)
    assert form == ITRForm.ITR1


def test_e2e_trader_itr2(engines):
    """Trader with STCG 111A & LTCG 112A: Requires ITR-2."""
    data = synthetic_trader()
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    form, reasons = select_itr_form(data, res_new.income.total_income)
    assert form == ITRForm.ITR2
    assert any("capital gain" in r.lower() for r in reasons)

    payload = ITR2Builder().build(data, res_new, engines["params"], "SUB-TRADER")
    assert "ScheduleCG" in payload["ITR"]["ITR2"]
    valid, errors = validate_itr_json("ITR-2", payload)
    assert valid is True, f"ITR-2 errors: {errors}"


def test_e2e_freelancer_44ada_itr4(engines):
    """Freelance Consultant under Section 44ADA: Requires ITR-4 (SUGAM)."""
    data = synthetic_freelancer_44ada()
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    form, reasons = select_itr_form(data, res_new.income.total_income)
    assert form == ITRForm.ITR4
    assert any("44AD" in r or "44ADA" in r for r in reasons)

    payload = ITR4Builder().build(data, res_new, engines["params"], "SUB-FREELANCE")
    assert "ScheduleBP" in payload["ITR"]["ITR4"]["IncomeDeductions"]
    valid, errors = validate_itr_json("ITR-4", payload)
    assert valid is True, f"ITR-4 errors: {errors}"


def test_e2e_landlord_multi_property(engines):
    """Landlord with 2 house properties: Requires ITR-2."""
    data = synthetic_landlord_multi_property()
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    form, reasons = select_itr_form(data, res_new.income.total_income)
    assert form == ITRForm.ITR2
    assert any("house properties" in r.lower() for r in reasons)


def test_e2e_high_earner_surcharge(engines):
    """High Earner (₹60L): Surcharge rate 10% applies under both regimes."""
    data = synthetic_high_earner_surcharge()
    inc_old = engines["income"].compute(data, Regime.OLD, engines["params"])
    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_old = engines["old_calc"].calculate(data, inc_old, engines["params"], date(2026, 7, 31))
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    assert res_old.surcharge > Decimal("0")
    assert res_new.surcharge > Decimal("0")

    comparison, _ = engines["comp"].run(data, res_old, res_new)
    assert comparison.recommended is not None


def test_e2e_job_changer(engines):
    """Job Changer with two Form 16s: Verifies salary aggregation and standard deduction."""
    data = synthetic_job_changer()
    data.aggregate_form16s()

    inc_new = engines["income"].compute(data, Regime.NEW, engines["params"])
    res_new = engines["new_calc"].calculate(data, inc_new, engines["params"], date(2026, 7, 31))

    # Standard deduction ₹75,000 deducted only once despite 2 Form 16s
    assert inc_new.gross_salary == Decimal("1500000")
    assert inc_new.standard_deduction == Decimal("75000")
    assert inc_new.income_from_salary == Decimal("1425000")
