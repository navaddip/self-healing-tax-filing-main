"""Structural self-consistency checks for Indian tax-year parameters.

These catch transcription errors (non-monotonic slabs, inverted surcharge rates,
improper Chapter VI-A sets, or bad bracket structures) independently of whether
a year is marked ``verified``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.schemas.tax import Regime
from app.tax_rules.params import TaxYearParams

KNOWN_CHAPTER_VIA_SECTIONS = frozenset({
    "80C",
    "80CCC",
    "80CCD1",
    "80CCD1B",
    "80CCD2",
    "80CCH",
    "80D",
    "80DD",
    "80DDB",
    "80E",
    "80EE",
    "80EEA",
    "80G",
    "80GG",
    "80GGC",
    "80TTA",
    "80TTB",
    "80U",
    "80JJAA",
})


def validate_params(p: TaxYearParams) -> list[str]:
    issues: list[str] = []

    def note(cond: bool, msg: str) -> None:
        if not cond:
            issues.append(f"[{p.financial_year}] {msg}")

    # Basic rates & thresholds
    note(Decimal("0") < p.cess_rate < Decimal("1"), "cess_rate must be between 0 and 1")

    # Regimes check
    note(Regime.NEW in p.regimes, "NEW regime params missing")
    note(Regime.OLD in p.regimes, "OLD regime params missing")

    if Regime.NEW in p.regimes and Regime.OLD in p.regimes:
        new_reg = p.regimes[Regime.NEW]
        old_reg = p.regimes[Regime.OLD]

        note(new_reg.rebate_max > 0, "new regime rebate_max must be positive")
        note(new_reg.rebate_limit > new_reg.rebate_max, "new regime rebate_limit must exceed rebate_max")
        note(old_reg.rebate_max > 0, "old regime rebate_max must be positive")
        note(old_reg.rebate_limit > old_reg.rebate_max, "old regime rebate_limit must exceed rebate_max")

        # Allowed Chapter VI-A checks
        note(
            new_reg.allowed_chapter_via.issubset(old_reg.allowed_chapter_via)
            and new_reg.allowed_chapter_via < old_reg.allowed_chapter_via,
            "allowed_chapter_via for NEW must be a strict subset of OLD",
        )
        note(
            "80CCD2" in new_reg.allowed_chapter_via,
            "allowed_chapter_via for NEW must contain 80CCD2",
        )

        # Slabs check for all regimes & age bands
        for reg_enum, reg_params in p.regimes.items():
            for age_band, slabs in reg_params.slabs.items():
                last_upper: Decimal | None = None
                prev_rate: Decimal | None = None
                for i, (upper, rate) in enumerate(slabs):
                    if i == len(slabs) - 1:
                        note(upper is None, f"{reg_enum} {age_band} slabs must end with an open band (None)")
                    else:
                        note(upper is not None, f"{reg_enum} {age_band} non-final band missing upper bound")
                        if upper is not None and last_upper is not None:
                            note(upper > last_upper, f"{reg_enum} {age_band} slab upper bounds not strictly increasing")
                        last_upper = upper
                    if prev_rate is not None:
                        note(rate >= prev_rate, f"{reg_enum} {age_band} slab rates must be non-decreasing")
                    prev_rate = rate

        # Top rates
        new_top = next(rate for upper, rate in new_reg.slabs[list(new_reg.slabs.keys())[0]] if upper is None)
        old_top = next(rate for upper, rate in old_reg.slabs[list(old_reg.slabs.keys())[0]] if upper is None)
        note(new_top == Decimal("0.30") and old_top == Decimal("0.30"), "new and old regime top rates must be 0.30")

    # Surcharge checks
    if Regime.NEW in p.surcharge and Regime.OLD in p.surcharge:
        new_sur = p.surcharge[Regime.NEW]
        old_sur = p.surcharge[Regime.OLD]

        for reg_enum, sur in p.surcharge.items():
            last_upper = None
            prev_rate = None
            for i, (upper, rate) in enumerate(sur.bands):
                if i == len(sur.bands) - 1:
                    note(upper is None, f"{reg_enum} surcharge bands must end with an open band")
                else:
                    note(upper is not None, f"{reg_enum} non-final surcharge band missing upper bound")
                    if upper is not None and last_upper is not None:
                        note(upper > last_upper, f"{reg_enum} surcharge bounds not increasing")
                    last_upper = upper
                if prev_rate is not None:
                    note(rate >= prev_rate, f"{reg_enum} surcharge rates must be non-decreasing")
                prev_rate = rate

        # New-regime max rate <= old-regime max rate
        new_max = sur.bands[-1][1]
        old_max = old_sur.bands[-1][1]
        note(new_max <= old_max, "new-regime max surcharge rate must be <= old-regime max surcharge rate")

    # Chapter VI-A sections check
    for sec in p.chapter_via.limits:
        note(sec in KNOWN_CHAPTER_VIA_SECTIONS, f"Unknown Chapter VI-A section '{sec}'")

    return issues


def validate_all(registry: dict[Any, TaxYearParams] | None = None) -> list[str]:
    from app.tax_rules.params import _REGISTRY
    reg = registry if registry is not None else _REGISTRY
    seen_years = set()
    issues: list[str] = []
    for params in reg.values():
        if params.financial_year not in seen_years:
            seen_years.add(params.financial_year)
            issues.extend(validate_params(params))
    return issues
