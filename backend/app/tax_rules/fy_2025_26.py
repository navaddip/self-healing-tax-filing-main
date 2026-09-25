"""Tax year parameter pack for Financial Year 2025-26 (Assessment Year 2026-27).

Statutory references:
- Finance Act, 2025
- Section 115BAC(1A): New default tax regime slabs and standard deduction
- Section 87A: Rebate and marginal relief
- Sections 111A, 112, 112A, 115BB: Special tax rates on capital gains and winnings
- Sections 234A, 234B, 234C, 234F: Interest and late filing fees
- Section 244A: Interest on refund
- Chapter VI-A (Sections 80C through 80U): Permissible deductions
"""

from datetime import date
from decimal import Decimal

from app.schemas.tax import AgeBand, Regime
from app.tax_rules.params import (
    CapitalGainParams,
    ChapterVIALimits,
    InterestParams,
    RegimeParams,
    SurchargeParams,
    TaxYearParams,
    register,
)

# New Regime Slabs - Section 115BAC(1A)
# Identical across all age bands
_NEW_REGIME_SLABS: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("400000"), Decimal("0.00")),
    (Decimal("800000"), Decimal("0.05")),
    (Decimal("1200000"), Decimal("0.10")),
    (Decimal("1600000"), Decimal("0.15")),
    (Decimal("2000000"), Decimal("0.20")),
    (Decimal("2400000"), Decimal("0.25")),
    (None, Decimal("0.30")),
]

_OLD_REGIME_SLABS_BELOW_60: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("250000"), Decimal("0.00")),
    (Decimal("500000"), Decimal("0.05")),
    (Decimal("1000000"), Decimal("0.20")),
    (None, Decimal("0.30")),
]

_OLD_REGIME_SLABS_SENIOR: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("300000"), Decimal("0.00")),
    (Decimal("500000"), Decimal("0.05")),
    (Decimal("1000000"), Decimal("0.20")),
    (None, Decimal("0.30")),
]

_OLD_REGIME_SLABS_SUPER_SENIOR: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("500000"), Decimal("0.00")),
    (Decimal("1000000"), Decimal("0.20")),
    (None, Decimal("0.30")),
]

_OLD_REGIME_SURCHARGE_BANDS: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("5000000"), Decimal("0.00")),
    (Decimal("10000000"), Decimal("0.10")),
    (Decimal("20000000"), Decimal("0.15")),
    (Decimal("50000000"), Decimal("0.25")),
    (None, Decimal("0.37")),
]

_NEW_REGIME_SURCHARGE_BANDS: list[tuple[Decimal | None, Decimal]] = [
    (Decimal("5000000"), Decimal("0.00")),
    (Decimal("10000000"), Decimal("0.10")),
    (Decimal("20000000"), Decimal("0.15")),
    (Decimal("50000000"), Decimal("0.25")),
    (None, Decimal("0.25")),  # Capped at 25% in new regime
]

# Cost Inflation Index (CII)
CII_TABLE: dict[int, int] = {
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117,
    2006: 122, 2007: 129, 2008: 137, 2009: 148, 2010: 167,
    2011: 184, 2012: 200, 2013: 220, 2014: 240, 2015: 254,
    2016: 264, 2017: 272, 2018: 280, 2019: 289, 2020: 301,
    2021: 317, 2022: 331, 2023: 348, 2024: 363, 2025: 376,
}

