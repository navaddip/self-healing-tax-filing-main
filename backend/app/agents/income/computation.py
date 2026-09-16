"""Deterministic Five Heads of Income Computation for Indian Income Tax.

LLMs read and classify. Deterministic code decides and computes.
Every number here is computed strictly per statutory provisions of the Income-tax Act.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.schemas.tax import (
    AgeBand,
    CapitalGainItem,
    HeadwiseIncome,
    HouseProperty,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
)
from app.tax_rules.params import TaxYearParams


def round_to_10(val: Decimal) -> Decimal:
    """Round to nearest ₹10 under Section 288A/288B using ROUND_HALF_UP."""
    return (val / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")


def hra_exemption(
    salary_breakup: SalaryBreakup | None,
    regime: Regime,
) -> tuple[Decimal, str]:
    """Calculate HRA exemption u/s 10(13A) under the Old Regime.

    Least of three:
    1. Actual HRA received
    2. 50% of (basic + DA) in metro (Delhi, Mumbai, Kolkata, Chennai), else 40%
    3. Rent paid minus 10% of (basic + DA), floored at 0
    Zero under the New Regime.
    """
    if regime == Regime.NEW or not salary_breakup:
        return Decimal("0"), "New regime / no salary breakup: HRA exemption = 0"

    if salary_breakup.rent_paid_annual <= Decimal("0"):
        return Decimal("0"), "Rent paid is 0: HRA exemption = 0"

    salary_base = salary_breakup.basic + salary_breakup.dearness_allowance
    actual_hra = salary_breakup.hra_received

    pct = Decimal("0.50") if salary_breakup.is_metro else Decimal("0.40")
    salary_pct_limit = salary_base * pct

    rent_over_10 = max(Decimal("0"), salary_breakup.rent_paid_annual - (salary_base * Decimal("0.10")))

    exempt = min(actual_hra, salary_pct_limit, rent_over_10)

    trace = (
        f"HRA u/s 10(13A): least of actual ({actual_hra}), "
        f"{'50%' if salary_breakup.is_metro else '40%'} salary ({salary_pct_limit}), "
        f"rent - 10% salary ({rent_over_10}) = {exempt}"
    )
    return exempt, trace


def apply_chapter_via(
    claims: dict[str, Decimal],
    gti: Decimal,
    special_rate_income: Decimal,
    data: IndianTaxpayerData,
    regime: Regime,
    params: TaxYearParams,
) -> tuple[dict[str, Decimal], Decimal, dict[str, Decimal], list[str]]:
    """Apply Chapter VI-A deductions strictly according to regime rules.

    Returns:
        (applied_dict, total_applied, disallowed_dict, traces)
    """
    reg_params = params.regimes[regime]
    limits = params.chapter_via
    allowed_sections = reg_params.allowed_chapter_via
    applied: dict[str, Decimal] = {}
    disallowed: dict[str, Decimal] = {}
    traces: list[str] = []

    # Maximum deductible amount: GTI reduced by special-rate capital gains/winnings
    max_deductible = max(Decimal("0"), gti - special_rate_income)

    # 1. First partition by allowed vs disallowed by regime
    for sec, raw_amount in claims.items():
        if raw_amount <= Decimal("0"):
            continue
        if sec not in allowed_sections:
            disallowed[sec] = raw_amount
            traces.append(f"Chapter VI-A: {sec} ({raw_amount}) disallowed under {regime} regime")

    # 2. Process allowed claims with per-section caps
    # Employer NPS 80CCD(2)
    if "80CCD2" in allowed_sections and "80CCD2" in claims:
        claim_80ccd2 = claims["80CCD2"]
        salary_base = Decimal("0")
        if data.salary_breakup:
            salary_base = data.salary_breakup.basic + data.salary_breakup.dearness_allowance
        elif data.form16s:
            # Fallback estimation if detailed breakup not present
            salary_base = sum(f.gross_salary_17_1 for f in data.form16s)

        max_nps = salary_base * reg_params.employer_nps_limit_pct
        eff_80ccd2 = min(claim_80ccd2, max_nps) if salary_base > Decimal("0") else claim_80ccd2
        applied["80CCD2"] = eff_80ccd2
        if claim_80ccd2 > eff_80ccd2:
            disallowed["80CCD2"] = claim_80ccd2 - eff_80ccd2
        traces.append(
            f"80CCD(2) Employer NPS: claimed {claim_80ccd2}, cap ({reg_params.employer_nps_limit_pct * 100}%) {max_nps} -> allowed {eff_80ccd2}"
        )

    # 80C, 80CCC, 80CCD(1) combined cap (Section 80CCE)
    if regime == Regime.OLD:
        c_claim = claims.get("80C", Decimal("0"))
        ccc_claim = claims.get("80CCC", Decimal("0"))
        ccd1_claim = claims.get("80CCD1", Decimal("0"))
        c_pool = c_claim + ccc_claim + ccd1_claim

        if c_pool > Decimal("0"):
            c_cap = limits.limits.get("80C", Decimal("150000"))
            allowed_c = min(c_pool, c_cap)
            applied["80C"] = allowed_c
            if c_pool > allowed_c:
                disallowed["80C"] = c_pool - allowed_c
            traces.append(f"80C+80CCC+80CCD(1): claimed {c_pool}, capped at {c_cap} -> allowed {allowed_c}")

        # 80CCD(1B) additional NPS ₹50,000
        if "80CCD1B" in claims:
            ccd1b = claims["80CCD1B"]
            ccd1b_cap = limits.limits.get("80CCD1B", Decimal("50000"))
            allowed_ccd1b = min(ccd1b, ccd1b_cap)
            applied["80CCD1B"] = allowed_ccd1b
            if ccd1b > allowed_ccd1b:
                disallowed["80CCD1B"] = ccd1b - allowed_ccd1b
            traces.append(f"80CCD(1B): claimed {ccd1b}, capped at {ccd1b_cap} -> allowed {allowed_ccd1b}")

        # 80D Health Insurance (with senior citizen variants)
        if "80D" in claims:
            d_claim = claims["80D"]
            d_cap = limits.senior_variants.get("80D", Decimal("50000")) if data.age_band != AgeBand.BELOW_60 else limits.limits.get("80D", Decimal("25000"))
            allowed_d = min(d_claim, d_cap)
            applied["80D"] = allowed_d
            if d_claim > allowed_d:
                disallowed["80D"] = d_claim - allowed_d
            traces.append(f"80D: claimed {d_claim}, capped at {d_cap} -> allowed {allowed_d}")

        # 80TTA / 80TTB Savings / Deposit interest
        if data.age_band == AgeBand.BELOW_60:
            if "80TTA" in claims:
                tta = claims["80TTA"]
                tta_cap = limits.limits.get("80TTA", Decimal("10000"))
                allowed_tta = min(tta, tta_cap)
                applied["80TTA"] = allowed_tta
                traces.append(f"80TTA: claimed {tta}, capped at {tta_cap} -> allowed {allowed_tta}")
        else:
            if "80TTB" in claims:
                ttb = claims["80TTB"]
                ttb_cap = limits.senior_variants.get("80TTB", Decimal("50000"))
                allowed_ttb = min(ttb, ttb_cap)
                applied["80TTB"] = allowed_ttb
                traces.append(f"80TTB: claimed {ttb}, capped at {ttb_cap} -> allowed {allowed_ttb}")

        # Other standard sections (80E, 80G, etc.)
        for sec in ["80E", "80G", "80GG", "80GGC", "80DD", "80DDB", "80U", "80JJAA", "80CCH"]:
            if sec in claims and sec not in applied:
                amt = claims[sec]
                cap = limits.limits.get(sec, Decimal("10000000"))
                allowed_sec = min(amt, cap)
                applied[sec] = allowed_sec
                if amt > allowed_sec:
                    disallowed[sec] = amt - allowed_sec
                traces.append(f"{sec}: claimed {amt}, allowed {allowed_sec}")

    total_applied = sum(applied.values(), Decimal("0"))
    if total_applied > max_deductible:
        traces.append(f"Chapter VI-A clamped from {total_applied} to max deductible GTI {max_deductible}")
        total_applied = max_deductible

    return applied, total_applied, disallowed, traces


class IncomeComputationService:
    """Computes five heads of income, inter-head set-off, Chapter VI-A, and GTI."""

    def compute(
        self,
        data: IndianTaxpayerData,
        regime: Regime,
        params: TaxYearParams,
    ) -> HeadwiseIncome:
        trace: list[str] = []
        reg_params = params.regimes[regime]

        # -------------------------------------------------------------
        # 1. SALARIES
        # -------------------------------------------------------------
        gross_salary = Decimal("0")
        for f16 in data.form16s:
            gross_salary += (
                f16.gross_salary_17_1
                + f16.perquisites_17_2
                + f16.profits_in_lieu_17_3
            )
        if gross_salary == Decimal("0") and data.salary_breakup:
            # Derived from salary breakup if no Form 16 attached
            gross_salary = (
                data.salary_breakup.basic
                + data.salary_breakup.dearness_allowance
                + data.salary_breakup.hra_received
                + data.salary_breakup.lta_received
                + data.salary_breakup.other_allowances
            )

        exempt_allowances = Decimal("0")
        if regime == Regime.OLD:
            # HRA exemption
            hra_ex, hra_trace = hra_exemption(data.salary_breakup, regime)
            exempt_allowances += hra_ex
            trace.append(hra_trace)
            # Other Section 10 exempt allowances from Form 16
            for f16 in data.form16s:
                for k, v in f16.exempt_allowances_10.items():
                    if k.lower() != "hra":
                        exempt_allowances += v
        else:
            trace.append("New regime: Section 10 exemptions disallowed")

        # Standard deduction u/s 16(ia)
        salary_after_exemptions = max(Decimal("0"), gross_salary - exempt_allowances)
        standard_deduction = min(
            reg_params.standard_deduction, salary_after_exemptions
        )

        # Professional tax u/s 16(iii) (capped at ₹2,500)
        professional_tax = Decimal("0")
        if regime == Regime.OLD:
            pt_claimed = Decimal("0")
            for f16 in data.form16s:
                pt_claimed += f16.professional_tax
            professional_tax = min(pt_claimed, Decimal("2500"))

        income_from_salary = max(
            Decimal("0"),
            salary_after_exemptions - standard_deduction - professional_tax,
        )
        trace.append(
            f"Salary: gross {gross_salary} - exempt {exempt_allowances} - std ded {standard_deduction} - prof tax {professional_tax} = {income_from_salary}"
        )

        # -------------------------------------------------------------
        # 2. HOUSE PROPERTY
        # -------------------------------------------------------------
        hp_income_total = Decimal("0")
        sop_interest_total = Decimal("0")
        let_out_net_total = Decimal("0")

        for hp in data.house_properties:
            if hp.is_self_occupied:
                sop_interest_total += hp.interest_on_loan_24b * hp.co_owner_share
            elif hp.is_let_out:
                gav = hp.annual_rent_received
                nav = max(Decimal("0"), gav - hp.municipal_taxes_paid)
                statutory_deduction = nav * Decimal("0.30")  # Section 24(a)
                net_hp = (nav - statutory_deduction - hp.interest_on_loan_24b) * hp.co_owner_share
                let_out_net_total += net_hp

        # Self-occupied property
        if regime == Regime.OLD:
            # 24(b) capped at ₹2,00,000 across all SOP properties combined
            allowed_sop_loss = min(sop_interest_total, Decimal("200000"))
            hp_income_total -= allowed_sop_loss
            if sop_interest_total > Decimal("0"):
                trace.append(f"House Property (SOP): interest {sop_interest_total} capped at {allowed_sop_loss}")
        else:
            trace.append("New regime: SOP Section 24(b) interest is disallowed")

        # Add let-out property income/loss
        hp_income_total += let_out_net_total

        # Set-off and carry-forward of net house property loss
        hp_loss_set_off = Decimal("0")
        hp_loss_carried_forward = Decimal("0")
        if hp_income_total < Decimal("0"):
            loss = abs(hp_income_total)
            if regime == Regime.OLD:
                # Inter-head set-off capped at ₹2,00,000 u/s 71(3A)
                hp_loss_set_off = min(loss, Decimal("200000"))
                hp_loss_carried_forward = loss - hp_loss_set_off
                trace.append(
                    f"HP Loss {loss}: set off {hp_loss_set_off} against other heads, {hp_loss_carried_forward} carried forward"
                )
            else:
                # New regime: no inter-head loss set off allowed
                hp_loss_set_off = Decimal("0")
                hp_loss_carried_forward = loss
                trace.append(f"New regime: HP Loss {loss} cannot be set off; {hp_loss_carried_forward} carried forward")
            hp_net_for_gti = -hp_loss_set_off
        else:
            hp_net_for_gti = hp_income_total

        # -------------------------------------------------------------
        # 3. PROFITS AND GAINS OF BUSINESS OR PROFESSION (Presumptive)
        # -------------------------------------------------------------
        business_income = Decimal("0")
        if data.presumptive:
            p = data.presumptive
            if p.section == "44AD":
                # Cash receipts check
                cash_limit = Decimal("30000000") if p.cash_receipts <= (p.turnover * Decimal("0.05")) else Decimal("20000000")
                if p.turnover > cash_limit:
                    raise ValueError(f"Turnover {p.turnover} exceeds Section 44AD limit {cash_limit}")
                deemed_profit = (p.digital_receipts * Decimal("0.06")) + (p.cash_receipts * Decimal("0.08"))
                business_income = max(p.declared_profit, deemed_profit)
                trace.append(f"Presumptive 44AD: deemed {deemed_profit}, declared {p.declared_profit} -> {business_income}")
            elif p.section == "44ADA":
                limit = Decimal("7500000") if p.cash_receipts <= (p.turnover * Decimal("0.05")) else Decimal("5000000")
                if p.turnover > limit:
                    raise ValueError(f"Gross receipts {p.turnover} exceed Section 44ADA limit {limit}")
                deemed_profit = p.turnover * Decimal("0.50")
                business_income = max(p.declared_profit, deemed_profit)
                trace.append(f"Presumptive 44ADA: deemed {deemed_profit}, declared {p.declared_profit} -> {business_income}")
            elif p.section == "44AE":
                # Vehicles calculation
                vehicles_profit = Decimal("0")
                if p.vehicles:
                    for v in p.vehicles:
                        weight = Decimal(str(v.get("weight_tons", 0)))
                        months = Decimal(str(v.get("months_operated", 12)))
                        if weight > Decimal("12"):
                            vehicles_profit += weight * Decimal("1000") * months
                        else:
                            vehicles_profit += Decimal("7500") * months
                business_income = max(p.declared_profit, vehicles_profit)
                trace.append(f"Presumptive 44AE: vehicles profit {vehicles_profit} -> {business_income}")

        # -------------------------------------------------------------
        # 4. CAPITAL GAINS
        # -------------------------------------------------------------
        stcg_111a = Decimal("0")
        stcg_slab = Decimal("0")
        ltcg_112a_gross = Decimal("0")
        ltcg_112 = Decimal("0")

        cg_params = params.capital_gains

        for item in data.capital_gains:
            # Classify holding period
            required_months = cg_params.holding_months.get(item.asset_type, 24)
            is_ltcg = bool(item.is_long_term)
            if item.asset_type == "debt_mf":
                # Section 50AA: Always short-term
                is_ltcg = False
            elif item.acquisition_date and item.transfer_date:
                holding_days = (item.transfer_date - item.acquisition_date).days
                # Approximate 12 months as 365 days, 24 months as 730 days
                threshold_days = 365 if required_months == 12 else 730
                is_ltcg = holding_days > threshold_days

            gain = (
                item.sale_consideration
                - item.transfer_expenses
                - item.cost_of_acquisition
                - item.cost_of_improvement
            )

            if item.asset_type in ("listed_equity", "equity_mf") and item.stt_paid:
                if is_ltcg:
                    ltcg_112a_gross += gain
                else:
                    stcg_111a += gain
            elif item.asset_type == "debt_mf":
                stcg_slab += gain
            else:
                # Immovable property, unlisted shares, gold
                if is_ltcg:
                    # Check pre-23 July 2024 indexation option
                    if (
                        item.is_pre_23jul2024
                        and item.asset_type == "immovable_property"
                        and data.residential_status in (
                            ResidentialStatus.RESIDENT_ORDINARY,
                            ResidentialStatus.RESIDENT_NOT_ORDINARY,
                        )
                    ):
                        # Compute both 12.5% unindexed vs 20% indexed
                        tax_unindexed = max(Decimal("0"), gain) * Decimal("0.125")
                        acq_year = item.acquisition_date.year if item.acquisition_date else 2015
                        acq_cii = Decimal(str(cg_params.cii.get(acq_year, 100)))
                        cur_cii = Decimal(str(cg_params.cii.get(2025, 376)))
                        indexed_cost = item.cost_of_acquisition * (cur_cii / acq_cii)
                        indexed_gain = max(
                            Decimal("0"),
                            item.sale_consideration
                            - item.transfer_expenses
                            - indexed_cost
                            - item.cost_of_improvement,
                        )
                        tax_indexed = indexed_gain * Decimal("0.20")

                        if tax_indexed < tax_unindexed:
                            # We record the effective gain equivalent or note in trace
                            trace.append(
                                f"Property LTCG indexation option: 20% indexed tax ({tax_indexed}) < 12.5% unindexed ({tax_unindexed}); indexed option chosen"
                            )
                            # To fit in ltcg_112 bucket at 12.5%, set effective gain so 12.5% matches tax_indexed:
                            ltcg_112 += (tax_indexed / Decimal("0.125"))
                        else:
                            trace.append(
                                f"Property LTCG 12.5% unindexed tax ({tax_unindexed}) <= 20% indexed ({tax_indexed}); 12.5% chosen"
                            )
                            ltcg_112 += gain
                    else:
                        ltcg_112 += gain
                else:
                    stcg_slab += gain

        # 112A exemption: first ₹1,25,000 exempt across all items
        ltcg_112a_exempt = min(max(Decimal("0"), ltcg_112a_gross), cg_params.ltcg_112a_exemption)
        ltcg_112a_taxable = max(Decimal("0"), ltcg_112a_gross - ltcg_112a_exempt)

        capital_gains_total = stcg_111a + stcg_slab + ltcg_112a_taxable + ltcg_112
        trace.append(
            f"Capital Gains: 111A ({stcg_111a}) + slab ({stcg_slab}) + 112A taxable ({ltcg_112a_taxable}, exempt {ltcg_112a_exempt}) + 112 ({ltcg_112}) = {capital_gains_total}"
        )

        # -------------------------------------------------------------
        # 5. INCOME FROM OTHER SOURCES
        # -------------------------------------------------------------
        # Family pension standard deduction u/s 57(iia)
        family_pension_ded = Decimal("0")
        if data.family_pension > Decimal("0"):
            if regime == Regime.NEW:
                family_pension_ded = min(data.family_pension, reg_params.family_pension_deduction)
            else:
                one_third = (data.family_pension / Decimal("3")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                family_pension_ded = min(one_third, reg_params.family_pension_deduction)

        other_sources_income = (
            data.savings_interest
            + data.fd_interest
            + data.dividend_income
            + max(Decimal("0"), data.family_pension - family_pension_ded)
            + data.other_income
            + data.winnings_115bb
        )
        trace.append(f"Other Sources: total {other_sources_income}")

        # -------------------------------------------------------------
        # 6. GROSS TOTAL INCOME (GTI)
        # -------------------------------------------------------------
        gross_total_income = (
            income_from_salary
            + hp_net_for_gti
            + business_income
            + capital_gains_total
            + other_sources_income
        )
        trace.append(f"Gross Total Income (GTI): {gross_total_income}")

        # -------------------------------------------------------------
        # 7. CHAPTER VI-A DEDUCTIONS
        # -------------------------------------------------------------
        special_rate_income = stcg_111a + ltcg_112a_taxable + ltcg_112 + data.winnings_115bb
        applied_via, via_total, disallowed_via, via_traces = apply_chapter_via(
            data.deduction_claims,
            gross_total_income,
            special_rate_income,
            data,
            regime,
            params,
        )
        trace.extend(via_traces)

        # -------------------------------------------------------------
        # 8. TOTAL INCOME (rounded to nearest ₹10 u/s 288A)
        # -------------------------------------------------------------
        total_income_unrounded = max(Decimal("0"), gross_total_income - via_total)
        total_income = round_to_10(total_income_unrounded)
        trace.append(f"Total Income: {gross_total_income} - {via_total} = {total_income} (rounded to nearest ₹10)")

        return HeadwiseIncome(
            regime=regime,
            gross_salary=gross_salary,
            exempt_allowances=exempt_allowances,
            standard_deduction=standard_deduction,
            professional_tax=professional_tax,
            income_from_salary=income_from_salary,
            house_property_income=hp_income_total,
            hp_loss_set_off=hp_loss_set_off,
            hp_loss_carried_forward=hp_loss_carried_forward,
            business_income=business_income,
            stcg_111a=stcg_111a,
            stcg_slab=stcg_slab,
            ltcg_112a_gross=ltcg_112a_gross,
            ltcg_112a_exempt=ltcg_112a_exempt,
            ltcg_112a_taxable=ltcg_112a_taxable,
            ltcg_112=ltcg_112,
            capital_gains_total=capital_gains_total,
            other_sources_income=other_sources_income,
            gross_total_income=gross_total_income,
            chapter_via=applied_via,
            chapter_via_total=via_total,
            total_income=total_income,
            trace=trace,
        )
