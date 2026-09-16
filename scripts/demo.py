"""End-to-End Demonstration Script for Indian Tax Filing System (AY 2026-27).

Runs a synthetic taxpayer through the 8-agent pipeline:
1. Document Reading & Evidence Extraction (Form 16)
2. Income Computation (5 Heads)
3. Dual-Regime Calculation (Old vs New Sec 115BAC)
4. Regime Comparison & Breakeven Analysis
5. Verification & Remediation Loop
6. CA-Grade 8-Page PDF Advisory Report Generation
7. CBDT-Compliant ITR JSON Generation & Validation
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.verification.agent import VerificationAgent
from app.agents.verification.completeness import select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.schema_loader import validate_itr_json
from app.schemas.tax import Regime
from app.services.pdf.comparison_report import ComparisonReportService
from app.synthetic import synthetic_mid_career
from app.tax_rules.params import get_params


def format_inr(val: Decimal | int | float) -> str:
    """Format an amount in Indian Numbering System with Rupee symbol."""
    d = Decimal(str(val))
    sign = "-" if d < 0 else ""
    d = abs(d)
    int_part = int(d)
    s = str(int_part)
    if len(s) > 3:
        last3 = s[-3:]
        other = s[:-3]
        groups = []
        while len(other) > 2:
            groups.insert(0, other[-2:])
            other = other[:-2]
        if other:
            groups.insert(0, other)
        formatted = ",".join(groups) + "," + last3
    else:
        formatted = s
    return f"{sign}₹{formatted}"


def main() -> None:
    print("=" * 80)
    print("  INDIA TAX FILING PIPELINE - AY 2026-27 (FY 2025-26) DEMONSTRATION")
    print("  Dual Regime Comparison & CA-Grade Advisory Engine")
    print("=" * 80)
    print()

    # 1. Initialize Parameter Pack & Engines
    params = get_params("2025-26")
    income_service = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comparison_agent = RegimeComparisonAgent(params)
    verifier = VerificationAgent(params)
    pdf_service = ComparisonReportService()
    filing_date = date(2026, 7, 31)

    # 2. Load Synthetic Persona (Mid-Career Salaried)
    data = synthetic_mid_career()
    print(f"Taxpayer: {data.name} | PAN: {data.pan} | Residential: {data.residential_status.value}")
    print(f"Gross Salary (Form 16): {format_inr(data.form16s[0].gross_salary_17_1)}")
    print(f"Rent Paid: {format_inr(data.salary_breakup.rent_paid_annual)} | Metro: {data.salary_breakup.is_metro}")
    print(f"Self-Occupied Home Loan Interest (Sec 24b): {format_inr(data.house_properties[0].interest_on_loan_24b)}")
    print(f"Deductions Claimed: 80C={format_inr(data.deduction_claims.get('80C', 0))}, "
          f"80D={format_inr(data.deduction_claims.get('80D', 0))}, "
          f"80CCD(1B)={format_inr(data.deduction_claims.get('80CCD1B', 0))}, "
          f"80CCD(2)={format_inr(data.deduction_claims.get('80CCD2', 0))}")
    print()

    # 3. Compute Headwise Income
    print("[Agent 1 & 2] Computing 5 Heads of Income under both regimes...")
    inc_old = income_service.compute(data, Regime.OLD, params)
    inc_new = income_service.compute(data, Regime.NEW, params)
    print(f"  Old Regime Total Income: {format_inr(inc_old.total_income)}")
    print(f"  New Regime Total Income: {format_inr(inc_new.total_income)}")
    print()

    # 4. Compute Tax Liabilities
    print("[Agent 3 & 4] Calculating Statutory Tax under Old & New Regimes...")
    res_old = old_calc.calculate(data, inc_old, params, filing_date)
    res_new = new_calc.calculate(data, inc_new, params, filing_date)
    print(f"  Old Regime Tax Liability: {format_inr(res_old.total_tax_liability)} (Refund: {format_inr(res_old.refund_due)})")
    print(f"  New Regime Tax Liability: {format_inr(res_new.total_tax_liability)} (Refund: {format_inr(res_new.refund_due)})")
    print()

    # 5. Regime Comparison
    print("[Agent 5] Running Regime Comparison & Breakeven Sensitivity Analysis...")
    comparison, audit = comparison_agent.run(data, res_old, res_new)
    print(f"  RECOMMENDATION: {comparison.recommended.value.upper()} REGIME")
    print(f"  NET TAX SAVINGS: {format_inr(comparison.savings)}")
    print(f"  BREAKEVEN DEDUCTION THRESHOLD: {format_inr(comparison.breakeven_deduction_amount)}")
    for r in comparison.reasons:
        print(f"  - {r}")
    print()

    # 6. Verification & Completeness
    print("[Agent 6 & 7] Verifying 11 Statutory Integrity Checks...")
    ver_res, ver_audit = verifier.run(data, comparison, filing_date=filing_date)
    print(f"  Verification Status: {'PASSED' if ver_res.valid else 'FAILED'} (Confidence: {ver_res.confidence_score * 100:.1f}%)")
    for chk in ver_res.checks:
        status_sym = "[OK]" if chk.passed else "[ERR]"
        print(f"    {status_sym} {chk.name}: {chk.message}")
    print()

    # 7. Form Selection & CBDT JSON Generation
    print("[Agent 8] Determining Eligible ITR Form & Building CBDT JSON...")
    target_res = res_old if comparison.recommended == Regime.OLD else res_new
    itr_form, reasons = select_itr_form(data, target_res.income.total_income)
    print(f"  Selected Form: {itr_form.value}")
    for r in reasons:
        print(f"    - {r}")

    out_dir = BASE_DIR / "output"
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "mid_career_ITR1.json"
    builder = ITR1Builder()
    payload = builder.build(data, target_res, params, "SUB-DEMO-001")
    is_valid, validation_errors = validate_itr_json("ITR-1", payload)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  Generated ITR JSON: {json_path}")
    print(f"  CBDT Schema Validation: {'PASSED' if is_valid else f'FAILED: {validation_errors}'}")
    print()

    # 8. CA-Grade 8-Page PDF Advisory Report
    print("[Report Agent] Generating 8-Page CA-Grade Regime Comparison Advisory Report...")
    pdf_path = out_dir / "mid_career_advisory_report.pdf"
    pdf_bytes = pdf_service.generate_pdf(data, comparison, ver_res, "SUB-DEMO-001", pdf_path)
    print(f"  PDF Report saved to: {pdf_path} ({len(pdf_bytes):,} bytes)")
    print()

    print("=" * 80)
    print("  DEMONSTRATION COMPLETE - ALL 8 AGENTS EXECUTED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