PARAMS_2025_26 = TaxYearParams(
    year=2025,
    financial_year="2025-26",
    assessment_year="2026-27",
    source=(
        "Income Tax Department, Salaried Individuals for AY 2026-27: "
        "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1; "
        "Income-tax Act, 1961, sections 288A and 288B"
    ),
    verified=True,
    cess_rate=Decimal("0.04"),
    regimes={
        Regime.NEW: RegimeParams(
            slabs={
                AgeBand.BELOW_60: _NEW_REGIME_SLABS,
                AgeBand.SENIOR_60_80: _NEW_REGIME_SLABS,
                AgeBand.SUPER_SENIOR_80_PLUS: _NEW_REGIME_SLABS,
            },
            standard_deduction=Decimal("75000"),
            family_pension_deduction=Decimal("25000"),
            rebate_limit=Decimal("1200000"),
            rebate_max=Decimal("60000"),
            rebate_marginal_relief=True,
            allowed_chapter_via=frozenset({"80CCD2", "80CCH", "80JJAA"}),
            allows_hra=False,
            allows_lta=False,
            allows_professional_tax=False,
            allows_sop_interest_24b=False,
            allows_hp_loss_setoff=False,
            employer_nps_limit_pct=Decimal("0.14"),
        ),
        Regime.OLD: RegimeParams(
            slabs={
                AgeBand.BELOW_60: _OLD_REGIME_SLABS_BELOW_60,
                AgeBand.SENIOR_60_80: _OLD_REGIME_SLABS_SENIOR,
                AgeBand.SUPER_SENIOR_80_PLUS: _OLD_REGIME_SLABS_SUPER_SENIOR,
            },
            standard_deduction=Decimal("50000"),
            family_pension_deduction=Decimal("15000"),
            rebate_limit=Decimal("500000"),
            rebate_max=Decimal("12500"),
            rebate_marginal_relief=False,
            allowed_chapter_via=frozenset({
                "80C", "80CCC", "80CCD1", "80CCD1B", "80CCD2", "80CCH",
                "80D", "80DD", "80DDB", "80E", "80EE", "80EEA", "80G",
                "80GG", "80GGC", "80TTA", "80TTB", "80U", "80JJAA",
            }),
            allows_hra=True,
            allows_lta=True,
            allows_professional_tax=True,
            allows_sop_interest_24b=True,
            allows_hp_loss_setoff=True,
            employer_nps_limit_pct=Decimal("0.10"),
        ),
    },
    surcharge={
        Regime.NEW: SurchargeParams(
            bands=_NEW_REGIME_SURCHARGE_BANDS,
            special_income_cap=Decimal("0.15"),
            marginal_relief=True,
        ),
        Regime.OLD: SurchargeParams(
            bands=_OLD_REGIME_SURCHARGE_BANDS,
            special_income_cap=Decimal("0.15"),
            marginal_relief=True,
        ),
    },
    capital_gains=CapitalGainParams(
        stcg_111a_rate=Decimal("0.20"),
        ltcg_112a_rate=Decimal("0.125"),
        ltcg_112a_exemption=Decimal("125000"),
        ltcg_112_rate=Decimal("0.125"),
        ltcg_112_indexed_rate=Decimal("0.20"),
        winnings_115bb_rate=Decimal("0.30"),
        holding_months={
            "listed_equity": 12,
            "equity_mf": 12,
            "immovable_property": 24,
            "unlisted_shares": 24,
            "gold": 24,
            "debt_mf": 0,
            "other": 24,
        },
        cii=CII_TABLE,
        indexation_option_cutoff=date(2024, 7, 23),
    ),
    chapter_via=ChapterVIALimits(
        limits={
            "80C": Decimal("150000"),
            "80CCC": Decimal("150000"),
            "80CCD1": Decimal("150000"),
            "80CCD1B": Decimal("50000"),
            "80CCD2": Decimal("0"),  # Computed by employer_nps_limit_pct * (basic + DA)
            "80CCH": Decimal("10000000"),
            "80D": Decimal("25000"),
            "80DD": Decimal("75000"),
            "80DDB": Decimal("40000"),
            "80E": Decimal("10000000"),
            "80EE": Decimal("50000"),
            "80EEA": Decimal("150000"),
            "80G": Decimal("10000000"),
            "80GG": Decimal("60000"),
            "80GGC": Decimal("10000000"),
            "80TTA": Decimal("10000"),
            "80TTB": Decimal("50000"),
            "80U": Decimal("75000"),
            "80JJAA": Decimal("10000000"),
        },
        senior_variants={
            "80D": Decimal("50000"),
            "80TTB": Decimal("50000"),
            "80DDB": Decimal("100000"),
            "80DD": Decimal("125000"),
            "80U": Decimal("125000"),
        },
        combined_ceilings={
            "80C": ("80C", "80CCC", "80CCD1"),
        },
    ),
    interest=InterestParams(
        rate_234a=Decimal("0.01"),
        rate_234b=Decimal("0.01"),
        rate_234c=Decimal("0.01"),
        fee_234f_high=Decimal("5000"),
        fee_234f_low=Decimal("1000"),
        fee_234f_income_threshold=Decimal("500000"),
        refund_interest_244a=Decimal("0.005"),
        advance_tax_schedule=[
            ("15 June", Decimal("0.15"), Decimal("0.12")),
            ("15 September", Decimal("0.45"), Decimal("0.36")),
            ("15 December", Decimal("0.75"), Decimal("0.75")),
            ("15 March", Decimal("1.00"), Decimal("1.00")),
        ],
        advance_tax_threshold=Decimal("10000"),
    ),
)

register(PARAMS_2025_26)
