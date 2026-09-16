"""Versioned Indian income tax parameters.

Every numeric constant the engine relies on lives in a ``TaxYearParams`` value
that carries its own provenance (``source`` + ``verified``). Constants must
never be authored by an LLM and must be traceable to statutory provisions of
the Income-tax Act, 1961 (and Income-tax Act, 2025).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.schemas.tax import AgeBand, Regime

Bracket = tuple[Decimal | None, Decimal]


def progressive_tax(amount: Decimal, brackets: list[Bracket]) -> Decimal:
    """Exact progressive tax on ``amount`` over ascending ``(upper, rate)`` bands.

    The final band must be open (``upper is None``).
    """
    tax = Decimal("0")
    lower = Decimal("0")
    for upper, rate in brackets:
        if amount <= lower:
            break
        band_top = amount if upper is None else min(amount, upper)
        tax += (band_top - lower) * rate
        if upper is None or amount <= upper:
            break
        lower = upper
    return tax


@dataclass(frozen=True)
class RegimeParams:
    slabs: dict[AgeBand, list[tuple[Decimal | None, Decimal]]]
    standard_deduction: Decimal
    family_pension_deduction: Decimal
    rebate_limit: Decimal  # total income ceiling for 87A
    rebate_max: Decimal
    rebate_marginal_relief: bool
    allowed_chapter_via: frozenset[str]
    allows_hra: bool
    allows_lta: bool
    allows_professional_tax: bool
    allows_sop_interest_24b: bool
    allows_hp_loss_setoff: bool
    employer_nps_limit_pct: Decimal  # 0.14 new, 0.10 old (private employees)


@dataclass(frozen=True)
class SurchargeParams:
    bands: list[tuple[Decimal | None, Decimal]]  # (total income upper, rate)
    special_income_cap: Decimal  # 0.15
    marginal_relief: bool = True


@dataclass(frozen=True)
class CapitalGainParams:
    stcg_111a_rate: Decimal
    ltcg_112a_rate: Decimal
    ltcg_112a_exemption: Decimal
    ltcg_112_rate: Decimal
    ltcg_112_indexed_rate: Decimal
    winnings_115bb_rate: Decimal
    holding_months: dict[str, int]
    cii: dict[int, int]
    indexation_option_cutoff: date


@dataclass(frozen=True)
class ChapterVIALimits:
    limits: dict[str, Decimal]
    senior_variants: dict[str, Decimal]
    combined_ceilings: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class InterestParams:
    rate_234a: Decimal
    rate_234b: Decimal
    rate_234c: Decimal
    fee_234f_high: Decimal
    fee_234f_low: Decimal
    fee_234f_income_threshold: Decimal
    refund_interest_244a: Decimal
    advance_tax_schedule: list[tuple[str, Decimal, Decimal]]
    advance_tax_threshold: Decimal


@dataclass(frozen=True)
class TaxYearParams:
    year: int
    financial_year: str
    assessment_year: str
    regimes: dict[Regime, RegimeParams]
    surcharge: dict[Regime, SurchargeParams]
    cess_rate: Decimal
    capital_gains: CapitalGainParams
    chapter_via: ChapterVIALimits
    interest: InterestParams
    source: str
    verified: bool
    section_map: dict[str, str] = field(default_factory=dict)


_REGISTRY: dict[str | int, TaxYearParams] = {}


def register(params: TaxYearParams) -> TaxYearParams:
    _REGISTRY[params.year] = params
    _REGISTRY[params.financial_year] = params
    return params


def get_params(year: int | str) -> TaxYearParams:
    if year in _REGISTRY:
        return _REGISTRY[year]
    # Try normalization, e.g. "2025" -> 2025 or 2025 -> "2025-26"
    try:
        y_int = int(str(year).split("-")[0])
        if y_int in _REGISTRY:
            return _REGISTRY[y_int]
    except (ValueError, TypeError):
        pass

    installed = ", ".join(str(y) for y in sorted(k for k in _REGISTRY if isinstance(k, str))) or "none"
    raise ValueError(
        f"No tax parameters installed for {year} (installed years: {installed})."
    )


TaxParams = TaxYearParams
