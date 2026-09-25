from datetime import date
from decimal import Decimal

import pytest

from app.agents.income.computation import IncomeComputationService, hra_exemption
from app.schemas.tax import (
    CapitalGainItem,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
)
from app.tax_rules.params import get_params


@pytest.fixture
def params():
    return get_params("2025-26")


@pytest.fixture
def service():
    return IncomeComputationService()


def test_hra_least_of_three_limb_1_actual_hra():
    # Actual HRA is the least
    sb = SalaryBreakup(
        basic=Decimal("1200000"),
        dearness_allowance=Decimal("0"),
        hra_received=Decimal("120000"),
        rent_paid_annual=Decimal("300000"),
        is_metro=True,
    )
    # Limb 1: 120,000
    # Limb 2: 50% of 12L = 600,000
    # Limb 3: 300,000 - 10%(12L) = 180,000
    exempt, _ = hra_exemption(sb, Regime.OLD)
    assert exempt == Decimal("120000")


def test_hra_least_of_three_limb_2_percentage_salary():
    # 50% of salary is the least
    sb = SalaryBreakup(
        basic=Decimal("300000"),
        dearness_allowance=Decimal("0"),
        hra_received=Decimal("250000"),
        rent_paid_annual=Decimal("250000"),
        is_metro=True,
    )
    # Limb 1: 250,000
    # Limb 2: 50% of 3L = 150,000
    # Limb 3: 250,000 - 10%(3L) = 220,000
    exempt, _ = hra_exemption(sb, Regime.OLD)
    assert exempt == Decimal("150000")


def test_hra_least_of_three_limb_3_rent_minus_ten_percent():
    # Rent minus 10% is the least
    sb = SalaryBreakup(
        basic=Decimal("1000000"),
        dearness_allowance=Decimal("0"),
        hra_received=Decimal("400000"),
        rent_paid_annual=Decimal("180000"),
        is_metro=True,
    )
    # Limb 1: 400,000
    # Limb 2: 500,000
    # Limb 3: 180,000 - 100,000 = 80,000
    exempt, _ = hra_exemption(sb, Regime.OLD)
    assert exempt == Decimal("80000")


def test_self_occupied_interest_cap(service, params):
    # Interest 3,00,000 on self-occupied property
    hp = HouseProperty(is_self_occupied=True, interest_on_loan_24b=Decimal("300000"))
    f16 = Form16(gross_salary_17_1=Decimal("1000000"))
    data = IndianTaxpayerData(form16s=[f16], house_properties=[hp])

    res_old = service.compute(data, Regime.OLD, params)
    # Old regime caps SOP interest at 2,00,000 (GTI reduced by 2,00,000)
    assert res_old.hp_loss_set_off == Decimal("200000")
    assert res_old.hp_loss_carried_forward == Decimal("0")

    res_new = service.compute(data, Regime.NEW, params)
    # New regime SOP interest is disallowed (hp_loss_set_off is 0)
    assert res_new.hp_loss_set_off == Decimal("0")


def test_let_out_loss_cap_and_carry_forward(service, params):
    # Let out property generating loss of 3,50,000
    # Rent 1,00,000, interest 4,20,000. NAV = 1,00,000 - 30% (30,000) = 70,000.
    # Net = 70,000 - 4,20,000 = -3,50,000.
    hp = HouseProperty(
        is_self_occupied=False,
        is_let_out=True,
        annual_rent_received=Decimal("100000"),
        interest_on_loan_24b=Decimal("420000"),
    )
    f16 = Form16(gross_salary_17_1=Decimal("1500000"))
    data = IndianTaxpayerData(form16s=[f16], house_properties=[hp])

    res_old = service.compute(data, Regime.OLD, params)
    assert res_old.hp_loss_set_off == Decimal("200000")
    assert res_old.hp_loss_carried_forward == Decimal("150000")

    res_new = service.compute(data, Regime.NEW, params)
    assert res_new.hp_loss_set_off == Decimal("0")
    assert res_new.hp_loss_carried_forward == Decimal("350000")


def test_ltcg_112a_exemption(service, params):
    item = CapitalGainItem(
        asset_type="listed_equity",
        acquisition_date=date(2023, 1, 1),
        transfer_date=date(2025, 6, 1),
        sale_consideration=Decimal("500000"),
        cost_of_acquisition=Decimal("300000"),
        stt_paid=True,
    )
    # Gross gain = 2,00,000
    data = IndianTaxpayerData(capital_gains=[item])
    res = service.compute(data, Regime.NEW, params)
    assert res.ltcg_112a_gross == Decimal("200000")
    assert res.ltcg_112a_exempt == Decimal("125000")
    assert res.ltcg_112a_taxable == Decimal("75000")


def test_property_indexation_option(service, params):
    # Property acquired in 2015 for 50L, sold in 2025 for 80L
    # Unindexed gain = 30L -> 12.5% tax = 3.75L
    # Indexed cost = 50L * (376 / 254) = 74.0157L -> Indexed gain = 5.984L -> 20% tax = 1.1968L
    # 20% indexed is significantly lower!
    item = CapitalGainItem(
        asset_type="immovable_property",
        acquisition_date=date(2015, 4, 1),
        transfer_date=date(2025, 8, 1),
        sale_consideration=Decimal("8000000"),
        cost_of_acquisition=Decimal("5000000"),
        is_pre_23jul2024=True,
    )
    data = IndianTaxpayerData(
        capital_gains=[item],
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
    )
    res = service.compute(data, Regime.NEW, params)
    # Verify indexation option is chosen
    assert any("indexed option chosen" in t for t in res.trace)


