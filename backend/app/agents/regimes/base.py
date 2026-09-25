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
    return sum(
        (component["tax"] for component in slab_tax_components(normal_taxable_income, slabs)),
        Decimal("0"),
    )


def slab_tax_components(
    normal_taxable_income: Decimal,
    slabs: list[tuple[Decimal | None, Decimal]],
) -> list[dict[str, Decimal | None]]:
    """Return the auditable progressive-tax contribution of every slab.

    The component sum is the source of truth for slab tax.  Keeping the
    breakdown next to the arithmetic prevents a report from rendering a slab
    table that belongs to another assessment year.
    """
    amount = max(Decimal("0"), normal_taxable_income)
    lower = Decimal("0")
    components: list[dict[str, Decimal | None]] = []
    for upper, rate in slabs:
        band_top = amount if upper is None else min(amount, upper)
        taxable = max(Decimal("0"), band_top - lower)
        components.append(
            {
                "lower": lower,
                "upper": upper,
                "rate": rate,
                "taxable": taxable,
                "tax": taxable * rate,
            }
        )
        if upper is None:
            break
        lower = upper
    return components


def calculate_taxable_income_liability(
    taxable_income: Decimal,
    regime: Regime,
    params: TaxYearParams,
    age_band: AgeBand = AgeBand.BELOW_60,
    is_resident: bool = True,
    round_taxable_income: bool = True,
) -> dict[str, object]:
    """Calculate ordinary-income tax from a taxable-income probe.

    This canonical probe is used by breakeven and sensitivity analysis.  It
    deliberately accepts taxable income, rather than fabricating claims in
    capped Chapter VI-A sections, while reusing the production slab, rebate,
    surcharge, cess and rounding functions.
    """
    raw_income = max(Decimal("0"), taxable_income)
    income = round_to_ten(raw_income) if round_taxable_income else raw_income
    applicable_age = age_band if (is_resident or regime == Regime.NEW) else AgeBand.BELOW_60
    components = slab_tax_components(income, params.regimes[regime].slabs[applicable_age])
    before_rebate = sum((c["tax"] for c in components), Decimal("0"))
    rebate, rebate_relief = rebate_87a(
        income, before_rebate, Decimal("0"), regime, params, is_resident
    )
    after_rebate = max(Decimal("0"), before_rebate - rebate - rebate_relief)
    sur, sur_relief = surcharge(
        income, after_rebate, Decimal("0"), regime, params, applicable_age
    )
    cess_amount = cess(after_rebate + sur, params.cess_rate)
    exact_total = after_rebate + sur + cess_amount
    return {
        "taxable_income": income,
        "slab_components": components,
        "tax_before_rebate": before_rebate,
        "rebate_87a": rebate,
        "marginal_relief_87a": rebate_relief,
        "tax_after_rebate": after_rebate,
        "surcharge": sur,
        "surcharge_marginal_relief": sur_relief,
        "cess": cess_amount,
        "total_tax_exact": exact_total,
        "total_tax_liability": round_to_ten(exact_total),
    }


