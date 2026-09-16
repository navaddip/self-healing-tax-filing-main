"""Deterministic federal income-tax engine.

No LLM is imported here on purpose: every number is produced by auditable,
unit-tested arithmetic driven by the versioned parameters in ``app.tax_rules``.

The flow mirrors a real Form 1040: income -> AGI -> deductions -> taxable
income -> tax (Tax Tables under $100k, Tax Computation Worksheet at/above) ->
preferential rates for qualified dividends & net long-term capital gain ->
nonrefundable credits -> other federal taxes -> payments -> refund/balance due.
All amounts use the IRS whole-dollar method.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

from app.schemas import FilingStatus, TaxCalculation, TaxpayerData
from app.tax_rules.params import (
    Bracket,
    TaxYearParams,
    get_params,
    progressive_tax,
)


ZERO = Decimal("0")
DOLLAR = Decimal("1")


def dollars(value: Decimal) -> Decimal:
    """Round to whole dollars (IRS whole-dollar method)."""
    return Decimal(value).quantize(DOLLAR, rounding=ROUND_HALF_UP)


def _bracket_formula(amount: Decimal, brackets: list[Bracket]) -> Decimal:
    """Exact progressive tax on ``amount`` (the Tax Computation Worksheet)."""
    return progressive_tax(amount, brackets)


def tax_liability(amount: Decimal, params: TaxYearParams, fs: FilingStatus) -> Decimal:
    """Tax on taxable income: IRS Tax Table under $100k, worksheet otherwise."""
    amount = dollars(max(ZERO, amount))
    brackets = params.brackets[fs]
    if amount <= 0:
        return ZERO
    if amount < Decimal("100000"):
        # Tax Tables look up the $50 band ($25 below $3,000) and tax its midpoint.
        band = Decimal("50") if amount >= Decimal("3000") else Decimal("25")
        lower = (amount // band) * band
        midpoint = lower + band / 2
        return dollars(_bracket_formula(midpoint, brackets))
    return dollars(_bracket_formula(amount, brackets))


def _preferential_tax(
    ordinary_ti: Decimal,
    pref_income: Decimal,
    params: TaxYearParams,
    fs: FilingStatus,
) -> Decimal:
    """Tax on qualified dividends + net LTCG via the stacking method (0/15/20%)."""
    if pref_income <= 0:
        return ZERO
    zero_max = params.preferential.zero_rate_max[fs]
    fifteen_max = params.preferential.fifteen_rate_max[fs]
    bottom = ordinary_ti
    top = ordinary_ti + pref_income
    zero_amt = max(ZERO, min(top, zero_max) - bottom)
    fifteen_amt = max(ZERO, min(top, fifteen_max) - max(bottom, zero_max))
    twenty_amt = pref_income - zero_amt - fifteen_amt
    return dollars(fifteen_amt * Decimal("0.15") + twenty_amt * Decimal("0.20"))


def _additional_standard_deduction(
    data: TaxpayerData, params: TaxYearParams
) -> Decimal:
    """Extra standard deduction boxes for being 65+ or blind."""
    boxes = sum([data.age_65_plus, data.blind])
    if data.filing_status == FilingStatus.MARRIED_JOINTLY:
        boxes += sum([data.spouse_65_plus, data.spouse_blind])
    married = data.filing_status in (
        FilingStatus.MARRIED_JOINTLY,
        FilingStatus.MARRIED_SEPARATELY,
    )
    per_box = (
        params.additional_std_married if married else params.additional_std_unmarried
    )
    return per_box * boxes


def _senior_deduction(
    data: TaxpayerData, params: TaxYearParams, agi: Decimal
) -> Decimal:
    """OBBBA bonus deduction for taxpayers 65+ (2025-2028), phased out by MAGI."""
    if not params.senior_deduction:
        return ZERO
    eligible = sum(
        [
            data.age_65_plus,
            data.spouse_65_plus and data.filing_status == FilingStatus.MARRIED_JOINTLY,
        ]
    )
    if not eligible:
        return ZERO
    amount = params.senior_deduction * eligible
    start = (params.senior_deduction_phaseout_start or {}).get(data.filing_status)
    rate = params.senior_deduction_phaseout_rate
    if start is not None and rate is not None and agi > start:
        amount = max(ZERO, amount - (agi - start) * rate)
    return dollars(amount)


def _self_employment_tax(
    data: TaxpayerData, params: TaxYearParams
) -> tuple[Decimal, Decimal]:
    """Schedule SE tax and the deductible (one-half) adjustment."""
    if data.self_employment_income <= 0:
        return ZERO, ZERO
    se_base = data.self_employment_income * params.se_net_factor
    if se_base <= 0:
        return ZERO, ZERO
    oasdi_room = max(ZERO, params.ss_wage_base - data.ss_wages)
    oasdi = min(se_base, oasdi_room) * Decimal("0.124")
    medicare = se_base * Decimal("0.029")
    se_tax = dollars(oasdi + medicare)
    return se_tax, dollars(se_tax / 2)


def _additional_medicare_tax(
    data: TaxpayerData, params: TaxYearParams, se_base: Decimal
) -> Decimal:
    medicare_wages = data.medicare_wages or data.wages
    threshold = params.addl_medicare_threshold[data.filing_status]
    over = max(ZERO, medicare_wages + max(ZERO, se_base) - threshold)
    return dollars(over * params.addl_medicare_rate)


def _niit(
    data: TaxpayerData,
    params: TaxYearParams,
    agi: Decimal,
    net_capital_gain: Decimal,
) -> Decimal:
    nii = (
        data.taxable_interest
        + data.ordinary_dividends
        + max(ZERO, net_capital_gain)
    )
    threshold = params.niit_threshold[data.filing_status]
    base = min(nii, max(ZERO, agi - threshold))
    return dollars(base * params.niit_rate)


def _credits(
    data: TaxpayerData,
    params: TaxYearParams,
    agi: Decimal,
    tax_before_credits: Decimal,
    earned_income: Decimal,
) -> dict[str, Decimal]:
    """Child Tax Credit / Credit for Other Dependents incl. refundable ACTC."""
    c = params.credits
    child_potential = c.ctc_per_child * data.qualifying_children
    odc_potential = c.odc_per_dependent * data.other_dependents
    total_potential = child_potential + odc_potential
    if total_potential <= 0:
        return {
            "child_tax_credit": ZERO,
            "other_dependent_credit": ZERO,
            "refundable_child_tax_credit": ZERO,
        }

    threshold = c.phaseout_start[data.filing_status]
    reduction = ZERO
    if agi > threshold:
        steps = math.ceil((agi - threshold) / Decimal("1000"))
        reduction = c.phaseout_per_1000 * steps
    # Phase out ODC first, then the CTC.
    odc_after = max(ZERO, odc_potential - reduction)
    leftover = max(ZERO, reduction - odc_potential)
    child_after = max(ZERO, child_potential - leftover)

    available = max(ZERO, tax_before_credits)
    odc_used = min(odc_after, available)
    available -= odc_used
    ctc_nonref = min(child_after, available)

    # Refundable Additional CTC: lesser of unused CTC, 15% of earned income over
    # $2,500, and the per-child refundable cap.
    unused = child_after - ctc_nonref
    earned_limit = max(ZERO, (earned_income - Decimal("2500")) * Decimal("0.15"))
    per_child_cap = c.ctc_refundable_cap * data.qualifying_children
    actc = min(unused, earned_limit, per_child_cap)
    return {
        "child_tax_credit": dollars(ctc_nonref),
        "other_dependent_credit": dollars(odc_used),
        "refundable_child_tax_credit": dollars(actc),
    }


def _eitc(
    data: TaxpayerData,
    params: TaxYearParams,
    agi: Decimal,
    earned_income: Decimal,
    investment_income: Decimal,
) -> Decimal:
    """Earned Income Tax Credit (refundable).

    Uses the statutory formula (phase-in to a plateau, then phase-out on the
    greater of earned income or AGI). The IRS publishes this as a lookup table;
    the formula is a faithful, documented approximation.
    """
    if params.eitc is None:
        return ZERO
    if data.filing_status == FilingStatus.MARRIED_SEPARATELY:
        return ZERO  # generally ineligible
    if earned_income <= 0:
        return ZERO
    if investment_income > params.eitc.investment_income_limit:
        return ZERO

    tier = params.eitc.tiers[min(data.qualifying_children, 3)]
    credit = min(tier.max_credit, earned_income * tier.credit_rate)
    phaseout_begin = (
        tier.phaseout_begin_mfj
        if data.filing_status == FilingStatus.MARRIED_JOINTLY
        else tier.phaseout_begin_other
    )
    measure = max(agi, earned_income)
    if measure > phaseout_begin:
        credit -= (measure - phaseout_begin) * tier.phaseout_rate
    return max(ZERO, dollars(credit))


def _phaseout_factor(agi: Decimal, start: Decimal, end: Decimal) -> Decimal:
    if agi <= start:
        return Decimal("1")
    if agi >= end:
        return ZERO
    return (end - agi) / (end - start)


def _education_credits(
    data: TaxpayerData, params: TaxYearParams, agi: Decimal
) -> tuple[Decimal, Decimal]:
    """Return (nonrefundable AOTC+LLC, refundable AOTC)."""
    ed = params.education
    if ed is None or data.qualified_tuition <= 0:
        return ZERO, ZERO
    if data.filing_status not in ed.phaseout:  # MFS is ineligible
        return ZERO, ZERO
    start, end = ed.phaseout[data.filing_status]
    factor = _phaseout_factor(agi, start, end)
    if factor <= 0:
        return ZERO, ZERO

    nonref = ZERO
    refundable = ZERO
    remaining_tuition = data.qualified_tuition
    if data.aotc_students > 0:
        exp_per = data.qualified_tuition / data.aotc_students
        credit_per = min(Decimal("2000"), exp_per) + Decimal("0.25") * min(
            Decimal("2000"), max(ZERO, exp_per - Decimal("2000"))
        )
        credit_per = min(credit_per, ed.aotc_max_per_student)
        aotc = credit_per * data.aotc_students * factor
        refundable = aotc * ed.aotc_refundable_rate
        nonref += aotc - refundable
        # Expenses consumed by AOTC ($4k/student) are unavailable for the LLC.
        remaining_tuition = max(
            ZERO, data.qualified_tuition - Decimal("4000") * data.aotc_students
        )

    nonref += ed.llc_rate * min(remaining_tuition, ed.llc_expense_cap) * factor
    return dollars(nonref), dollars(refundable)


def _savers_credit(
    data: TaxpayerData, params: TaxYearParams, agi: Decimal
) -> Decimal:
    sv = params.savers
    if sv is None or data.retirement_contributions <= 0:
        return ZERO
    cap = sv.contribution_cap * (
        2 if data.filing_status == FilingStatus.MARRIED_JOINTLY else 1
    )
    eligible = min(data.retirement_contributions, cap)
    rate = ZERO
    for ceiling, tier_rate in sv.tiers.get(data.filing_status, []):
        if agi <= ceiling:
            rate = tier_rate
            break
    return dollars(eligible * rate)


_SS_BASE = {
    FilingStatus.MARRIED_JOINTLY: (Decimal("32000"), Decimal("44000")),
    FilingStatus.MARRIED_SEPARATELY: (ZERO, ZERO),
}
_SS_BASE_DEFAULT = (Decimal("25000"), Decimal("34000"))


def _taxable_social_security(data: TaxpayerData, agi_excluding_ss: Decimal) -> Decimal:
    """Taxable portion of Social Security benefits (Pub 915 worksheet)."""
    ss = data.social_security_benefits
    if ss <= 0:
        return ZERO
    base1, base2 = _SS_BASE.get(data.filing_status, _SS_BASE_DEFAULT)
    half = ss / 2
    provisional = agi_excluding_ss + data.tax_exempt_interest + half
    if provisional <= base1:
        taxable = ZERO
    elif provisional <= base2:
        taxable = min(half, (provisional - base1) / 2)
    else:
        lower_tier = min(half, (base2 - base1) / 2)
        taxable = min(
            ss * Decimal("0.85"),
            (provisional - base2) * Decimal("0.85") + lower_tier,
        )
    return dollars(min(taxable, ss * Decimal("0.85")))


def _itemized(data: TaxpayerData, agi: Decimal) -> tuple[Decimal, Decimal]:
    """Schedule A total and the SALT amount allowed (for the AMT add-back)."""
    salt_capped = min(data.salt_paid, Decimal("10000"))
    line_items = (
        data.salt_paid
        + data.mortgage_interest
        + data.medical_expenses
        + data.charitable_contributions
    )
    computed = ZERO
    if line_items > 0:
        medical = max(ZERO, data.medical_expenses - Decimal("0.075") * agi)
        charitable = min(data.charitable_contributions, Decimal("0.60") * agi)
        computed = salt_capped + data.mortgage_interest + medical + charitable
    return dollars(max(computed, data.itemized_deductions)), salt_capped


def _amt(
    data: TaxpayerData,
    params: TaxYearParams,
    agi: Decimal,
    qbi_deduction: Decimal,
    amt_deduction: Decimal,
    regular_tax_before_credits: Decimal,
) -> Decimal:
    """Alternative Minimum Tax (Form 6251, simplified).

    AMTI = AGI - QBI - (itemized deductions allowed for AMT, i.e. excluding the
    SALT add-back) + explicit preference items. When the standard deduction is
    taken, ``amt_deduction`` is 0 so the full standard deduction is added back.
    """
    amt = params.amt
    if amt is None:
        return ZERO
    fs = data.filing_status
    amti = max(
        ZERO, agi - qbi_deduction - amt_deduction + data.amt_preference_items
    )
    exemption = max(
        ZERO,
        amt.exemption[fs]
        - Decimal("0.25") * max(ZERO, amti - amt.phaseout_start[fs]),
    )
    base = max(ZERO, amti - exemption)
    threshold = amt.rate_28_threshold
    if fs == FilingStatus.MARRIED_SEPARATELY:
        threshold /= 2
    tentative_min = Decimal("0.26") * min(base, threshold) + Decimal(
        "0.28"
    ) * max(ZERO, base - threshold)
    return max(ZERO, dollars(tentative_min) - regular_tax_before_credits)


class TaxCalculator:
    def calculate(self, data: TaxpayerData) -> TaxCalculation:
        params = get_params(data.tax_year)
        # QSS uses MFJ rates, deduction, and thresholds in full.
        if data.filing_status == FilingStatus.QUALIFYING_SURVIVING_SPOUSE:
            data = data.model_copy(
                update={"filing_status": FilingStatus.MARRIED_JOINTLY}
            )
        fs = data.filing_status
        trace: list[str] = []

        # --- Self-employment tax (half is an above-the-line adjustment) ---
        se_tax, se_deduction = _self_employment_tax(data, params)
        se_base = data.self_employment_income * params.se_net_factor

        # --- Capital gains with prior-year carryover; track carryforward ---
        loss_cap = (
            Decimal("1500")
            if fs == FilingStatus.MARRIED_SEPARATELY
            else Decimal("3000")
        )
        net_capital_gain = (
            data.long_term_capital_gain
            + data.short_term_capital_gain
            - data.capital_loss_carryover
        )
        capital_reported = (
            net_capital_gain
            if net_capital_gain >= 0
            else max(net_capital_gain, -loss_cap)
        )
        capital_loss_carryforward = (
            dollars(-net_capital_gain - loss_cap)
            if net_capital_gain < -loss_cap
            else ZERO
        )

        # --- Income (Social Security taxability depends on the rest of AGI) ---
        income_excl_ss = (
            data.wages
            + data.taxable_interest
            + data.ordinary_dividends
            + capital_reported
            + data.self_employment_income
            + data.partnership_income
            + data.taxable_pension_ira
            + data.other_income
        )
        adjustments = dollars(data.adjustments + se_deduction)
        agi_excl_ss = income_excl_ss - adjustments
        taxable_ss = _taxable_social_security(data, agi_excl_ss)
        total_income = dollars(income_excl_ss + taxable_ss)
        agi = dollars(total_income - adjustments)
        trace.append(f"Total income: {total_income} (taxable SS {taxable_ss})")
        trace.append(f"Adjustments (incl. 1/2 SE tax {se_deduction}): {adjustments}")
        trace.append(f"AGI: {agi}")

        # --- Deductions (standard stack vs. Schedule A itemized) ---
        standard = params.standard_deductions[fs]
        additional_std = _additional_standard_deduction(data, params)
        senior = _senior_deduction(data, params, agi)
        std_stack = standard + additional_std
        itemized_total, salt_capped = _itemized(data, agi)
        itemizing = itemized_total > std_stack
        base_deduction = max(std_stack, itemized_total)
        deduction = dollars(base_deduction + senior)
        taxable_before_qbi = dollars(max(ZERO, agi - deduction))
        # Deduction allowed when recomputing AMTI (SALT added back if itemizing).
        amt_deduction = (itemized_total - salt_capped) if itemizing else ZERO

        # --- QBI deduction (Form 8995, simplified below-threshold method) ---
        # Net qualified business income = SE profit less the deductible half of
        # SE tax. Limited to 20% of (taxable income before QBI - net cap gain).
        preferential_amount = data.qualified_dividends + max(
            ZERO, min(data.long_term_capital_gain, capital_reported)
        )
        qbi = max(ZERO, data.self_employment_income - se_deduction)
        qbi_component = params.qbi_rate * qbi
        qbi_income_limit = params.qbi_rate * max(
            ZERO, taxable_before_qbi - preferential_amount
        )
        qbi_deduction = dollars(min(qbi_component, qbi_income_limit))
        taxable_income = dollars(max(ZERO, taxable_before_qbi - qbi_deduction))
        trace.append(
            f"Deduction: max(std {std_stack}, itemized {itemized_total}) "
            f"+ senior {senior} = {deduction}"
        )
        if qbi_deduction:
            trace.append(f"QBI deduction (Form 8995): {qbi_deduction}")
        trace.append(f"Taxable income: {taxable_income}")

        # --- Income tax (ordinary + preferential), capped at regular tax ---
        pref_income = min(preferential_amount, taxable_income)
        ordinary_ti = dollars(max(ZERO, taxable_income - pref_income))
        ordinary_tax = tax_liability(ordinary_ti, params, fs)
        preferential_tax = _preferential_tax(ordinary_ti, pref_income, params, fs)
        regular_full = tax_liability(taxable_income, params, fs)
        income_tax = min(ordinary_tax + preferential_tax, regular_full)
        used_table = taxable_income < Decimal("100000")
        trace.append(
            f"Income tax: ordinary {ordinary_tax} + preferential {preferential_tax} "
            f"(capped at {regular_full}) = {income_tax} "
            f"[{'Tax Table' if used_table else 'Tax Computation Worksheet'}]"
        )

        # --- Nonrefundable credits (applied in 1040 order against tax) ---
        earned_income = data.wages + max(ZERO, data.self_employment_income)
        ed_nonref, refundable_aotc = _education_credits(data, params, agi)
        savers = _savers_credit(data, params, agi)
        available = income_tax
        ed_used = min(ed_nonref, available)
        available -= ed_used
        savers_used = min(savers, available)
        available -= savers_used
        # CTC/ODC limited to the tax remaining after the other credits.
        credits = _credits(data, params, agi, available, earned_income)
        nonrefundable = dollars(
            ed_used
            + savers_used
            + credits["child_tax_credit"]
            + credits["other_dependent_credit"]
        )
        income_tax_after_credits = dollars(max(ZERO, income_tax - nonrefundable))
        if nonrefundable:
            trace.append(
                f"Nonrefundable credits (CTC {credits['child_tax_credit']}, ODC "
                f"{credits['other_dependent_credit']}, education {ed_used}, "
                f"savers {savers_used}): -{nonrefundable}"
            )

        # --- Other federal taxes ---
        addl_medicare = _additional_medicare_tax(data, params, se_base)
        niit = _niit(data, params, agi, capital_reported)
        amt = _amt(data, params, agi, qbi_deduction, amt_deduction, income_tax)
        other_taxes = dollars(se_tax + addl_medicare + niit + amt)
        if other_taxes:
            trace.append(
                f"Other taxes: SE {se_tax} + addl Medicare {addl_medicare} "
                f"+ NIIT {niit} + AMT {amt}"
            )

        federal_total_tax = dollars(income_tax_after_credits + other_taxes)

        # --- Refundable Earned Income Tax Credit ---
        eitc_earned = data.wages + max(ZERO, data.self_employment_income - se_deduction)
        investment_income = (
            data.taxable_interest
            + data.tax_exempt_interest
            + data.ordinary_dividends
            + max(ZERO, capital_reported)
        )
        eitc = _eitc(data, params, agi, eitc_earned, investment_income)
        if eitc:
            trace.append(f"Earned Income Tax Credit (refundable): {eitc}")

        # --- State tax: installed per-state rule pack first, then the flat-rate
        # fallback. A pack models real state law and overrides the supplied
        # flat rate; absent a pack, state_tax_rate (default 0) is used. ---
        state_tax = ZERO
        pack = get_state_pack(data.state, data.tax_year)
        if pack is not None:
            federal_ctx = FederalContext(
                filing_status=fs,
                agi=agi,
                taxable_income=taxable_income,
                taxable_social_security=taxable_ss,
            )
            state_result = pack.compute(data, federal_ctx)
            state_tax = dollars(state_result.tax)
            trace.extend(state_result.trace)
            if not pack.verified:
                trace.append(
                    f"[unverified] {pack.state} {pack.year} state pack: {pack.source}"
                )
        elif data.state_tax_rate > 0:
            state_tax = dollars(taxable_income * data.state_tax_rate)
            trace.append(f"State tax (flat {data.state_tax_rate}): {state_tax}")

        # --- Payments ---
        max_ss = dollars(params.ss_wage_base * params.ss_rate)
        excess_ss = (
            dollars(data.ss_tax_withheld - max_ss)
            if data.employer_count >= 2 and data.ss_tax_withheld > max_ss
            else ZERO
        )
        federal_withholding = dollars(data.federal_tax_withheld)
        state_withholding = dollars(data.state_tax_withheld)
        federal_payments = dollars(
            federal_withholding
            + data.estimated_payments
            + excess_ss
            + credits["refundable_child_tax_credit"]
            + eitc
            + refundable_aotc
        )
        # The 1040 refund/balance is FEDERAL only; state withholding is not a
        # federal payment (a state return is separate and only computed when a
        # state rate is supplied).
        federal_net = federal_payments - federal_total_tax
        state_net = state_withholding - state_tax

        total_tax = dollars(federal_total_tax + state_tax)
        total_withholding = dollars(federal_withholding + state_withholding)
        total_payments = dollars(federal_payments + state_withholding)

        return TaxCalculation(
            gross_income=total_income,
            total_income=total_income,
            taxable_social_security=taxable_ss,
            capital_loss_carryforward=capital_loss_carryforward,
            adjustments=adjustments,
            adjusted_gross_income=agi,
            standard_deduction=dollars(standard),
            additional_standard_deduction=additional_std,
            senior_deduction=senior,
            deductions=deduction,
            qbi_deduction=qbi_deduction,
            taxable_income=taxable_income,
            ordinary_taxable_income=ordinary_ti,
            ordinary_tax=ordinary_tax,
            preferential_tax=preferential_tax,
            income_tax_before_credits=income_tax,
            tax_table_used=used_table,
            child_tax_credit=credits["child_tax_credit"],
            other_dependent_credit=credits["other_dependent_credit"],
            education_credits=ed_used,
            savers_credit=savers_used,
            nonrefundable_credits=nonrefundable,
            self_employment_tax=se_tax,
            additional_medicare_tax=addl_medicare,
            net_investment_income_tax=niit,
            alternative_minimum_tax=amt,
            other_taxes=other_taxes,
            federal_tax=federal_total_tax,
            state_tax=state_tax,
            total_tax=total_tax,
            total_withholding=total_withholding,
            estimated_payments=dollars(data.estimated_payments),
            excess_ss_credit=excess_ss,
            refundable_child_tax_credit=credits["refundable_child_tax_credit"],
            earned_income_credit=eitc,
            refundable_education_credit=refundable_aotc,
            total_payments=total_payments,
            refund=max(ZERO, federal_net),
            tax_due=max(ZERO, -federal_net),
            state_refund=max(ZERO, state_net),
            state_balance_due=max(ZERO, -state_net),
            params_verified=params.verified,
            trace=trace,
        )
