"""Run the full 8-agent tax filing pipeline on the extracted data from filled_form_16.pdf."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agents.reading.agent import ReadingAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.verification.agent import VerificationAgent
from app.agents.verification.completeness import select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.schema_loader import validate_itr_json, SchemaValidationError
from app.schemas.tax import Regime
from app.tax_rules.params import get_params

def main():
    pdf_path = BASE_DIR / "filled_form_16.pdf"
    print(f"Reading {pdf_path.name} through ReadingAgent...")
    reader = ReadingAgent()
    data, text, logs = reader.run(pdf_path)

    # Add banking details for ITR refund/credit verification gate
    data.bank_account_last4 = "4819"
    data.bank_ifsc = "SBIN0001234"
    data.date_of_birth = date(1988, 6, 15)

    params = get_params("2025-26")
    income_service = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comparison_agent = RegimeComparisonAgent(params)
    verifier = VerificationAgent(params)
    filing_date = date(2026, 7, 25)

    print("\n[Heads of Income Computation]")
    inc_old = income_service.compute(data, Regime.OLD, params)
    inc_new = income_service.compute(data, Regime.NEW, params)
    print(f"  Old Regime Total Income: Rs. {inc_old.total_income:,.2f}")
    print(f"  New Regime Total Income: Rs. {inc_new.total_income:,.2f}")

    print("\n[Dual Engine Calculation]")
    res_old = old_calc.calculate(data, inc_old, params, filing_date)
    res_new = new_calc.calculate(data, inc_new, params, filing_date)
    print(f"  Old Regime Tax Liability: Rs. {res_old.total_tax_liability:,.2f} | Refund: Rs. {res_old.refund_due:,.2f}")
    print(f"  New Regime Tax Liability: Rs. {res_new.total_tax_liability:,.2f} | Refund: Rs. {res_new.refund_due:,.2f}")

    print("\n[Regime Comparison]")
    comparison, comp_audit = comparison_agent.run(data, res_old, res_new)
    print(f"  Recommended Regime: {comparison.recommended.value.upper()}")
    print(f"  Net Savings: Rs. {comparison.savings:,.2f}")
    print(f"  Breakeven Threshold: Rs. {comparison.breakeven_deduction_amount:,.2f}")
    for reason in comparison.reasons:
        print(f"  - {reason}")

    print("\n[11 Statutory Verification Gates]")
    ver_res, ver_audit = verifier.run(data, comparison, filing_date=filing_date)
    print(f"  Overall Valid: {ver_res.valid} | Confidence: {ver_res.confidence_score * 100:.1f}%")
    for chk in ver_res.checks:
        symbol = "[PASS]" if chk.passed else "[FAIL]"
        print(f"  {symbol} {chk.name}: {chk.message}")

    print("\n[Form Selection & CBDT ITR JSON Validation]")
    target_res = res_old if comparison.recommended == Regime.OLD else res_new
    itr_form, reasons = select_itr_form(data, target_res.income.total_income)
    print(f"  Selected ITR Form: {itr_form.value}")
    try:
        builder = ITR1Builder()
        payload = builder.build(data, target_res, params, "SUB-FILLED-001")
        is_valid, validation_errors = validate_itr_json("ITR-1", payload)
        print(f"  CBDT Schema Validation: {'PASSED' if is_valid else f'FAILED: {validation_errors}'}")
    except SchemaValidationError as exc:
        print(f"  CBDT Schema Export: BLOCKED (Advisory safeguard) -> {exc}")

    print("\n[Generating 8-Page Tax Comparison Advisory Report PDF...]")
    from app.services.pdf.comparison_report import ComparisonReportService
    report_service = ComparisonReportService()
    output_pdf_path = BASE_DIR / "output" / "Tax_Comparison_Advisory_Report.pdf"
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = report_service.generate_pdf(
        data=data,
        comparison=comparison,
        verification=ver_res,
        submission_id="SUB-FILLED-001",
        output_path=output_pdf_path,
    )
    print(f"  Successfully generated Advisory Report at: {output_pdf_path} ({len(pdf_bytes):,} bytes)")

if __name__ == "__main__":
    main()
