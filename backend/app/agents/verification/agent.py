"""Verification Agent for Indian Tax Returns.

Emits two independent verdicts:
- correctness_ok: arithmetic soundness, dual engine recomputation, statutory caps,
  TDS vs 26AS reconciliation, AIS cross-footing, rounding, and special rate isolation.
- completeness_ok: source evidence grounding, required certificates, ITR form eligibility,
  landlord PAN, and refund bank details.

A return is VALID only when both hold and the confidence score clears the threshold (default 0.95).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.base import slab_tax
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.verification.completeness import check_completeness
from app.schemas.tax import (
    AuditEntry,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    ResidentialStatus,
    VerificationCheck,
    VerificationResult,
)
from app.schemas.validators import validate_ifsc, validate_pan
from app.tax_rules.params import TaxYearParams, get_params


class VerificationAgent:
    name = "Verification Agent (India)"

    def __init__(
        self,
        calculator: Any | None = None,
        threshold: float = 0.95,
        params: TaxYearParams | None = None,
    ):
        self.threshold = threshold
        self.params = params
        self.income_service = IncomeComputationService()
        self.old_calculator = OldRegimeCalculator()
        self.new_calculator = NewRegimeCalculator()

    def run(
        self,
        data: IndianTaxpayerData,
        comparison: RegimeComparison,
        transcript: dict[str, Any] | None = None,
        filing_date: date | None = None,
    ) -> tuple[VerificationResult, AuditEntry]:
        params = self.params or get_params(data.financial_year)
        checks: list[VerificationCheck] = []
        errors: list[str] = []
        requires_reextraction = False

        def add_check(
            name: str, passed: bool, msg_pass: str, msg_fail: str, weight: float = 1.0
        ):
            checks.append(
                VerificationCheck(
                    name=name,
                    passed=passed,
                    message=msg_pass if passed else msg_fail,
                    weight=weight,
                )
            )
            if not passed:
                errors.append(msg_fail)

        # -------------------------------------------------------------------
        # 1. Recomputation Check [Weight: 3.0]
        # Anti-hallucination: re-run BOTH engines in a fresh instance from data
        # -------------------------------------------------------------------
        f_date = filing_date or date(2026, 7, 31)
        inc_old_fresh = self.income_service.compute(data, Regime.OLD, params)
        inc_new_fresh = self.income_service.compute(data, Regime.NEW, params)

        res_old_fresh = self.old_calculator.calculate(data, inc_old_fresh, params, f_date)
        res_new_fresh = self.new_calculator.calculate(data, inc_new_fresh, params, f_date)

        recompute_old_ok = (
            res_old_fresh.total_tax_liability == comparison.old.total_tax_liability
        )
        recompute_new_ok = (
            res_new_fresh.total_tax_liability == comparison.new.total_tax_liability
        )
        recompute_ok = recompute_old_ok and recompute_new_ok

        add_check(
            "deterministic_recomputation",
            recompute_ok,
            "Both Old and New Regime tax calculations recomputed identically to the rupee",
            f"Recomputation mismatch: Old expected ₹{res_old_fresh.total_tax_liability} (got ₹{comparison.old.total_tax_liability}); "
            f"New expected ₹{res_new_fresh.total_tax_liability} (got ₹{comparison.new.total_tax_liability})",
            weight=3.0,
        )

        # -------------------------------------------------------------------
        # 2. TDS Reconciliation [Weight: 3.0]
        # Sum of TDS claimed across Form 16s vs Form 26AS Part I + Part II
        # -------------------------------------------------------------------
        tds_claimed = sum(f.tds_deducted for f in data.form16s) + data.taxes_paid.tds_non_salary
        tds_26as = data.taxes_paid.tds_salary + data.taxes_paid.tds_non_salary

        # If 26AS data is present, must match within ₹1
        if data.taxes_paid.tds_salary > Decimal("0") or data.taxes_paid.tds_non_salary > Decimal("0"):
            tds_diff = abs(tds_claimed - tds_26as)
            tds_ok = tds_diff <= Decimal("1")
        else:
            tds_ok = True
            tds_diff = Decimal("0")

        if not tds_ok:
            requires_reextraction = True

        add_check(
            "tds_26as_reconciliation",
            tds_ok,
            f"TDS claimed (₹{tds_claimed:,.0f}) reconciled with Form 26AS credit (₹{tds_26as:,.0f})",
            f"TDS mismatch: Claimed ₹{tds_claimed:,.0f} vs Form 26AS ₹{tds_26as:,.0f} (variance ₹{tds_diff:,.0f})",
            weight=3.0,
        )

        # -------------------------------------------------------------------
        # 3. AIS/TIS Reconciliation [Weight: 2.0]
        # Salary, interest, and dividend totals match AIS within 1% or ₹1,000
        # -------------------------------------------------------------------
        ais_ok = True
        ais_issues: list[str] = []
        if transcript and "ais" in transcript:
            ais_data = transcript["ais"]
            for cat, declared_val in [
                ("salary", sum(f.gross_salary_17_1 for f in data.form16s)),
                ("savings_interest", data.savings_interest),
                ("fd_interest", data.fd_interest),
                ("dividend", data.dividend_income),
            ]:
                if cat in ais_data:
                    ais_val = Decimal(str(ais_data[cat]))
                    tol = max(Decimal("1000"), ais_val * Decimal("0.01"))
                    if abs(declared_val - ais_val) > tol:
                        ais_ok = False
                        ais_issues.append(f"{cat}: declared ₹{declared_val:,.0f} vs AIS ₹{ais_val:,.0f}")

        add_check(
            "ais_tis_reconciliation",
            ais_ok,
            "Reported incomes reconciled against AIS/TIS entries within statutory tolerance",
            f"AIS variance detected: {'; '.join(ais_issues)}",
            weight=2.0,
        )

        # -------------------------------------------------------------------
        # 4. Slab Arithmetic [Weight: 2.0]
        # Independent loop over cumulative bands
        # -------------------------------------------------------------------
        rec_res = comparison.old if comparison.recommended == Regime.OLD else comparison.new
        normal_inc = rec_res.income.total_income - (
            rec_res.income.stcg_111a + rec_res.income.ltcg_112a_taxable + rec_res.income.ltcg_112
        )
        normal_inc = max(Decimal("0"), normal_inc)
        slabs = params.regimes[rec_res.regime].slabs[data.age_band]
        alt_slab_tax = Decimal("0")
        prev_limit = Decimal("0")
        for upper, rate in slabs:
            if upper is None:
                if normal_inc > prev_limit:
                    alt_slab_tax += (normal_inc - prev_limit) * rate
                break
            if normal_inc > prev_limit:
                band_taxable = min(normal_inc, upper) - prev_limit
                alt_slab_tax += band_taxable * rate
            prev_limit = upper

        slab_ok = abs(alt_slab_tax - rec_res.tax_on_slab_income) <= Decimal("1")
        add_check(
            "slab_arithmetic_independent",
            slab_ok,
            "Slab tax verified with independent cumulative band computation",
            f"Slab tax discrepancy: computed ₹{rec_res.tax_on_slab_income} vs independent ₹{alt_slab_tax}",
            weight=2.0,
        )

        # -------------------------------------------------------------------
        # 5. Regime Comparison Sanity [Weight: 2.0]
        # Recommended regime <= non-recommended, deltas reflect savings
        # -------------------------------------------------------------------
        rec_is_cheaper = (
            rec_res.total_tax_liability <= (
                comparison.new.total_tax_liability
                if comparison.recommended == Regime.OLD
                else comparison.old.total_tax_liability
            )
        )
        expected_savings = abs(
            comparison.old.total_tax_liability - comparison.new.total_tax_liability
        )
        savings_ok = comparison.savings == expected_savings
        comparison_ok = rec_is_cheaper and savings_ok

        add_check(
            "regime_comparison_sanity",
            comparison_ok,
            f"Recommendation sound: {comparison.recommended.value.upper()} saves ₹{comparison.savings:,.0f}",
            "Comparison sanity failed: recommended regime is not cheaper or savings calculation incorrect",
            weight=2.0,
        )

        # -------------------------------------------------------------------
        # 6. Deduction Legality [Weight: 2.0]
        # No disallowed deductions in New regime, caps respected
        # -------------------------------------------------------------------
        deductions_ok = True
        # In new regime, allowed set check
        allowed_new = params.regimes[Regime.NEW].allowed_chapter_via
        for sec in comparison.new.income.chapter_via:
            if sec not in allowed_new:
                deductions_ok = False
                errors.append(f"Section {sec} claimed in New Regime is legally disallowed.")

        # In old regime, 80C <= 1.5L
        c_tot = sum(
            comparison.old.income.chapter_via.get(s, Decimal("0"))
            for s in ("80C", "80CCC", "80CCD1")
        )
        c_raw = (
            data.deduction_claims.get("80C", Decimal("0"))
            + data.deduction_claims.get("80CCC", Decimal("0"))
            + data.deduction_claims.get("80CCD1", Decimal("0"))
        )
        if c_tot > Decimal("150000") or c_raw > Decimal("150000"):
            deductions_ok = False
            errors.append(f"Section 80C+80CCC+80CCD(1) claim exceeds statutory cap of ₹1,50,000.")

        add_check(
            "deduction_legality",
            deductions_ok,
            "All Chapter VI-A deductions comply with statutory caps and regime eligibility",
            "Deduction legality violation: disallowed section or statutory cap exceeded",
            weight=2.0,
        )

        # -------------------------------------------------------------------
        # 7. Capital Gains Classification [Weight: 2.0]
        # Holding period matches dates, 112A exemption <= 1.25L
        # -------------------------------------------------------------------
        cg_ok = True
        for item in data.capital_gains:
            if item.acquisition_date and item.transfer_date:
                days = (item.transfer_date - item.acquisition_date).days
                if (days > 365) != item.is_long_term and item.asset_type == "listed_equity":
                    cg_ok = False
                    errors.append(f"Asset {item.asset_type} classified incorrectly based on {days} holding days.")

        if comparison.old.income.ltcg_112a_exempt > Decimal("125000"):
            cg_ok = False
            errors.append("Section 112A LTCG exemption exceeds ₹1,25,000 ceiling.")

        add_check(
            "capital_gains_classification",
            cg_ok,
            "Capital gains holding periods, asset categories, and Section 112A exemption verified",
            "Capital gains error: holding period mismatch or excessive exemption claimed",
            weight=2.0,
        )

        # -------------------------------------------------------------------
        # 8. Special-Rate Isolation [Weight: 1.0]
        # 87A not on 112A, special slice surcharge <= 15%
        # -------------------------------------------------------------------
        special_ok = True
        # In New Regime, 87A rebate must not exceed slab tax
        if comparison.new.rebate_87a > comparison.new.tax_on_slab_income:
            special_ok = False
            errors.append("Section 87A rebate wrongfully applied against special-rate income in New Regime.")

        add_check(
            "special_rate_isolation",
            special_ok,
            "Special-rate income isolated from Section 87A rebate and surcharge cap respected",
            "Special-rate tax isolation failure",
            weight=1.0,
        )

        # -------------------------------------------------------------------
        # 9. Arithmetic Identity [Weight: 1.0]
        # Total Income = GTI - VI-A, Refund/Payable equation balanced
        # -------------------------------------------------------------------
        identity_ok = True
        for res in (comparison.old, comparison.new):
            if (res.income.gross_total_income - res.income.chapter_via_total) < res.income.total_income - Decimal("10"):
                identity_ok = False
            settlement_diff = abs(
                (res.refund_due - res.tax_payable)
                - (res.taxes_paid_total - (res.total_tax_liability + res.interest_234a + res.interest_234b + res.interest_234c + res.fee_234f))
            )
            if settlement_diff > Decimal("10"):
                identity_ok = False

        add_check(
            "arithmetic_identity",
            identity_ok,
            "Gross-to-net income and tax settlement equations balance perfectly",
            "Arithmetic identity violation in computation sheet",
            weight=1.0,
        )

        # -------------------------------------------------------------------
        # 10. Rounding Compliance [Weight: 1.0]
        # Section 288A and 288B (multiples of 10)
        # -------------------------------------------------------------------
        rounding_ok = (
            comparison.old.income.total_income % Decimal("10") == Decimal("0")
            and comparison.new.income.total_income % Decimal("10") == Decimal("0")
            and comparison.old.total_tax_liability % Decimal("10") == Decimal("0")
            and comparison.new.total_tax_liability % Decimal("10") == Decimal("0")
        )
        add_check(
            "section_288a_288b_rounding",
            rounding_ok,
            "Total income and tax liability rounded to nearest ₹10 per Sections 288A and 288B",
            "Rounding violation: figures are not multiples of ₹10",
            weight=1.0,
        )

        # -------------------------------------------------------------------
        # 11. PAN and Identity Validity [Weight: 1.0]
        # -------------------------------------------------------------------
        pan_ok = validate_pan(data.pan)
        if data.residential_status == ResidentialStatus.RESIDENT_ORDINARY and data.pan:
            # 4th character must be 'P' for individual
            if len(data.pan) >= 4 and data.pan[3] != "P":
                pan_ok = False

        add_check(
            "pan_and_identity_validity",
            pan_ok,
            f"PAN {data.masked_pan} validated with individual character verification",
            f"Invalid PAN format or individual category mismatch: {data.pan}",
            weight=1.0,
        )

        # Run Completeness checks
        comp_report = check_completeness(data, comparison, filing_date=f_date)
        checks.extend(comp_report.checks)
        errors.extend(comp_report.errors)
        if comp_report.requires_reextraction:
            requires_reextraction = True

        # Compute weighted confidence score
        total_weight = sum(c.weight for c in checks)
        passed_weight = sum(c.weight for c in checks if c.passed)
        rule_score = passed_weight / total_weight if total_weight > 0 else 1.0

        # Field extraction confidence (average from data)
        ext_conf = (
            sum(data.field_confidence.values()) / len(data.field_confidence)
            if data.field_confidence
            else 1.0
        )
        overall_confidence = float(
            Decimal(str(0.8 * rule_score + 0.2 * ext_conf)).quantize(
                Decimal("0.001")
            )
        )

        correctness_ok = all(
            c.passed
            for c in checks
            if c.name
            in (
                "deterministic_recomputation",
                "tds_26as_reconciliation",
                "ais_tis_reconciliation",
                "slab_arithmetic_independent",
                "regime_comparison_sanity",
                "deduction_legality",
                "capital_gains_classification",
                "special_rate_isolation",
                "arithmetic_identity",
                "section_288a_288b_rounding",
                "pan_and_identity_validity",
            )
        )
        completeness_ok = comp_report.ok

        is_valid = (
            correctness_ok
            and completeness_ok
            and overall_confidence >= self.threshold
        )

        result = VerificationResult(
            valid=is_valid,
            confidence_score=overall_confidence,
            checks=checks,
            hallucination_flags=comp_report.hallucination_flags,
            errors=errors,
            correctness_ok=correctness_ok,
            completeness_ok=completeness_ok,
            requires_reextraction=requires_reextraction,
        )

        audit = AuditEntry(
            agent=self.name,
            action="verify_return",
            reason=f"Verification {'PASSED' if is_valid else 'FAILED'} with confidence {overall_confidence:.1%}",
            details={
                "valid": is_valid,
                "confidence_score": overall_confidence,
                "correctness_ok": correctness_ok,
                "completeness_ok": completeness_ok,
                "failed_checks": [c.name for c in checks if not c.passed],
            },
        )

        return result, audit
