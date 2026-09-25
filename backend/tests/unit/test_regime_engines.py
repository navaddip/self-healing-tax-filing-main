from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.schemas.tax import (
    AgeBand,
    CapitalGainItem,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
    TaxesPaid,
)
from app.tax_rules.params import get_params


@pytest.fixture
def params():
    return get_params("2025-26")


@pytest.fixture
def income_service():
    return IncomeComputationService()


@pytest.fixture
def old_calc():
    return OldRegimeCalculator()


@pytest.fixture
def new_calc():
    return NewRegimeCalculator()


def test_golden_case_1_mid_career_salaried(income_service, old_calc, new_calc, params):
    """Case 1: Mid-career salaried, heavy old-regime claims -> OLD wins."""
    f16 = Form16(
        gross_salary_17_1=Decimal("1500000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("145000"),
    )
    sb = SalaryBreakup(
        basic=Decimal("900000"),
        dearness_allowance=Decimal("0"),
        hra_received=Decimal("240000"),
        rent_paid_annual=Decimal("290000"),
        is_metro=True,
    )
    hp = HouseProperty(is_self_occupied=True, interest_on_loan_24b=Decimal("200000"))
    data = IndianTaxpayerData(
        form16s=[f16],
        salary_breakup=sb,
        house_properties=[hp],
        savings_interest=Decimal("15000"),
        deduction_claims={
            "80C": Decimal("150000"),
            "80D": Decimal("25000"),
            "80CCD1B": Decimal("50000"),
            "80CCD2": Decimal("90000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("145000")),
    )
    # HRA exemption: rent (2,60,000) - 10% basic (60,000) = 2,00,000
    inc_old = income_service.compute(data, Regime.OLD, params)
    assert inc_old.gross_salary == Decimal("1500000")
    assert inc_old.exempt_allowances == Decimal("200000")
    assert inc_old.standard_deduction == Decimal("50000")
    assert inc_old.professional_tax == Decimal("2400")
    assert inc_old.income_from_salary == Decimal("1247600")
    assert inc_old.hp_loss_set_off == Decimal("200000")
    assert inc_old.other_sources_income == Decimal("15000")
    assert inc_old.gross_total_income == Decimal("1062600")
    assert inc_old.chapter_via_total == Decimal("325000")
    assert inc_old.total_income == Decimal("737600")

    res_old = old_calc.calculate(data, inc_old, params)
    assert res_old.tax_on_slab_income == Decimal("60020")
    assert res_old.rebate_87a == Decimal("0")
    assert res_old.total_tax_liability == Decimal("62420")
    assert res_old.refund_due == Decimal("82580")

    inc_new = income_service.compute(data, Regime.NEW, params)
    assert inc_new.gross_salary == Decimal("1500000")
    assert inc_new.exempt_allowances == Decimal("0")
    assert inc_new.standard_deduction == Decimal("75000")
    assert inc_new.professional_tax == Decimal("0")
    assert inc_new.income_from_salary == Decimal("1425000")
    assert inc_new.hp_loss_set_off == Decimal("0")
    assert inc_new.gross_total_income == Decimal("1440000")
    assert inc_new.chapter_via_total == Decimal("90000")
    assert inc_new.total_income == Decimal("1350000")

    res_new = new_calc.calculate(data, inc_new, params)
    assert res_new.tax_on_slab_income == Decimal("82500")
    assert res_new.total_tax_liability == Decimal("85800")
    assert res_new.refund_due == Decimal("59200")

    # Savings = 85,800 - 62,420 = 23,380
    savings = res_new.total_tax_liability - res_old.total_tax_liability
    assert savings == Decimal("23380")


def test_golden_case_2_salaried_thin_claims(income_service, old_calc, new_calc, params):
    """Case 2: Salaried ₹12,00,000, thin claims -> NEW wins."""
    f16 = Form16(gross_salary_17_1=Decimal("1200000"))
    data = IndianTaxpayerData(
        form16s=[f16],
        deduction_claims={"80C": Decimal("50000")},
    )
    inc_old = income_service.compute(data, Regime.OLD, params)
    assert inc_old.total_income == Decimal("1100000")
    res_old = old_calc.calculate(data, inc_old, params)
    assert res_old.tax_on_slab_income == Decimal("142500")
    assert res_old.total_tax_liability == Decimal("148200")

    inc_new = income_service.compute(data, Regime.NEW, params)
    assert inc_new.total_income == Decimal("1125000")
    res_new = new_calc.calculate(data, inc_new, params)
    assert res_new.tax_on_slab_income == Decimal("52500")
    assert res_new.rebate_87a == Decimal("52500")
    assert res_new.total_tax_liability == Decimal("0")

    savings = res_old.total_tax_liability - res_new.total_tax_liability
    assert savings == Decimal("148200")


@pytest.mark.parametrize(
    "total_income, expected_tax_after_relief, expected_total_tax",
    [
        (Decimal("1200000"), Decimal("0"), Decimal("0")),
        (Decimal("1210000"), Decimal("10000"), Decimal("10400")),
        (Decimal("1250000"), Decimal("50000"), Decimal("52000")),
        (Decimal("1270588"), Decimal("70588"), Decimal("73412")),
        (Decimal("1275000"), Decimal("71250"), Decimal("74100")),
        (Decimal("1300000"), Decimal("75000"), Decimal("78000")),
    ],
)
def test_golden_case_3_marginal_relief_band(
    new_calc, params, total_income, expected_tax_after_relief, expected_total_tax
):
    """Case 3: Section 87A marginal relief band under the new regime."""
    from app.schemas.tax import HeadwiseIncome

    data = IndianTaxpayerData()
    inc = HeadwiseIncome(
        regime=Regime.NEW,
        gross_total_income=total_income,
        total_income=total_income,
    )
    res = new_calc.calculate(data, inc, params)
    assert res.tax_after_rebate == expected_tax_after_relief
    tax_with_cess = (res.tax_after_rebate + res.cess).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    assert tax_with_cess == expected_total_tax


def test_golden_case_4_surcharge_and_capital_gains(
    income_service, old_calc, new_calc, params
):
    """Case 4: Surcharge plus capital gains, total income ₹60,00,000."""
    f16 = Form16(gross_salary_17_1=Decimal("5050000"))
    cg = CapitalGainItem(
        asset_type="listed_equity",
        acquisition_date=date(2023, 1, 1),
        transfer_date=date(2025, 6, 1),
        sale_consideration=Decimal("1125000"),
        cost_of_acquisition=Decimal("0"),
        stt_paid=True,
    )
    # Gross 112A gain = 11,25,000 -> taxable = 10,00,000
    data = IndianTaxpayerData(form16s=[f16], capital_gains=[cg])

    inc_old = income_service.compute(data, Regime.OLD, params)
    # Gross salary 50,50,000 - 50,000 std ded = 50,00,000 normal
    # 112A taxable = 10,00,000. Total income = 60,00,000
    assert inc_old.total_income == Decimal("6000000")
    res_old = old_calc.calculate(data, inc_old, params)
    assert res_old.tax_on_slab_income == Decimal("1312500")
    assert res_old.tax_on_special_income == Decimal("125000")
    assert res_old.surcharge == Decimal("143750")
    assert res_old.cess == Decimal("63250")
    assert res_old.total_tax_liability == Decimal("1644500")

    # In NEW regime: salary 50,75,000 - 75,000 std ded = 50,00,000 normal
    f16_new = Form16(gross_salary_17_1=Decimal("5075000"))
    data_new = IndianTaxpayerData(form16s=[f16_new], capital_gains=[cg])
    inc_new = income_service.compute(data_new, Regime.NEW, params)
    assert inc_new.total_income == Decimal("6000000")
    res_new = new_calc.calculate(data_new, inc_new, params)
    assert res_new.tax_on_slab_income == Decimal("1080000")
    assert res_new.tax_on_special_income == Decimal("125000")
    assert res_new.surcharge == Decimal("120500")
    assert res_new.cess == Decimal("53020")
    assert res_new.total_tax_liability == Decimal("1378520")


def test_golden_case_5_senior_citizen_pensioner(
    income_service, old_calc, new_calc, params
):
    """Case 5: Senior citizen pensioner, pension ₹9,00,000."""
    f16 = Form16(gross_salary_17_1=Decimal("900000"))
    data = IndianTaxpayerData(
        age_band=AgeBand.SENIOR_60_80,
        form16s=[f16],
        deduction_claims={"80D": Decimal("50000"), "80TTB": Decimal("50000")},
    )
    inc_old = income_service.compute(data, Regime.OLD, params)
    assert inc_old.total_income == Decimal("800000")
    assert inc_old.chapter_via["80TTB"] == 0  # no qualifying interest declared
    res_old = old_calc.calculate(data, inc_old, params)
    assert res_old.tax_on_slab_income == Decimal("70000")
    assert res_old.rebate_87a == Decimal("0")
    assert res_old.total_tax_liability == Decimal("72800")

    inc_new = income_service.compute(data, Regime.NEW, params)
    assert inc_new.total_income == Decimal("825000")
    res_new = new_calc.calculate(data, inc_new, params)
    assert res_new.tax_on_slab_income == Decimal("22500")
    assert res_new.rebate_87a == Decimal("22500")
    assert res_new.total_tax_liability == Decimal("0")


@pytest.mark.parametrize(
    "total_income, expected_surcharge, expected_total_tax",
    [
        (Decimal("5000000"), Decimal("0"), Decimal("1123200")),
        (Decimal("5050000"), Decimal("35000"), Decimal("1175200")),
        (Decimal("5100000"), Decimal("70000"), Decimal("1227200")),
        (Decimal("5200000"), Decimal("114000"), Decimal("1304160")),
    ],
)
def test_golden_case_6_surcharge_marginal_relief(
    new_calc, params, total_income, expected_surcharge, expected_total_tax
):
    """Case 6: Surcharge marginal relief at ₹50,00,000 threshold under new regime."""
    from app.schemas.tax import HeadwiseIncome

    data = IndianTaxpayerData()
    inc = HeadwiseIncome(
        regime=Regime.NEW,
        gross_total_income=total_income,
        total_income=total_income,
    )
    res = new_calc.calculate(data, inc, params)
    assert res.surcharge == expected_surcharge
    assert res.total_tax_liability == expected_total_tax


def test_winnings_115bb_flat_tax(income_service, old_calc, new_calc, params):
    """Section 115BB: Winnings are taxed at flat 30% without basic exemption limit."""
    data = IndianTaxpayerData(winnings_115bb=Decimal("200000"))

    inc_new = income_service.compute(data, Regime.NEW, params)
    res_new = new_calc.calculate(data, inc_new, params)
    assert res_new.tax_on_slab_income == Decimal("0")
    assert res_new.tax_on_special_income == Decimal("60000")
    assert res_new.cess == Decimal("2400")
    assert res_new.total_tax_liability == Decimal("62400")

    inc_old = income_service.compute(data, Regime.OLD, params)
    res_old = old_calc.calculate(data, inc_old, params)
    assert res_old.tax_on_slab_income == Decimal("0")
    assert res_old.tax_on_special_income == Decimal("60000")
    assert res_old.cess == Decimal("2400")
    assert res_old.total_tax_liability == Decimal("62400")


def test_old_regime_rebate_87a_on_stcg_111a(income_service, old_calc, params):
    """Old Regime: Rebate 87A applies against STCG 111A up to ₹12,500 when total income <= ₹5L."""
    cg = CapitalGainItem(
        asset_type="listed_equity",
        acquisition_date=date(2025, 1, 1),
        transfer_date=date(2025, 4, 1),
        sale_consideration=Decimal("200000"),
        cost_of_acquisition=Decimal("100000"),
        stt_paid=True,
    )
    # Gross salary 3,50,000 - 50,000 std ded = 3,00,000 salary
    # STCG 111A = 1,00,000. Total income = 4,00,000 (<= 5,00,000).
    f16 = Form16(gross_salary_17_1=Decimal("350000"))
    data = IndianTaxpayerData(form16s=[f16], capital_gains=[cg])

    inc_old = income_service.compute(data, Regime.OLD, params)
    res_old = old_calc.calculate(data, inc_old, params)
    # Slab tax on ₹3,00,000: 5% on 50,000 = ₹2,500
    assert res_old.tax_on_slab_income == Decimal("2500")
    # Special tax on STCG 111A ₹1,00,000 @ 20% = ₹20,000
    assert res_old.tax_on_special_income == Decimal("20000")
    assert res_old.tax_before_rebate == Decimal("22500")
    # Rebate 87A capped at ₹12,500
    assert res_old.rebate_87a == Decimal("12500")
    assert res_old.tax_after_rebate == Decimal("10000")
    assert res_old.cess == Decimal("400")
    assert res_old.total_tax_liability == Decimal("10400")


def test_non_resident_senior_citizen_old_regime_slabs(income_service, old_calc, params):
    """Non-residents do not qualify for senior citizen exemption limits (₹3L/₹5L)."""
    # Gross salary 5,50,000 - 50,000 std ded = 5,00,000 total income
    f16 = Form16(gross_salary_17_1=Decimal("550000"))
    data = IndianTaxpayerData(
        age_band=AgeBand.SENIOR_60_80,
        residential_status=ResidentialStatus.NON_RESIDENT,
        form16s=[f16],
    )
    inc = income_service.compute(data, Regime.OLD, params)
    res = old_calc.calculate(data, inc, params)
    # Exemption is ₹2,50,000 (not ₹3,00,000). Tax = 5% of ₹2,50,000 = ₹12,500.
    assert res.tax_on_slab_income == Decimal("12500")
    # Non-residents are not entitled to Section 87A rebate
    assert res.rebate_87a == Decimal("0")
    assert res.cess == Decimal("500")
    assert res.total_tax_liability == Decimal("13000")


def test_rule_119a_rounding_for_section_234a(old_calc, params):
    """Rule 119A: Fraction of 100 is ignored when computing interest under Section 234A."""
    from app.agents.regimes.base import interest_and_fees

    # Unpaid tax ₹12,385 -> base under Rule 119A is ₹12,300
    out = interest_and_fees(
        total_tax_liability=Decimal("12385"),
        taxes_paid_total=Decimal("0"),
        filing_date=date(2026, 9, 15),
        due_date=date(2026, 7, 31),
        params=params,
        is_belated=True,
        total_income=Decimal("500000"),
    )
    # Months late: Aug + Sep = 2 months. Rate: 1% per month.
    # Base: 12,300 * 1% * 2 = 246
    assert out["interest_234a"] == Decimal("246")

