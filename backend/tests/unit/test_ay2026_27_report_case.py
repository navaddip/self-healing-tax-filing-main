from datetime import date
from decimal import Decimal

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.schemas.tax import AgeBand, Form16, IndianTaxpayerData, Regime, ResidentialStatus, TaxesPaid
from app.services.pdf.validation import validate_report_model
from app.tax_rules.params import get_params


def _case():
    return IndianTaxpayerData(
        name="AY 2026-27 Form 16 Case",
        pan="ABCDE1234F",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        assessment_year="2026-27",
        financial_year="2025-26",
        form16s=[Form16(
            gross_salary_17_1=Decimal("1800000"),
            exempt_allowances_10={"HRA": Decimal("300000")},
            professional_tax=Decimal("2400"),
            reported_house_property_loss=Decimal("200000"),
            tds_deducted=Decimal("114420"),
        )],
        deduction_claims={
            "80C": Decimal("150000"),
            "80CCD1B": Decimal("50000"),
            "80D": Decimal("25000"),
            "80E": Decimal("25000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("114420")),
    )


def test_ay2026_27_form16_canonical_results():
    params = get_params("AY_2026_27")
    data = _case()
    income = IncomeComputationService()
    old_income = income.compute(data, Regime.OLD, params)
    new_income = income.compute(data, Regime.NEW, params)
    old = OldRegimeCalculator().calculate(data, old_income, params, date(2026, 7, 31))
    new = NewRegimeCalculator().calculate(data, new_income, params, date(2026, 7, 31))
    comparison, _ = RegimeComparisonAgent(params).run(data, old, new)

    assert old_income.income_from_salary == Decimal("1447600")
    assert old_income.gross_total_income == Decimal("1247600")
    assert old_income.chapter_via_total == Decimal("225000")
    assert old_income.chapter_via["80E"] == Decimal("0")
    assert old_income.total_income == Decimal("1022600")
    assert old.tax_before_rebate == Decimal("119280")
    assert old.cess == Decimal("4771.20")
    assert old.total_tax_liability == Decimal("124050")
    assert old.tax_payable == Decimal("9630")

    assert new_income.total_income == Decimal("1725000")
    assert new.tax_before_rebate == Decimal("145000")
    assert new.cess == Decimal("5800")
    assert new.total_tax_liability == Decimal("150800")
    assert new.tax_payable == Decimal("39662")
    assert comparison.savings == Decimal("26750")
    assert sum(comparison.deductions_forfeited_if_new.values()) == Decimal("727400")
    assert comparison.current_old_total_reductions == Decimal("777400")
    assert comparison.breakeven_deduction_amount == Decimal("691667")
    assert sum(Decimal(str(c["tax"])) for c in new.slab_components) == new.tax_before_rebate
    assert validate_report_model(data, comparison, params) == []