def test_80c_cap_and_regime_filtering(service, params):
    f16 = Form16(gross_salary_17_1=Decimal("1500000"))
    data = IndianTaxpayerData(
        form16s=[f16],
        deduction_claims={"80C": Decimal("200000")},
    )
    res_old = service.compute(data, Regime.OLD, params)
    assert res_old.chapter_via.get("80C") == Decimal("150000")

    res_new = service.compute(data, Regime.NEW, params)
    assert "80C" not in res_new.chapter_via


def test_80ccd2_survives_in_both_regimes(service, params):
    # Salary basic 10,00,000
    sb = SalaryBreakup(basic=Decimal("1000000"), rent_paid_annual=Decimal("0"))
    f16 = Form16(gross_salary_17_1=Decimal("1000000"))
    # Claim 80CCD(2) = 1,40,000 (14%)
    data = IndianTaxpayerData(
        form16s=[f16],
        salary_breakup=sb,
        deduction_claims={"80CCD2": Decimal("140000")},
    )

    # In NEW regime: up to 14% = 1,40,000
    res_new = service.compute(data, Regime.NEW, params)
    assert res_new.chapter_via.get("80CCD2") == Decimal("140000")

    # In OLD regime: capped at 10% = 1,00,000
    res_old = service.compute(data, Regime.OLD, params)
    assert res_old.chapter_via.get("80CCD2") == Decimal("100000")


def test_family_pension_deduction_one_third_rule(service, params):
    # Test case A: Pension ₹60,000 -> 1/3 is ₹20,000.
    # New Regime cap is ₹25,000 -> deduction should be ₹20,000 (not ₹25,000!).
    # Old Regime cap is ₹15,000 -> deduction should be ₹15,000.
    data_a = IndianTaxpayerData(family_pension=Decimal("60000"))
    res_a_new = service.compute(data_a, Regime.NEW, params)
    assert res_a_new.other_sources_income == Decimal("40000")  # 60,000 - 20,000

    res_a_old = service.compute(data_a, Regime.OLD, params)
    assert res_a_old.other_sources_income == Decimal("45000")  # 60,000 - 15,000

    # Test case B: Pension ₹90,000 -> 1/3 is ₹30,000.
    # New Regime cap ₹25,000 binds -> deduction is ₹25,000.
    # Old Regime cap ₹15,000 binds -> deduction is ₹15,000.
    data_b = IndianTaxpayerData(family_pension=Decimal("90000"))
    res_b_new = service.compute(data_b, Regime.NEW, params)
    assert res_b_new.other_sources_income == Decimal("65000")  # 90,000 - 25,000

    res_b_old = service.compute(data_b, Regime.OLD, params)
    assert res_b_old.other_sources_income == Decimal("75000")  # 90,000 - 15,000


def test_capital_loss_cannot_offset_salary_under_section_71_3(service, params):
    # Section 71(3) strictly prohibits setting off capital loss against any other head.
    f16 = Form16(gross_salary_17_1=Decimal("1000000"))
    cg_loss = CapitalGainItem(
        asset_type="listed_equity",
        acquisition_date=date(2025, 1, 1),
        transfer_date=date(2025, 4, 1),
        sale_consideration=Decimal("100000"),
        cost_of_acquisition=Decimal("300000"),
        stt_paid=True,
    )
    data = IndianTaxpayerData(form16s=[f16], capital_gains=[cg_loss])

    # In New Regime: Salary after standard deduction = 10,00,000 - 75,000 = 9,25,000.
    # Net capital gain is -2,00,000.
    # GTI must remain 9,25,000 (NOT 7,25,000).
    res_new = service.compute(data, Regime.NEW, params)
    assert res_new.income_from_salary == Decimal("925000")
    assert res_new.capital_gains_total == Decimal("0")
    assert res_new.cg_loss_carried_forward == Decimal("200000")
    assert res_new.gross_total_income == Decimal("925000")
    assert res_new.total_income == Decimal("925000")

    # In Old Regime: Salary after standard deduction = 10,00,000 - 50,000 = 9,50,000.
    res_old = service.compute(data, Regime.OLD, params)
    assert res_old.income_from_salary == Decimal("950000")
    assert res_old.capital_gains_total == Decimal("0")
    assert res_old.cg_loss_carried_forward == Decimal("200000")
    assert res_old.gross_total_income == Decimal("950000")
    assert res_old.total_income == Decimal("950000")


def test_winnings_115bb_in_headwise_income(service, params):
    data = IndianTaxpayerData(winnings_115bb=Decimal("100000"))
    res = service.compute(data, Regime.NEW, params)
    assert res.winnings_115bb == Decimal("100000")
    assert res.other_sources_income == Decimal("100000")
    assert res.gross_total_income == Decimal("100000")
    assert res.total_income == Decimal("100000")

