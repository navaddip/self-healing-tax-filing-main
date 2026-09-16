"""Base arithmetic functions for Indian income tax regimes.

Both Old Regime and New Regime share the exact same computational structure;
they differ only in parameter pack constants (slabs, thresholds, allowed deductions).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.tax import (
    AgeBand,
    HeadwiseIncome,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
)
from app.tax_rules.params import CapitalGainParams, TaxYearParams, progressive_tax


def round_to_ten(value: Decimal) -> Decimal:
    """Round to nearest ₹10 under Section 288A/288B using ROUND_HALF_UP."""
    return (value / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")


def slab_tax(
    normal_taxable_income: Decimal,
    slabs: list[tuple[Decimal | None, Decimal]],
) -> Decimal:
    """Compute tax on normal income using progressive slabs."""
    if normal_taxable_income <= Decimal("0"):
        return Decimal("0")
    return progressive_tax(normal_taxable_income, slabs)


def special_rate_tax(
    income: HeadwiseIncome,
    cg: CapitalGainParams,
) -> tuple[Decimal, dict[str, Decimal]]:
    """Compute tax on special-rate incomes.

    Sections:
    - 111A (STCG listed equity): 20%
    - 112A (LTCG listed equity): 12.5% on amount exceeding ₹1,25,000
    - 112 (LTCG property/unlisted): 12.5% (or indexation equivalent)
    - 115BB (Winnings): 30%
    """
    breakdown: dict[str, Decimal] = {}

    # Section 111A
    t_111a = income.stcg_111a * cg.stcg_111a_rate
    breakdown["111A"] = t_111a

    # Section 112A (taxable slice)
    t_112a = income.ltcg_112a_taxable * cg.ltcg_112a_rate
    breakdown["112A"] = t_112a

    # Section 112
    t_112 = income.ltcg_112 * cg.ltcg_112_rate
    breakdown["112"] = t_112

    total = t_111a + t_112a + t_112
    return total, breakdown


def rebate_87a(
    total_income: Decimal,
    slab_tax_amount: Decimal,
    special_tax_amount: Decimal,
    regime: Regime,
    params: TaxYearParams,
    is_resident: bool,
) -> tuple[Decimal, Decimal]:
    """Calculate Section 87A rebate and marginal relief.

    Returns:
        (rebate_87a, marginal_relief_87a)
    """
    if not is_resident:
        return Decimal("0"), Decimal("0")

    reg_params = params.regimes[regime]

    if regime == Regime.NEW:
        # Resident individual with total income <= ₹12,00,000
        # Rebate is on slab tax only (special rate income excluded)
        if total_income <= reg_params.rebate_limit:
            rebate = min(slab_tax_amount, reg_params.rebate_max)
            return rebate, Decimal("0")

        # Marginal relief under New Regime for income between ₹12,00,000 and ₹12,70,588
        if reg_params.rebate_marginal_relief:
            excess_income = total_income - reg_params.rebate_limit
            # Normal tax payable without rebate/relief
            tax_without_relief = slab_tax_amount
            if tax_without_relief > excess_income:
                marginal_relief = tax_without_relief - excess_income
                return Decimal("0"), marginal_relief

        return Decimal("0"), Decimal("0")

    else:
        # Old Regime: total income <= ₹5,00,000
        # Available on slab tax and STCG 111A, but not on LTCG 112A
        if total_income <= reg_params.rebate_limit:
            rebate_base = slab_tax_amount
            rebate = min(rebate_base, reg_params.rebate_max)
            return rebate, Decimal("0")

        return Decimal("0"), Decimal("0")


def surcharge(
    total_income: Decimal,
    tax_after_rebate: Decimal,
    special_tax: Decimal,
    regime: Regime,
    params: TaxYearParams,
    age_band: AgeBand = AgeBand.BELOW_60,
) -> tuple[Decimal, Decimal]:
    """Calculate Surcharge and Surcharge Marginal Relief.

    Returns:
        (effective_surcharge, marginal_relief)
    """
    sur_params = params.surcharge[regime]
    bands = sur_params.bands

    # Find applicable band rate
    band_rate = Decimal("0")
    crossed_threshold = Decimal("0")
    for upper, rate in bands:
        if upper is not None and total_income > upper:
            crossed_threshold = upper
        if upper is None or total_income <= upper:
            band_rate = rate
            break

    if band_rate == Decimal("0"):
        return Decimal("0"), Decimal("0")

    # If rate exceeds special income cap (15%), split normal vs special income tax
    normal_tax = max(Decimal("0"), tax_after_rebate - special_tax)
    if band_rate > sur_params.special_income_cap:
        raw_surcharge = (normal_tax * band_rate) + (special_tax * sur_params.special_income_cap)
    else:
        raw_surcharge = tax_after_rebate * band_rate

    # Apply Surcharge Marginal Relief at the crossed threshold (e.g. 50L, 1Cr, 2Cr)
    if sur_params.marginal_relief and crossed_threshold > Decimal("0"):
        # Tax at threshold
        slabs = params.regimes[regime].slabs[age_band]
        tax_at_threshold = slab_tax(crossed_threshold, slabs)
        # Check threshold surcharge rate
        thresh_sur_rate = Decimal("0")
        for up, r in bands:
            if up is None or crossed_threshold <= up:
                thresh_sur_rate = r
                break
        total_at_thresh = tax_at_threshold * (Decimal("1") + thresh_sur_rate)

        incremental_income = total_income - crossed_threshold
        incremental_tax = (tax_after_rebate + raw_surcharge) - total_at_thresh

        if incremental_tax > incremental_income:
            relief = incremental_tax - incremental_income
            relieved_surcharge = max(Decimal("0"), raw_surcharge - relief)
            return relieved_surcharge, relief

    return raw_surcharge, Decimal("0")


def cess(tax_plus_surcharge: Decimal, rate: Decimal = Decimal("0.04")) -> Decimal:
    """Calculate 4% Health and Education Cess."""
    return tax_plus_surcharge * rate


def interest_and_fees(
    total_tax_liability: Decimal,
    taxes_paid_total: Decimal,
    filing_date: date | None,
    due_date: date | None,
    params: TaxYearParams,
    is_belated: bool = False,
    total_income: Decimal = Decimal("0"),
) -> dict[str, Decimal]:
    """Calculate interest u/s 234A, 234B, 234C and late fee u/s 234F."""
    int_params = params.interest
    out = {
        "interest_234a": Decimal("0"),
        "interest_234b": Decimal("0"),
        "interest_234c": Decimal("0"),
        "fee_234f": Decimal("0"),
    }

    unpaid_tax = max(Decimal("0"), total_tax_liability - taxes_paid_total)

    # 234F Late filing fee
    if is_belated:
        if total_income <= int_params.fee_234f_income_threshold:
            out["fee_234f"] = int_params.fee_234f_low
        else:
            out["fee_234f"] = int_params.fee_234f_high

    # 234A Interest for delay in filing return
    if is_belated and unpaid_tax > Decimal("0") and filing_date and due_date:
        if filing_date > due_date:
            months = Decimal(str(max(1, (filing_date.year - due_date.year) * 12 + filing_date.month - due_date.month)))
            out["interest_234a"] = unpaid_tax * int_params.rate_234a * months

    return out
