import sys
from datetime import date
from pathlib import Path
from decimal import Decimal

# Ensure backend is in python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import fitz
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.comparison.agent import RegimeComparisonAgent
from app.schemas.tax import (
    IndianTaxpayerData,
    Form16,
    HouseProperty,
    SalaryBreakup,
    TaxesPaid,
    Regime,
    AgeBand,
    ResidentialStatus,
)
from app.tax_rules.params import get_params
from app.services.pdf.comparison_report import ComparisonReportService

def main():
    params = get_params("2025-26")
    income_service = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    f16 = Form16(
        employer_name="Acme Corp India Pvt Ltd",
        employer_tan="DELA12345B",
        gross_salary_17_1=Decimal("1800000"),
        exempt_allowances_10={"HRA": Decimal("300000")},
        standard_deduction=Decimal("50000"),
        professional_tax=Decimal("2400"),
        reported_house_property_loss=Decimal("200000"),
        tds_deducted=Decimal("114420"),
    )

    data = IndianTaxpayerData(
        pan="ABCDE1234F",
        name="Rajesh Kumar",
        assessment_year="2026-27",
        financial_year="2025-26",
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        age_band=AgeBand.BELOW_60,
        form16s=[f16],
        deduction_claims={
            "80C": Decimal("150000"),
            "80CCD1B": Decimal("50000"),
            "80D": Decimal("25000"),
            "80E": Decimal("25000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("114420")),
    )

    inc_old = income_service.compute(data, Regime.OLD, params)
    inc_new = income_service.compute(data, Regime.NEW, params)

    filing_date = date(2026, 7, 28)
    res_old = old_calc.calculate(data, inc_old, params, filing_date)
    res_new = new_calc.calculate(data, inc_new, params, filing_date)

    comp, _ = comp_agent.run(data, res_old, res_new)

    svc = ComparisonReportService()
    out_dir = Path(__file__).resolve().parent.parent / "output" / "pdf"
    out_dir.mkdir(exist_ok=True)
    pdf_path = out_dir / "ay2026_27_tax_regime_comparison.pdf"
    svc.generate_pdf(data, comp, output_path=pdf_path)

    doc = fitz.open(pdf_path)
    print(f"PDF generated successfully! Total pages: {len(doc)}")
    prev_dir = out_dir / "report_preview"
    prev_dir.mkdir(exist_ok=True)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        pix.save(prev_dir / f"page_{i+1}.png")
    print(f"Rendered all {len(doc)} pages to {prev_dir}")

if __name__ == "__main__":
    main()
