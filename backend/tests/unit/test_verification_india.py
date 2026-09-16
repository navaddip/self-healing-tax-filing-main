"""Unit tests for Milestones 7 & 8: Verification Agent & Remediation Loop for India."""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.remediation.agent import RemediationAgent
from app.agents.verification.agent import VerificationAgent
from app.agents.verification.completeness import select_itr_form
from app.schemas.tax import (
    AgeBand,
    CapitalGainItem,
    Form16,
    HouseProperty,
    ITRForm,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
    SourceEvidence,
    TaxesPaid,
)
from app.tax_rules.params import get_params


@pytest.fixture
def params():
    return get_params("2025-26")


@pytest.fixture
def verification_agent(params):
    return VerificationAgent(threshold=0.95, params=params)


@pytest.fixture
def remediation_agent():
    return RemediationAgent()


@pytest.fixture
def golden_data():
    return IndianTaxpayerData(
        name="Mid-Career Salaried",
        pan="ABCPS1234F",
        bank_ifsc="HDFC0001234",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Tech Corp India",
                employer_tan="BLRT12345A",
                gross_salary_17_1=Decimal("1500000"),
                professional_tax=Decimal("2400"),
                tds_deducted=Decimal("145000"),
            )
        ],
        salary_breakup=SalaryBreakup(
            basic=Decimal("900000"),
            hra_received=Decimal("360000"),
            rent_paid_annual=Decimal("290000"),
            landlord_pan="AAABT1234F",
            is_metro=False,
        ),
        house_properties=[
            HouseProperty(
                is_self_occupied=True,
                interest_on_loan_24b=Decimal("200000"),
            )
        ],
        savings_interest=Decimal("15000"),
        deduction_claims={
            "80C": Decimal("150000"),
            "80D": Decimal("25000"),
            "80CCD1B": Decimal("50000"),
            "80CCD2": Decimal("90000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("145000")),
        evidence=[
            SourceEvidence(
                field="gross_salary_17_1",
                page=1,
                raw_text="Salary: Rs 15,00,000",
                confidence=0.99,
            ),
            SourceEvidence(
                field="tds_salary",
                page=1,
                raw_text="TDS: Rs 1,45,000",
                confidence=0.99,
            ),
        ],
        field_confidence={
            "gross_salary_17_1": 0.99,
            "tds_salary": 0.99,
        },
    )


def test_golden_return_passes_verification(params, verification_agent, golden_data):
    """A clean golden return scores >= 0.95 and passes."""
    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(golden_data, Regime.OLD, params)
    inc_new = inc_svc.compute(golden_data, Regime.NEW, params)

    res_old = old_calc.calculate(golden_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(golden_data, inc_new, params, date(2026, 7, 31))

    comparison, _ = comp_agent.run(golden_data, res_old, res_new)
    result, audit = verification_agent.run(golden_data, comparison)

    assert result.valid is True
    assert result.confidence_score >= 0.95
    assert result.correctness_ok is True
    assert result.completeness_ok is True


def test_recomputation_mismatch_detected(params, verification_agent, golden_data):
    """A return whose stored tax is off by ₹100 fails recomputation."""
    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(golden_data, Regime.OLD, params)
    inc_new = inc_svc.compute(golden_data, Regime.NEW, params)

    res_old = old_calc.calculate(golden_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(golden_data, inc_new, params, date(2026, 7, 31))

    # Artificially tamper with stored tax liability by ₹100
    res_old_corrupt = res_old.model_copy(deep=True)
    res_old_corrupt.total_tax_liability += Decimal("100")

    comparison, _ = comp_agent.run(golden_data, res_old_corrupt, res_new)
    result, audit = verification_agent.run(golden_data, comparison)

    assert result.valid is False
    assert result.correctness_ok is False
    assert any(c.name == "deterministic_recomputation" and not c.passed for c in result.checks)


def test_tds_mismatch_against_26as_fails(params, verification_agent, golden_data):
    """A return with a ₹5,000 TDS mismatch against 26AS fails reconciliation."""
    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    # Invalidate 26AS TDS (26AS reports 140,000 instead of 145,000 claimed)
    corrupted_data = golden_data.model_copy(deep=True)
    corrupted_data.taxes_paid.tds_salary = Decimal("140000")

    inc_old = inc_svc.compute(corrupted_data, Regime.OLD, params)
    inc_new = inc_svc.compute(corrupted_data, Regime.NEW, params)

    res_old = old_calc.calculate(corrupted_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(corrupted_data, inc_new, params, date(2026, 7, 31))

    comparison, _ = comp_agent.run(corrupted_data, res_old, res_new)
    result, audit = verification_agent.run(corrupted_data, comparison)

    assert result.valid is False
    assert any(c.name == "tds_26as_reconciliation" and not c.passed for c in result.checks)
    assert result.requires_reextraction is True


def test_deduction_legality_fails_on_injected_80c(params, verification_agent, golden_data):
    """A return with 80C injected into New Regime result fails deduction legality."""
    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(golden_data, Regime.OLD, params)
    inc_new = inc_svc.compute(golden_data, Regime.NEW, params)

    res_old = old_calc.calculate(golden_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(golden_data, inc_new, params, date(2026, 7, 31))

    # Inject 80C illegally into New Regime
    res_new_corrupt = res_new.model_copy(deep=True)
    res_new_corrupt.income.chapter_via["80C"] = Decimal("150000")

    comparison, _ = comp_agent.run(golden_data, res_old, res_new_corrupt)
    result, _ = verification_agent.run(golden_data, comparison)

    assert result.valid is False
    assert any(c.name == "deduction_legality" and not c.passed for c in result.checks)


def test_itr_form_selector_rejects_stcg_for_itr1(golden_data):
    """ITR-1 selector rejects presence of STCG and names STCG."""
    data_with_stcg = golden_data.model_copy(deep=True)
    data_with_stcg.capital_gains.append(
        CapitalGainItem(
            asset_type="listed_equity",
            acquisition_date=date(2026, 1, 1),
            transfer_date=date(2026, 2, 1),
            cost_of_acquisition=Decimal("100000"),
            sale_consideration=Decimal("120000"),
        )
    )

    form, reasons = select_itr_form(data_with_stcg, Decimal("1000000"))
    assert form == ITRForm.ITR2
    assert any("STCG" in r for r in reasons)


def test_remediation_heals_tds_mismatch(golden_data, remediation_agent, verification_agent, params):
    """Remediation heals a TDS mismatch in 1 pass by adopting 26AS."""
    # Data with mismatch: Form 16 claims 150,000, 26AS shows 145,000
    mismatch_data = golden_data.model_copy(deep=True)
    mismatch_data.form16s[0].tds_deducted = Decimal("150000")
    mismatch_data.taxes_paid.tds_salary = Decimal("145000")

    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(mismatch_data, Regime.OLD, params)
    inc_new = inc_svc.compute(mismatch_data, Regime.NEW, params)
    res_old = old_calc.calculate(mismatch_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(mismatch_data, inc_new, params, date(2026, 7, 31))
    comparison, _ = comp_agent.run(mismatch_data, res_old, res_new)

    ver_res, _ = verification_agent.run(mismatch_data, comparison)
    assert ver_res.valid is False

    # Apply remediation
    healed_data, needs_reextraction, audit = remediation_agent.run(mismatch_data, ver_res)

    assert healed_data.form16s[0].tds_deducted == Decimal("145000")
    assert "Overrode Form 16 TDS" in " ".join(audit.details["actions"])


def test_remediation_caps_80c_excess(golden_data, remediation_agent, verification_agent, params):
    """Remediation caps an excess 80C claim at ₹1,50,000."""
    excess_data = golden_data.model_copy(deep=True)
    excess_data.deduction_claims["80C"] = Decimal("250000")

    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(excess_data, Regime.OLD, params)
    inc_new = inc_svc.compute(excess_data, Regime.NEW, params)
    res_old = old_calc.calculate(excess_data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(excess_data, inc_new, params, date(2026, 7, 31))
    comparison, _ = comp_agent.run(excess_data, res_old, res_new)

    ver_res, _ = verification_agent.run(excess_data, comparison)

    # Remediation enforces ₹1,50,000 cap
    healed_data, _, audit = remediation_agent.run(excess_data, ver_res)
    assert healed_data.deduction_claims["80C"] == Decimal("150000")
