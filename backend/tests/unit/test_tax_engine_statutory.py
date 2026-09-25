"""Statutory audit of the FY 2025-26 tax engine.

Every expected figure is hand-computed from the Income-tax Act as amended by the
Finance Act 2025; the arithmetic is written out next to each assertion.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService, apply_chapter_via
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.schemas.tax import (
    AgeBand,
    CapitalGainItem,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    PresumptiveBusiness,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
    TaxesPaid,
)
from app.tax_rules.params import get_params

P = get_params("2025-26")
DUE = date(2026, 7, 31)
NEW, OLD = Regime.NEW, Regime.OLD


def taxpayer(salary=0, **kw) -> IndianTaxpayerData:
    form16s = [Form16(gross_salary_17_1=D(salary))] if salary else []
    return IndianTaxpayerData(pan="ABCPD1234F", form16s=form16s, **kw)


def run(data: IndianTaxpayerData, regime: Regime, filing: date = DUE):
    income = IncomeComputationService().compute(data, regime, P)
    calc = NewRegimeCalculator() if regime == NEW else OldRegimeCalculator()
    return calc.calculate(data, income, P, filing)


def equity(sale, cost, bought, sold=date(2025, 9, 1), asset="listed_equity", **kw):
    return CapitalGainItem(
        asset_type=asset, acquisition_date=bought, transfer_date=sold,
        cost_of_acquisition=D(cost), sale_consideration=D(sale),
        stt_paid=asset in ("listed_equity", "equity_mf"), **kw,
    )


SHORT = date(2025, 5, 1)   # < 12 months before a Sep 2025 sale
LONG = date(2023, 1, 1)    # > 12 months


# ---------------------------------------------------------------------------
# New regime slabs, section 87A rebate and marginal relief
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "salary, expected",
    [
        # TI 12,00,000: slab 60,000 fully rebated
        (1275000, 0),
        # TI 12,00,010: slab 60,001.5; relief caps tax at excess 10; cess 0.4 -> 10
        (1275010, 10),
        # TI 12,70,000: slab 70,500 > excess 70,000 -> tax 70,000 + cess 2,800
        (1345000, 72800),
        # TI 12,80,000: slab 72,000 < excess 80,000 -> no relief; 72,000 + 2,880
        (1355000, 74880),
        # TI 30,00,000: 3,00,000 up to 24L + 30% of 6L = 4,80,000 + 19,200
        (3075000, 499200),
    ],
)
def test_new_regime_slabs_rebate_and_marginal_relief(salary, expected):
    assert run(taxpayer(salary), NEW).total_tax_liability == D(expected)


# ---------------------------------------------------------------------------
# Old regime slabs by age band and residence
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "salary, age, expected",
    [
        # TI 5,00,000: slab 12,500 fully rebated u/s 87A
        (550000, AgeBand.BELOW_60, 0),
        # TI 5,00,010: slab 12,502, no rebate above 5L; + cess 500.08 -> 13,000
        (550010, AgeBand.BELOW_60, 13000),
        # Senior TI 10L: 10,000 (3-5L) + 1,00,000 (5-10L) = 1,10,000 + 4,400
        (1050000, AgeBand.SENIOR_60_80, 114400),
        # Super senior TI 10L: 1,00,000 (5-10L) + 4,000
        (1050000, AgeBand.SUPER_SENIOR_80_PLUS, 104000),
    ],
)
def test_old_regime_slabs_by_age(salary, age, expected):
    assert run(taxpayer(salary, age_band=age), OLD).total_tax_liability == D(expected)


def test_non_residents_get_no_rebate_and_no_senior_slabs():
    nr = dict(residential_status=ResidentialStatus.NON_RESIDENT)
    # Old, TI 5L: 12,500 with no 87A rebate + 500 cess
    assert run(taxpayer(550000, **nr), OLD).total_tax_liability == D("13000")
    # Old senior NR TI 10L uses below-60 slabs: 1,12,500 + 4,500
    assert run(taxpayer(1050000, age_band=AgeBand.SENIOR_60_80, **nr), OLD).total_tax_liability == D("117000")
    # New, TI 7L: 5% of 3L = 15,000, no rebate + 600
    assert run(taxpayer(775000, **nr), NEW).total_tax_liability == D("15600")


# ---------------------------------------------------------------------------
# Surcharge bands and marginal relief
# ---------------------------------------------------------------------------
def test_surcharge_marginal_relief_just_above_50_lakh():
    # TI 51L: slab 11,10,000; raw surcharge 1,11,000. Tax at 50L is 10,80,000, so
    # extra tax may not exceed extra income 1,00,000: surcharge = 70,000.
    result = run(taxpayer(5175000), NEW)
    assert result.surcharge == D("70000")
    assert result.surcharge_marginal_relief == D("41000")
    assert result.total_tax_liability == D("1227200")  # (11,10,000 + 70,000) * 1.04


def test_surcharge_ten_percent_without_relief():
    # TI 60L: slab 13,80,000 + 10% 1,38,000 = 15,18,000 + cess 60,720
    assert run(taxpayer(6075000), NEW).total_tax_liability == D("1578720")


def test_old_regime_surcharge_marginal_relief_just_above_one_crore():
    # TI 1,00,10,000: slab 28,15,500; 15% = 4,22,325. At 1Cr: 28,12,500 * 1.10 =
    # 30,93,750, so surcharge is limited to 30,93,750 + 10,000 - 28,15,500 = 2,88,250.
    result = run(taxpayer(10060000), OLD)
    assert result.surcharge == D("288250")
    assert result.total_tax_liability == D("3227900")


def test_new_regime_surcharge_capped_at_25_percent_old_regime_37_percent():
    # TI 6Cr new: slab 1,75,80,000 + 25% 43,95,000 = 2,19,75,000 + 4% = 2,28,54,000
    assert run(taxpayer(60075000), NEW).total_tax_liability == D("22854000")
    # TI 6Cr old: slab 1,78,12,500 + 37% 65,90,625 = 2,44,03,125 + 4% = 2,53,79,250
    assert run(taxpayer(60050000), OLD).total_tax_liability == D("25379250")


def test_winnings_surcharge_is_not_capped_at_15_percent():
    # TI 3Cr: salary income 2.5Cr + 50L winnings (new regime, 25% band).
    # Salary slab tax 3,00,000 + 30% of 2,26,00,000 = 70,80,000; winnings 15,00,000.
    # Winnings are not capital gains, so both parts take the full 25%:
    # 85,80,000 * 25% = 21,45,000 (a 15% cap on winnings would give 19,95,000).
    data = taxpayer(25075000, winnings_115bb=D("5000000"))
    result = run(data, NEW)
    assert result.tax_on_special_income == D("1500000")
    assert result.surcharge == D("2145000")


def test_let_out_property_rent_is_taxed():
    # Rent 5L, municipal tax 20,000: NAV 4,80,000 - 30% 1,44,000 - interest 1L = 2,36,000
    hp = HouseProperty(is_let_out=True, annual_rent_received=D("500000"),
                       municipal_taxes_paid=D("20000"), interest_on_loan_24b=D("100000"))
    assert hp.is_self_occupied is False
    income = run(taxpayer(1500000, house_properties=[hp]), OLD).income
    assert income.house_property_income == D("236000")


# ---------------------------------------------------------------------------
# Special-rate income and the resident basic-exemption set-off
# ---------------------------------------------------------------------------
def test_basic_exemption_absorbs_short_term_gain_for_residents():
    # Only income: 3L STCG u/s 111A. New regime basic exemption 4L absorbs it all.
    data = taxpayer(capital_gains=[equity(400000, 100000, SHORT)])
    assert run(data, NEW).total_tax_liability == D("0")
    # Old regime: 2.5L absorbed, 50,000 @ 20% = 10,000, rebated u/s 87A (TI 3L)
    assert run(data, OLD).total_tax_liability == D("0")


def test_basic_exemption_partly_absorbs_larger_gain_and_new_regime_rebate_excludes_111a():
    data = taxpayer(capital_gains=[equity(700000, 100000, SHORT)])  # 6L STCG
    # New: (6L - 4L) * 20% = 40,000; 87A does not cover special-rate tax -> 41,600
    assert run(data, NEW).total_tax_liability == D("41600")
    # Old: (6L - 2.5L) * 20% = 70,000; TI 6L > 5L so no rebate -> 72,800
    assert run(data, OLD).total_tax_liability == D("72800")


def test_non_resident_gets_no_basic_exemption_set_off():
    data = taxpayer(
        capital_gains=[equity(400000, 100000, SHORT)],
        residential_status=ResidentialStatus.NON_RESIDENT,
    )
    # 3L * 20% = 60,000 + 2,400
    assert run(data, NEW).total_tax_liability == D("62400")


def test_old_regime_rebate_covers_111a_tax():
    # Salary income 2L + STCG 2L: 50,000 of basic exemption absorbed, 1.5L @ 20% =
    # 30,000; TI 4L <= 5L so 87A rebates 12,500 -> 17,500 + 700
    data = taxpayer(250000, capital_gains=[equity(300000, 100000, SHORT)])
    assert run(data, OLD).total_tax_liability == D("18200")


def test_ltcg_112a_exemption_and_rebate_on_slab_tax_only():
    # Salary TI 10L + 3L LTCG 112A: 1.25L exempt, 1.75L @ 12.5% = 21,875.
    # TI 11.75L <= 12L: slab tax 40,000 rebated, 112A tax is not -> 21,875 + 875
    data = taxpayer(1075000, capital_gains=[equity(400000, 100000, LONG)])
    result = run(data, NEW)
    assert result.income.ltcg_112a_exempt == D("125000")
    assert result.rebate_87a == D("40000")
    assert result.total_tax_liability == D("22750")


def test_winnings_taxed_at_30_percent_without_rebate_or_exemption():
    # Salary TI 5L + 1L winnings: slab 5% of 1L = 5,000 rebated; 30,000 + 1,200
    data = taxpayer(575000, winnings_115bb=D("100000"))
    assert run(data, NEW).total_tax_liability == D("31200")


# ---------------------------------------------------------------------------
# Capital-loss set-off (sections 70, 71(3), 74)
# ---------------------------------------------------------------------------
def test_short_term_loss_never_increases_tax_on_salary():
    # TI 20L new: slab 2,00,000 + 8,000. A 50,000 STCL is carried forward.
    base = run(taxpayer(2075000), NEW)
    with_loss = run(taxpayer(2075000, capital_gains=[equity(100000, 150000, SHORT)]), NEW)
    assert base.total_tax_liability == with_loss.total_tax_liability == D("208000")
    assert with_loss.tax_on_special_income == D("0")
    assert with_loss.income.cg_loss_carried_forward == D("50000")


def test_short_term_loss_offsets_long_term_gain():
    # 3L LTCG 112A - 1L STCL = 2L; 1.25L exempt; 75,000 @ 12.5% = 9,375.
    # With TI 20L salary: (2,00,000 + 9,375) * 1.04 = 2,17,750
    data = taxpayer(2075000, capital_gains=[
        equity(400000, 100000, LONG),
        equity(100000, 200000, SHORT),
    ])
    result = run(data, NEW)
    assert result.income.ltcg_112a_gross == D("200000")
    assert result.income.cg_loss_carried_forward == D("0")
    assert result.total_tax_liability == D("217750")


def test_long_term_loss_cannot_offset_short_term_gain():
    # 80,000 STCG stays taxable (16,000); 1L LTCL carried forward.
    data = taxpayer(2075000, capital_gains=[
        equity(180000, 100000, SHORT),
        equity(100000, 200000, LONG),
    ])
    result = run(data, NEW)
    assert result.income.stcg_111a == D("80000")
    assert result.income.cg_loss_carried_forward == D("100000")
    assert result.total_tax_liability == D("224640")  # (2,00,000 + 16,000) * 1.04


def test_short_term_loss_absorbs_slab_rate_gain_first():
    # Debt MF STCG 1L (slab) and 60,000 STCL on equity: slab gain falls to 40,000.
    # TI 20.4L: 2,00,000 + 25% of 40,000 = 2,10,000 + 8,400
    data = taxpayer(2075000, capital_gains=[
        equity(200000, 100000, SHORT, asset="debt_mf"),
        equity(100000, 160000, SHORT),
    ])
    result = run(data, NEW)
    assert result.income.stcg_slab == D("40000")
    assert result.income.stcg_111a == D("0")
    assert result.total_tax_liability == D("218400")


# ---------------------------------------------------------------------------
# House property
# ---------------------------------------------------------------------------
def test_self_occupied_interest_capped_at_two_lakh_old_regime():
    # Salary income 14.5L - 2L SOP interest = TI 12.5L: 1,12,500 + 75,000 = 1,87,500 + 7,500
    data = taxpayer(1500000, house_properties=[HouseProperty(is_self_occupied=True, interest_on_loan_24b=D("300000"))])
    result = run(data, OLD)
    assert result.income.hp_loss_set_off == D("200000")
    assert result.total_tax_liability == D("195000")


def test_let_out_loss_set_off_limit_and_carry_forward():
    # NAV 3,00,000 - 20,000 = 2,80,000; 30% = 84,000; loss = 2,80,000 - 84,000 - 5,00,000 = -3,04,000
    hp = HouseProperty(is_let_out=True, annual_rent_received=D("300000"),
                       municipal_taxes_paid=D("20000"), interest_on_loan_24b=D("500000"))
    data = taxpayer(1500000, house_properties=[hp])
    old = run(data, OLD).income
    assert (old.hp_loss_set_off, old.hp_loss_carried_forward) == (D("200000"), D("104000"))
    assert old.gross_total_income == D("1250000")
    new = run(data, NEW).income
    assert (new.hp_loss_set_off, new.hp_loss_carried_forward) == (D("0"), D("304000"))
    assert new.gross_total_income == D("1425000")


# ---------------------------------------------------------------------------
# Chapter VI-A
# ---------------------------------------------------------------------------
def via(claims, age=AgeBand.BELOW_60, regime=OLD, gti=D("2000000"), special=D("0"), **kw):
    data = taxpayer(2050000, age_band=age, **kw)
    return apply_chapter_via({k: D(v) for k, v in claims.items()}, gti, special, data, regime, P)


def test_section_caps_80c_80ccd1b_80d():
    applied, total, disallowed, _ = via({"80C": 200000, "80CCD1B": 70000, "80D": 40000})
    assert applied == {"80C": D("150000"), "80CCD1B": D("50000"), "80D": D("25000")}
    assert disallowed["80C"] == D("50000")
    assert total == D("225000")


def test_80ddb_senior_limit():
    applied, *_ = via({"80DDB": 90000}, age=AgeBand.SENIOR_60_80)
    assert applied["80DDB"] == D("90000")
    applied, _, disallowed, _ = via({"80DDB": 90000})
    assert applied["80DDB"] == D("40000")
    assert disallowed["80DDB"] == D("50000")


def test_80tta_80ttb_wrong_age_claims_are_recorded():
    applied, _, disallowed, traces = via({"80TTA": 10000}, age=AgeBand.SENIOR_60_80, savings_interest=D("20000"))
    assert "80TTA" not in applied
    assert disallowed["80TTA"] == D("10000")
    assert any("80TTA" in t and "disallowed" in t for t in traces)
    applied, _, disallowed, _ = via({"80TTB": 40000}, fd_interest=D("60000"))
    assert "80TTB" not in applied and disallowed["80TTB"] == D("40000")


def test_80tta_limited_by_cap_and_interest():
    applied, _, disallowed, _ = via({"80TTA": 15000}, savings_interest=D("12000"))
    assert applied["80TTA"] == D("10000")
    assert disallowed["80TTA"] == D("5000")
    applied, _, _, _ = via({"80TTA": 10000}, savings_interest=D("6000"))
    assert applied["80TTA"] == D("6000")


def test_80ttb_senior_interest_deduction():
    applied, *_ = via({"80TTB": 60000}, age=AgeBand.SENIOR_60_80, fd_interest=D("70000"))
    assert applied["80TTB"] == D("50000")


def test_new_regime_allows_only_employer_nps_capped_at_14_percent():
    # Salary 17(1) 20.5L * 14% = 2,87,000 cap, so the full 2,00,000 claim is allowed
    applied, _, disallowed, _ = via({"80C": 150000, "80CCD2": 200000}, regime=NEW)
    assert applied == {"80CCD2": D("200000")}
    assert disallowed["80C"] == D("150000")
    # A 3,00,000 claim exceeds the 14% cap
    applied, _, disallowed, _ = via({"80CCD2": 300000}, regime=NEW)
    assert applied["80CCD2"] == D("287000")
    assert disallowed["80CCD2"] == D("13000")


def test_chapter_via_cannot_reduce_special_rate_income():
    # GTI 3L of which 2L is STCG 111A: only 1L of deductions can be used.
    applied, total, _, _ = via({"80C": 150000, "80D": 25000}, gti=D("300000"), special=D("200000"))
    assert total == D("100000")


# ---------------------------------------------------------------------------
# Indexation for property bought before 23 July 2024
# ---------------------------------------------------------------------------
def test_indexation_uses_financial_year_cii():
    # Bought 15 Feb 2020 = FY 2019-20 (CII 289). Indexed cost 80L * 376/289 =
    # 1,04,08,304 > sale 1Cr, so the indexed gain is nil and is chosen over
    # 20L * 12.5%. The calendar-year CII (301) would leave a ~10,631 gain.
    item = CapitalGainItem(
        asset_type="immovable_property", acquisition_date=date(2020, 2, 15),
        transfer_date=date(2025, 6, 1), cost_of_acquisition=D("8000000"),
        sale_consideration=D("10000000"), is_pre_23jul2024=True,
    )
    result = run(taxpayer(1075000, capital_gains=[item]), OLD)
    assert result.income.ltcg_112 == D("0")


# ---------------------------------------------------------------------------
# Relief u/s 89 / 90 / 91 in settlement
# ---------------------------------------------------------------------------
def test_relief_89_reduces_net_settlement():
    # Liability 2,08,000; TDS 2,00,000 + relief 10,000 -> refund 2,000, no interest
    data = taxpayer(2075000, taxes_paid=TaxesPaid(tds_salary=D("200000"), relief_89=D("10000")))
    result = run(data, NEW)
    assert result.total_tax_liability == D("208000")
    assert (result.refund_due, result.tax_payable) == (D("2000"), D("0"))
    assert result.interest_234b == result.interest_234c == D("0")


def test_relief_cannot_create_a_refund_beyond_liability():
    # TI 5L new: liability 0; relief 5,000 is unusable, only the 1,000 TDS is refunded
    data = taxpayer(575000, taxes_paid=TaxesPaid(tds_salary=D("1000"), relief_89=D("5000")))
    assert run(data, NEW).refund_due == D("1000")


def test_form16_relief_89_flows_into_taxes_paid():
    data = IndianTaxpayerData(form16s=[Form16(gross_salary_17_1=D("2075000"), tds_deducted=D("200000"), relief_89=D("10000"))])
    data.aggregate_form16s()
    assert data.taxes_paid.relief_89 == D("10000")


# ---------------------------------------------------------------------------
# Interest u/s 234A/B/C and fee u/s 234F
# ---------------------------------------------------------------------------
def test_234b_and_234c_on_time_filing_without_advance_tax():
    # Liability 2,08,000 (TI 20L new), nothing paid, filed 31 Jul 2026.
    # 234B: 2,08,000 * 1% * 4 months = 8,320
    # 234C: 31,200*3% + 93,600*3% + 1,56,000*3% + 2,08,000*1% = 936 + 2,808 + 4,680 + 2,080
    result = run(taxpayer(2075000), NEW)
    assert result.interest_234a == D("0")
    assert result.interest_234b == D("8320")
    assert result.interest_234c == D("10504")
    assert result.tax_payable == D("226824")


def test_belated_filing_adds_234a_longer_234b_and_234f():
    # Filed 15 Oct 2026: 234A Aug-Oct 3 months = 6,240; 234B Apr-Oct 7 months = 14,560
    result = run(taxpayer(2075000), NEW, filing=date(2026, 10, 15))
    assert result.interest_234a == D("6240")
    assert result.interest_234b == D("14560")
    assert result.fee_234f == D("5000")


@pytest.mark.parametrize(
    "salary, regime, expected_fee",
    [
        (375000, NEW, 0),      # TI 3L <= new-regime basic exemption 4L
        (525000, NEW, 1000),   # TI 4.5L: above 4L, within 5L
        (550000, OLD, 1000),   # TI 5L: above old basic exemption 2.5L, within 5L
        (275000, OLD, 0),      # TI 2.25L <= old-regime basic exemption 2.5L
    ],
)
def test_234f_not_levied_within_basic_exemption(salary, regime, expected_fee):
    assert run(taxpayer(salary), regime, filing=date(2026, 12, 15)).fee_234f == D(expected_fee)


def test_resident_senior_without_business_is_exempt_from_advance_tax_interest():
    result = run(taxpayer(2075000, age_band=AgeBand.SENIOR_60_80), NEW)
    assert result.interest_234b == result.interest_234c == D("0")


# ---------------------------------------------------------------------------
# Other heads and rounding
# ---------------------------------------------------------------------------
def test_total_income_rounded_to_nearest_ten():
    # GTI 10,00,005 rounds up to 10,00,010 (section 288A)
    assert run(taxpayer(1075005), NEW).income.total_income == D("1000010")


def test_family_pension_deduction():
    # 1/3 of 90,000 = 30,000, capped at 25,000 (new) / 15,000 (old)
    data = taxpayer(family_pension=D("90000"))
    assert run(data, NEW).income.other_sources_income == D("65000")
    assert run(data, OLD).income.other_sources_income == D("75000")


def test_presumptive_business_income():
    ada = taxpayer(presumptive=PresumptiveBusiness(section="44ADA", turnover=D("4000000"), declared_profit=D("1500000")))
    assert run(ada, NEW).income.business_income == D("2000000")  # 50% deemed > declared
    ad = taxpayer(presumptive=PresumptiveBusiness(section="44AD", turnover=D("10000000"), digital_receipts=D("10000000"), declared_profit=D("500000")))
    assert run(ad, NEW).income.business_income == D("600000")    # 6% of digital receipts


def test_breakeven_uses_salary_breakup_when_no_form16():
    breakup = SalaryBreakup(basic=D("1200000"), hra_received=D("300000"), other_allowances=D("100000"))
    data = taxpayer(salary_breakup=breakup)
    assert RegimeComparisonAgent(P)._compute_raw_gross_income(data) == D("1600000")
    old, new = run(data, OLD), run(data, NEW)
    comparison, _ = RegimeComparisonAgent(P).run(data, old, new)
    assert comparison.breakeven_deduction_amount > D("0")
