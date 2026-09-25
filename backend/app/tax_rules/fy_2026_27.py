"""Tax year parameter pack for Financial Year 2026-27 (Tax Year 2026-27).

Statutory references:
- Budget 2026: Slabs, rates, and deduction caps unchanged from FY 2025-26.
- Income-tax Act, 2025 (effective 1 April 2026):
  Replaces the Income-tax Act, 1961. Rates and slabs carry over unchanged.
  Renumbered sections:
    - Section 115BAC -> Section 202
    - Section 80C -> Section 123
    - Section 192 -> Section 392
    - Section 139 -> Section 263
    - Section 16(ia) -> Section 28
    - Section 24(b) -> Section 36
    - Section 87A -> Section 145
  "Tax Year" replaces the previous year / assessment year pair.
"""

from datetime import date
from decimal import Decimal

from app.schemas.tax import AgeBand, Regime
from app.tax_rules.fy_2025_26 import (
    CII_TABLE,
    _NEW_REGIME_SLABS,
    _NEW_REGIME_SURCHARGE_BANDS,
    _OLD_REGIME_SLABS_BELOW_60,
    _OLD_REGIME_SLABS_SENIOR,
    _OLD_REGIME_SLABS_SUPER_SENIOR,
    _OLD_REGIME_SURCHARGE_BANDS,
)
from app.tax_rules.params import (
    CapitalGainParams,
    ChapterVIALimits,
    InterestParams,
    RegimeParams,
    SurchargeParams,
    TaxYearParams,
    register,
)

SECTION_MAP_2026_27: dict[str, str] = {
    "115BAC": "202",
    "80C": "123",
    "80CCD1B": "124",
    "80CCD2": "125",
    "80D": "126",
    "80TTA": "127",
    "80TTB": "128",
    "16(ia)": "28",
    "16(iii)": "30",
    "24(b)": "36",
    "87A": "145",
    "111A": "165",
    "112": "166",
    "112A": "167",
    "139": "263",
    "192": "392",
}

PARAMS_2026_27 = TaxYearParams(
    year=2026,
    financial_year="2026-27",
    assessment_year="2027-28",
    source="Budget 2026; Income-tax Act 2025",
    verified=False,
    cess_rate=Decimal("0.04"),
    section_map=SECTION_MAP_2026_27,
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
            "80CCD2": Decimal("0"),
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

register(PARAMS_2026_27)
