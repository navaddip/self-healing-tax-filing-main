"""Regime Comparison Agent.

Compares Old and New tax regimes deterministically, identifies the cheaper regime,
computes line-by-line deltas, deductions forfeited under the new regime,
the breakeven deduction amount, unused headroom, Form 10-IEA requirements,
plain-English reasons, and a sensitivity table for what-if scenarios.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.agents.regimes.base import (
    cess,
    rebate_87a,
    round_to_ten,
    slab_tax,
    surcharge,
)
from app.schemas.tax import (
    AuditEntry,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    RegimeTaxResult,
    ResidentialStatus,
)
from app.tax_rules.params import TaxYearParams, get_params


class RegimeComparisonAgent:
    """Compares Old vs New Regime results deterministically."""

    def __init__(self, params: TaxYearParams | None = None):
        self.params = params

    def run(
        self,
        data: IndianTaxpayerData,
        old: RegimeTaxResult,
        new: RegimeTaxResult,
    ) -> tuple[RegimeComparison, AuditEntry]:
        params = self.params or get_params(data.financial_year)

        # 1. Recommendation (tie-break to NEW as statutory default)
        if old.total_tax_liability < new.total_tax_liability:
            recommended = Regime.OLD
        else:
            recommended = Regime.NEW

        # 2. Savings and savings percentage
        savings = abs(old.total_tax_liability - new.total_tax_liability)
        max_tax = max(old.total_tax_liability, new.total_tax_liability)
        if max_tax > Decimal("0"):
            savings_pct = (savings / max_tax * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            savings_pct = Decimal("0")

        # 3. Line-by-line deltas
        deltas = self._compute_deltas(old, new)

        # 4. Deductions forfeited if NEW
        deductions_forfeited = self._compute_forfeited_deductions(data, old, new)

        # 5. Breakeven deduction amount
        breakeven = self._compute_breakeven(data, old, new, params)

        # 6. Unused 80C headroom
        c_claimed = (
            data.deduction_claims.get("80C", Decimal("0"))
            + data.deduction_claims.get("80CCC", Decimal("0"))
            + data.deduction_claims.get("80CCD1", Decimal("0"))
        )
        c_limit = params.chapter_via.limits.get("80C", Decimal("150000"))
        diff_80c = max(Decimal("0"), c_limit - c_claimed)

        # Only meaningful if OLD is recommended or within ₹25,000 of winning
        tax_diff_to_old = old.total_tax_liability - new.total_tax_liability
        if recommended == Regime.OLD or tax_diff_to_old <= Decimal("25000"):
            unused_80c = diff_80c
        else:
            unused_80c = Decimal("0")

        # 7. Switch allowed annually & Form 10-IEA
        has_business_income = (
            data.presumptive is not None
            or old.income.business_income > Decimal("0")
        )
        switch_allowed = not has_business_income
        form_10iea = (recommended == Regime.OLD) and has_business_income

        # Current total old deductions and exemptions
        current_old_claims = self._compute_total_old_claims(data, old)

        # 8. Reasons
        reasons = self._generate_reasons(
            data=data,
            old=old,
            new=new,
            recommended=recommended,
            savings=savings,
            breakeven=breakeven,
            current_old_claims=current_old_claims,
            deductions_forfeited=deductions_forfeited,
            form_10iea=form_10iea,
        )

        comparison = RegimeComparison(
            old=old,
            new=new,
            recommended=recommended,
            savings=savings,
            savings_pct=savings_pct,
            deltas=deltas,
            deductions_forfeited_if_new=deductions_forfeited,
            breakeven_deduction_amount=breakeven,
            unused_80c_headroom=unused_80c,
            switch_allowed_annually=switch_allowed,
            form_10iea_required=form_10iea,
            reasons=reasons,
        )

        audit = AuditEntry(
            agent="RegimeComparisonAgent",
            action="compare_regimes",
            reason=f"Recommended {recommended.value} regime with savings of ₹{savings:,}",
            details={
                "recommended": recommended.value,
                "savings": str(savings),
                "savings_pct": str(savings_pct),
                "breakeven_deduction": str(breakeven),
                "form_10iea_required": form_10iea,
            },
        )

        return comparison, audit

    def _compute_total_old_claims(
        self, data: IndianTaxpayerData, old: RegimeTaxResult
    ) -> Decimal:
        """Sum of all deductions and exemptions claimed under the Old Regime."""
        total = Decimal("0")
        # Standard deduction
        total += old.income.standard_deduction
        # Exempt allowances (e.g. HRA, LTA)
        total += old.income.exempt_allowances
        # Professional tax
        total += old.income.professional_tax
        # Self-occupied HP interest
        if any(hp.is_self_occupied for hp in data.house_properties):
            total += old.income.hp_loss_set_off
        # Chapter VI-A
        total += old.income.chapter_via_total
        return total

    def _compute_deltas(
        self, old: RegimeTaxResult, new: RegimeTaxResult
    ) -> list[dict[str, Any]]:
        deltas: list[dict[str, Any]] = []

        def add_row(
            line: str,
            old_val: Decimal,
            new_val: Decimal,
            note: str = "",
        ):
            deltas.append(
                {
                    "line": line,
                    "old_value": old_val,
                    "new_value": new_val,
                    "delta": new_val - old_val,
                    "note": note,
                }
            )

        # 1. Salary head
        add_row(
            "Gross salary",
            old.income.gross_salary,
            new.income.gross_salary,
        )
        add_row(
            "Exempt allowances (HRA/LTA)",
            old.income.exempt_allowances,
            new.income.exempt_allowances,
            "Disallowed in New Regime except Sec 10(14)",
        )
        add_row(
            "Standard deduction",
            old.income.standard_deduction,
            new.income.standard_deduction,
            "₹50,000 (Old) vs ₹75,000 (New)",
        )
        add_row(
            "Professional tax",
            old.income.professional_tax,
            new.income.professional_tax,
            "Old Regime only",
        )
        add_row(
            "Income from salary",
            old.income.income_from_salary,
            new.income.income_from_salary,
        )

        # 2. House Property
        add_row(
            "House property income/loss",
            old.income.house_property_income,
            new.income.house_property_income,
            "SOP interest capped at ₹2L (Old), ₹0 (New)",
        )

        # 3. Business Income
        add_row(
            "Business/profession income",
            old.income.business_income,
            new.income.business_income,
        )

        # 4. Capital Gains
        add_row("STCG u/s 111A (20%)", old.income.stcg_111a, new.income.stcg_111a)
        add_row("STCG at slab rates", old.income.stcg_slab, new.income.stcg_slab)
        add_row(
            "LTCG u/s 112A (12.5% > ₹1.25L)",
            old.income.ltcg_112a_taxable,
            new.income.ltcg_112a_taxable,
        )
        add_row("LTCG u/s 112", old.income.ltcg_112, new.income.ltcg_112)

        # 5. Other Sources
        add_row(
            "Income from other sources",
            old.income.other_sources_income,
            new.income.other_sources_income,
        )

        # 6. Gross Total Income
        add_row(
            "Gross total income",
            old.income.gross_total_income,
            new.income.gross_total_income,
        )

        # 7. Chapter VI-A lines
        all_sections = sorted(
            set(old.income.chapter_via.keys())
            | set(new.income.chapter_via.keys())
        )
        for sec in all_sections:
            old_sec = old.income.chapter_via.get(sec, Decimal("0"))
            new_sec = new.income.chapter_via.get(sec, Decimal("0"))
            add_row(f"Section {sec}", old_sec, new_sec)

        add_row(
            "Total Chapter VI-A deductions",
            old.income.chapter_via_total,
            new.income.chapter_via_total,
        )

        # 8. Total Taxable Income
        add_row(
            "Total taxable income",
            old.income.total_income,
            new.income.total_income,
            "Rounded to ₹10 u/s 288A",
        )

        # 9. Tax Computation
        add_row(
            "Tax at slab rates",
            old.tax_on_slab_income,
            new.tax_on_slab_income,
        )
        add_row(
            "Tax at special rates",
            old.tax_on_special_income,
            new.tax_on_special_income,
        )
        add_row("Rebate u/s 87A", old.rebate_87a, new.rebate_87a)
        add_row(
            "Marginal relief u/s 87A",
            old.marginal_relief_87a,
            new.marginal_relief_87a,
        )
        add_row(
            "Surcharge",
            old.surcharge,
            new.surcharge,
        )
        add_row(
            "Health & education cess (4%)",
            old.cess,
            new.cess,
        )
        add_row(
            "Total tax liability",
            old.total_tax_liability,
            new.total_tax_liability,
            "Rounded to ₹10 u/s 288B",
        )
        add_row(
            "Taxes paid (TDS/Advance)",
            old.taxes_paid_total,
            new.taxes_paid_total,
        )
        add_row(
            "Refund due",
            old.refund_due,
            new.refund_due,
        )
        add_row(
            "Tax payable",
            old.tax_payable,
            new.tax_payable,
        )

        return deltas

    def _compute_forfeited_deductions(
        self,
        data: IndianTaxpayerData,
        old: RegimeTaxResult,
        new: RegimeTaxResult,
    ) -> dict[str, Decimal]:
        forfeited: dict[str, Decimal] = {}

        # Exempt allowances (e.g. HRA, LTA)
        if old.income.exempt_allowances > Decimal("0"):
            forfeited["Exempt Allowances (HRA/LTA)"] = (
                old.income.exempt_allowances
            )

        # Professional tax
        if old.income.professional_tax > Decimal("0"):
            forfeited["Professional Tax u/s 16(iii)"] = (
                old.income.professional_tax
            )

        # Self-occupied property loan interest
        if any(hp.is_self_occupied for hp in data.house_properties):
            if old.income.hp_loss_set_off > Decimal("0"):
                forfeited["Home Loan Interest SOP u/s 24(b)"] = (
                    old.income.hp_loss_set_off
                )

        # Chapter VI-A sections disallowed in New
        for sec, amt in old.income.chapter_via.items():
            new_amt = new.income.chapter_via.get(sec, Decimal("0"))
            if amt > new_amt:
                forfeited[f"Section {sec}"] = amt - new_amt

        return forfeited

    def _compute_raw_gross_income(self, data: IndianTaxpayerData) -> Decimal:
        """Compute taxpayer's total raw income before any deductions or exemptions."""
        # Gross salary before deductions and exemptions
        salary = sum(
            f.gross_salary_17_1 + f.perquisites_17_2 + f.profits_in_lieu_17_3
            for f in data.form16s
        )
        # Let-out house property rent
        hp_let_out = Decimal("0")
        for hp in data.house_properties:
            if hp.is_let_out:
                nav = max(
                    Decimal("0"), hp.annual_rent_received - hp.municipal_taxes_paid
                )
                standard_30 = (nav * Decimal("0.30")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                hp_let_out += (nav - standard_30 - hp.interest_on_loan_24b) * hp.co_owner_share

        # Presumptive
        business = Decimal("0")
        if data.presumptive:
            business += data.presumptive.declared_profit

        # Capital gains
        cg = sum(
            max(
                Decimal("0"),
                item.sale_consideration
                - item.transfer_expenses
                - item.cost_of_acquisition
                - item.cost_of_improvement,
            )
            for item in data.capital_gains
        )

        # Other sources
        other = (
            data.savings_interest
            + data.fd_interest
            + data.dividend_income
            + data.other_income
            + data.family_pension
            + data.winnings_115bb
        )

        return salary + hp_let_out + business + cg + other

    def _compute_breakeven(
        self,
        data: IndianTaxpayerData,
        old: RegimeTaxResult,
        new: RegimeTaxResult,
        params: TaxYearParams,
    ) -> Decimal:
        """Bisect to find the exact deduction amount D where Old tax equals New tax."""
        raw_gross = self._compute_raw_gross_income(data)
        target_tax = new.total_tax_liability
        is_resident = (
            data.residential_status != ResidentialStatus.NON_RESIDENT
        )
        age_band = data.age_band
        special_tax = old.tax_on_special_income

        def tax_at_deduction(d: Decimal) -> Decimal:
            taxable = max(Decimal("0"), raw_gross - d)
            normal_income = max(Decimal("0"), taxable - (old.income.stcg_111a + old.income.ltcg_112a_taxable + old.income.ltcg_112))
            st = slab_tax(normal_income, params.regimes[Regime.OLD].slabs[age_band])
            reb, _ = rebate_87a(taxable, st, special_tax, Regime.OLD, params, is_resident)
            tax_after_reb = (st + special_tax) - reb
            sur, _ = surcharge(taxable, tax_after_reb, special_tax, Regime.OLD, params)
            tax_plus_sur = tax_after_reb + sur
            c = cess(tax_plus_sur, params.cess_rate)
            # Use unrounded tax + cess for exact bisection crossover
            return tax_plus_sur + c

        # If even at 0 deductions, old tax is <= target tax, breakeven is 0
        if tax_at_deduction(Decimal("0")) <= target_tax:
            return Decimal("0")

        # If at max deductions (gross income), old tax > target tax (target tax is 0 and old tax > 0)
        # return raw_gross
        if tax_at_deduction(raw_gross) > target_tax:
            return raw_gross

        low = Decimal("0")
        high = raw_gross
        one = Decimal("1")

        # Integer bisection to the rupee
        while (high - low) > one:
            mid = ((low + high) / Decimal("2")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            val = tax_at_deduction(mid)
            if val <= target_tax:
                # Old tax is <= target, so deduction is sufficient; try smaller deduction
                high = mid
            else:
                # Old tax is still higher than target; need more deduction
                low = mid

        # Check between low and high
        if tax_at_deduction(low) <= target_tax:
            return low
        return high

    def _generate_reasons(
        self,
        data: IndianTaxpayerData,
        old: RegimeTaxResult,
        new: RegimeTaxResult,
        recommended: Regime,
        savings: Decimal,
        breakeven: Decimal,
        current_old_claims: Decimal,
        deductions_forfeited: dict[str, Decimal],
        form_10iea: bool,
    ) -> list[str]:
        reasons: list[str] = []

        if recommended == Regime.OLD:
            # 1. Breakeven comparison
            reasons.append(
                f"The old regime becomes cheaper for you once your total deductions and exemptions "
                f"exceed ₹{breakeven:,.0f}. You currently claim ₹{current_old_claims:,.0f}."
            )
            # 2. Key forfeited value
            hra_amt = deductions_forfeited.get("Exempt Allowances (HRA/LTA)", Decimal("0"))
            sop_amt = deductions_forfeited.get("Home Loan Interest SOP u/s 24(b)", Decimal("0"))
            if hra_amt > Decimal("0") or sop_amt > Decimal("0"):
                combined_amt = hra_amt + sop_amt
                raw_gross = self._compute_raw_gross_income(data)
                # Marginal tax rate applicable to forfeited income if added back
                if raw_gross > Decimal("1000000"):
                    marginal_rate = Decimal("0.312")
                elif raw_gross > Decimal("500000"):
                    marginal_rate = Decimal("0.208")
                else:
                    marginal_rate = Decimal("0.052")

                tax_val = (combined_amt * marginal_rate).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                reasons.append(
                    f"Your HRA exemption of ₹{hra_amt:,.0f} and Section 24(b) interest of ₹{sop_amt:,.0f} "
                    f"are worth ₹{tax_val:,.0f} in tax under the old regime and nothing under the new regime."
                )

            reasons.append(
                f"By choosing the Old Regime, you save ₹{savings:,.0f} in total tax liability."
            )

            if form_10iea:
                reasons.append(
                    "Form 10-IEA must be filed on or before the Section 139(1) due date to opt into the Old Regime for business/profession income."
                )
        else:
            # NEW is recommended
            if new.total_tax_liability == Decimal("0"):
                reasons.append(
                    "Even with zero deductions the new regime's ₹60,000 rebate wipes out your entire liability, "
                    "so no investment can make the old regime cheaper for you."
                )
            elif savings <= Decimal("10000"):
                reasons.append(
                    f"The two regimes are within ₹{savings:,.0f} of each other. Choose the new regime for the lighter "
                    f"compliance unless you expect your 80C investments to rise next year."
                )
            else:
                reasons.append(
                    f"Under the New Regime, wider tax slabs and the ₹75,000 standard deduction deliver ₹{savings:,.0f} in tax savings."
                )

            if breakeven > current_old_claims and breakeven > Decimal("0"):
                reasons.append(
                    f"The old regime would only become cheaper if your total deductions and exemptions "
                    f"exceeded ₹{breakeven:,.0f} (you currently claim ₹{current_old_claims:,.0f})."
                )

        return reasons

    def sensitivity(
        self,
        data: IndianTaxpayerData,
        params: TaxYearParams,
        deduction_deltas: list[Decimal] | None = None,
    ) -> list[dict[str, Any]]:
        """Re-run old-regime at GTI-constant for various deduction deltas."""
        if deduction_deltas is None:
            deduction_deltas = [
                Decimal("-50000"),
                Decimal("-25000"),
                Decimal("0"),
                Decimal("25000"),
                Decimal("50000"),
                Decimal("100000"),
                Decimal("150000"),
            ]

        # Calculate base old and new
        from app.agents.income.computation import IncomeComputationService
        from app.agents.regimes.new_regime import NewRegimeCalculator
        from app.agents.regimes.old_regime import OldRegimeCalculator

        income_svc = IncomeComputationService()
        old_calc = OldRegimeCalculator()
        new_calc = NewRegimeCalculator()

        inc_old = income_svc.compute(data, Regime.OLD, params)
        inc_new = income_svc.compute(data, Regime.NEW, params)

        from datetime import date
        dummy_date = date(2026, 7, 31)

        res_new = new_calc.calculate(data, inc_new, params, dummy_date)
        new_tax = res_new.total_tax_liability

        results: list[dict[str, Any]] = []
        raw_gross = self._compute_raw_gross_income(data)
        current_claims = self._compute_total_old_claims(data, old_calc.calculate(data, inc_old, params, dummy_date))

        is_resident = (
            data.residential_status != ResidentialStatus.NON_RESIDENT
        )
        age_band = data.age_band
        special_tax = inc_old.stcg_111a * Decimal("0.20") + inc_old.ltcg_112a_taxable * Decimal("0.125") + inc_old.ltcg_112 * Decimal("0.125")

        for delta in deduction_deltas:
            adjusted_claims = max(Decimal("0"), current_claims + delta)
            taxable = max(Decimal("0"), raw_gross - adjusted_claims)
            taxable_rounded = round_to_ten(taxable)
            normal_income = max(
                Decimal("0"),
                taxable_rounded
                - (inc_old.stcg_111a + inc_old.ltcg_112a_taxable + inc_old.ltcg_112),
            )

            st = slab_tax(normal_income, params.regimes[Regime.OLD].slabs[age_band])
            reb, mr_87a = rebate_87a(
                taxable_rounded, st, special_tax, Regime.OLD, params, is_resident
            )
            tax_after_reb = (st + special_tax) - reb - mr_87a
            sur, sur_mr = surcharge(
                taxable_rounded, tax_after_reb, special_tax, Regime.OLD, params
            )
            c = cess(tax_after_reb + sur, params.cess_rate)
            old_tax = round_to_ten(tax_after_reb + sur + c)

            winner = Regime.OLD if old_tax < new_tax else Regime.NEW
            results.append(
                {
                    "delta": delta,
                    "old_tax": old_tax,
                    "new_tax": new_tax,
                    "winner": winner.value,
                }
            )

        return results