def basic_exemption_limit(slabs: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    """Maximum amount not chargeable to tax: the upper bound of the nil-rate slab."""
    upper, rate = slabs[0]
    return upper if upper is not None and rate == Decimal("0") else Decimal("0")


def absorb_basic_exemption(
    income: HeadwiseIncome,
    normal_income: Decimal,
    basic_exemption: Decimal,
) -> HeadwiseIncome:
    """Set unused basic exemption against 111A/112/112A income (provisos to those sections).

    Available to resident individuals only; 115BB winnings never absorb it.
    The highest-rate income (111A) is reduced first.
    """
    shortfall = max(Decimal("0"), basic_exemption - normal_income)
    if shortfall == Decimal("0"):
        return income
    update: dict[str, Decimal] = {}
    for field in ("stcg_111a", "ltcg_112", "ltcg_112a_taxable"):
        amount = getattr(income, field)
        used = min(shortfall, amount)
        update[field] = amount - used
        shortfall -= used
    return income.model_copy(update=update)


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

    # Section 115BB (Winnings from lottery, betting, games, etc.)
    winnings = getattr(income, "winnings_115bb", Decimal("0"))
    t_115bb = winnings * cg.winnings_115bb_rate
    breakdown["115BB"] = t_115bb

    total = t_111a + t_112a + t_112 + t_115bb
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
        # Available on slab tax and eligible special rate taxes (excluding LTCG 112A per Sec 112A(6))
        if total_income <= reg_params.rebate_limit:
            rebate_base = slab_tax_amount + special_tax_amount
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
    data=None,
    basic_exemption: Decimal = Decimal("0"),
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

    if filing_date and due_date:
        is_belated = filing_date > due_date

    # 234F Late filing fee; proviso: no fee when total income is within the basic exemption
    if is_belated and total_income > basic_exemption:
        if total_income <= int_params.fee_234f_income_threshold:
            out["fee_234f"] = int_params.fee_234f_low
        else:
            out["fee_234f"] = int_params.fee_234f_high

    # 234A Interest for delay in filing return (Rule 119A: round tax base down to nearest ₹100)
    if is_belated and unpaid_tax > Decimal("0") and filing_date and due_date:
        if filing_date > due_date:
            months = Decimal(str(max(1, (filing_date.year - due_date.year) * 12 + filing_date.month - due_date.month)))
            out["interest_234a"] = (unpaid_tax // 100 * 100) * int_params.rate_234a * months

    # Advance-tax interest for ordinary salary/interest income. Instalment
    # dictionary values are individual payments, keyed by ISO date or due label.
    if data is not None:
        exempt = data.age_band != AgeBand.BELOW_60 and data.residential_status != ResidentialStatus.NON_RESIDENT and not data.presumptive
        credits = data.taxes_paid.tds_salary + data.taxes_paid.tds_non_salary + data.taxes_paid.tcs + data.taxes_paid.relief_89 + data.taxes_paid.relief_90_91
        assessed = max(Decimal("0"), total_tax_liability - credits)
        if not exempt and assessed >= int_params.advance_tax_threshold:
            fy = params.year
            schedule_dates = [date(fy, 6, 15), date(fy, 9, 15), date(fy, 12, 15), date(fy + 1, 3, 15)]
            aliases = dict(zip([item[0] for item in int_params.advance_tax_schedule], schedule_dates))
            payments = []
            for key, amount in data.taxes_paid.advance_tax_instalments.items():
                try:
                    paid_on = aliases[key] if key in aliases else date.fromisoformat(key)
                except ValueError as exc:
                    raise ValueError("Advance tax payments require ISO dates or rule-pack instalment labels") from exc
                if amount < 0:
                    raise ValueError("Advance tax payments cannot be negative")
                payments.append((paid_on, amount))
            def paid_by(day):
                return sum((amount for paid_on, amount in payments if paid_on <= day), Decimal("0"))
            def base(amount):
                return max(Decimal("0"), amount) // 100 * 100
            advance = paid_by(date(fy + 1, 3, 31))
            end = filing_date or params.filing_due_date
            if advance < assessed * Decimal("0.90") and end >= date(fy + 1, 4, 1):
                months = (end.year - fy - 1) * 12 + end.month - 4 + 1
                out["interest_234b"] = base(assessed - advance) * int_params.rate_234b * months
            for i, (label, required, tolerance) in enumerate(int_params.advance_tax_schedule):
                if data.presumptive and data.presumptive.section in ("44AD", "44ADA") and i < 3:
                    continue
                paid = paid_by(schedule_dates[i])
                if paid < assessed * tolerance:
                    out["interest_234c"] += base(assessed * required - paid) * int_params.rate_234c * (1 if i == 3 else 3)
    return out
