"""Integration tests for Milestone 9: 8-Page Regime Comparison Advisory Report (PDF)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.schemas.tax import (
    AgeBand,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    Regime,
    ResidentialStatus,
    SalaryBreakup,
    SourceEvidence,
    SubmissionResult,
    TaxesPaid,
    VerificationResult,
    WorkflowStatus,
)
from app.services.pdf.comparison_report import (
    ComparisonReportService,
    ProfessionalReportService,
)
from app.services.pdf.style import inr, inr_words
from app.tax_rules.params import get_params


def test_inr_formatting_boundaries():
    """Verify Indian digit grouping across 12 required boundary values."""
    assert inr(0) == "0"
    assert inr(999) == "999"
    assert inr(1000) == "1,000"
    assert inr(99999) == "99,999"
    assert inr(100000) == "1,00,000"
    assert inr(1234567) == "12,34,567"
    assert inr(9999999) == "99,99,999"
    assert inr(10000000) == "1,00,00,000"
    assert inr(25000000) == "2,50,00,000"
    # Negatives in parentheses
    assert inr(-45300) == "(45,300)"
    assert inr(-100000) == "(1,00,000)"
    # Decimals
    assert inr(Decimal("1234567.50"), decimals=2) == "12,34,567.50"


def test_inr_words_converter():
    assert inr_words(0) == "Rupees Zero only"
    assert inr_words(82580) == "Rupees Eighty Two Thousand Five Hundred Eighty only"
    assert inr_words(148200) == "Rupees One Lakh Forty Eight Thousand Two Hundred only"


def test_golden_case_1_pdf_generation(tmp_path):
    """Verify Golden Case 1 produces an 8-page PDF matching CA standards."""
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    old_calc = OldRegimeCalculator()
    new_calc = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    data = IndianTaxpayerData(
        name="Mid-Career Salaried",
        pan="ABCPS1234F",
        bank_ifsc="HDFC0001234",
        bank_account_last4="5678",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Tech Corp India",
                employer_tan="BLRT12345A",
                gross_salary_17_1=Decimal("1500000"),
                professional_tax=Decimal("2400"),
                tds_deducted=Decimal("145000"),
            )
        ],
        salary_breakup=SalaryBreakup(
            basic=Decimal("900000"),
            hra_received=Decimal("360000"),
            rent_paid_annual=Decimal("290000"),
            landlord_pan="AAABT1234F",
            is_metro=False,
        ),
        house_properties=[
            HouseProperty(
                is_self_occupied=True,
                interest_on_loan_24b=Decimal("200000"),
            )
        ],
        savings_interest=Decimal("15000"),
        deduction_claims={
            "80C": Decimal("150000"),
            "80D": Decimal("25000"),
            "80CCD1B": Decimal("50000"),
            "80CCD2": Decimal("90000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("145000")),
    )

    inc_old = inc_svc.compute(data, Regime.OLD, params)
    inc_new = inc_svc.compute(data, Regime.NEW, params)
    res_old = old_calc.calculate(data, inc_old, params, date(2026, 7, 31))
    res_new = new_calc.calculate(data, inc_new, params, date(2026, 7, 31))

    comparison, _ = comp_agent.run(data, res_old, res_new)

    report_path = tmp_path / "case1_report.pdf"
    service = ComparisonReportService()
    pdf_bytes = service.generate_pdf(
        data=data,
        comparison=comparison,
        submission_id="SUB-CASE-1",
        output_path=report_path,
    )

    assert report_path.exists()
    assert len(pdf_bytes) > 5000

    # Open with PyMuPDF to inspect structure
    doc = fitz.open(report_path)
    assert doc.page_count == 8

    # Page 1 checks
    page1_text = doc[0].get_text()
    assert "RECOMMENDED: OLD REGIME" in page1_text
    assert "23,380" in page1_text  # Correct Indian digit grouping
    assert "Old Regime" in page1_text
    assert "Refund Due" in page1_text

    # Check footer disclaimer on every page
    for i in range(8):
        page_text = doc[i].get_text()
        assert "Technology Meets Compliance" in page_text
        assert f"Page {i + 1} of 8" in page_text

    # The downloadable filing package appends the exact uploaded Form 16 after
    # the eight-page advisory, making the source document the final page.
    source_path = tmp_path / "uploaded_form16.pdf"
    source = fitz.open()
    source_page = source.new_page()
    source_page.insert_text((72, 72), "UPLOADED FORM 16 SOURCE")
    source.save(source_path)
    source.close()

    final_path = tmp_path / "tax_filing_package.pdf"
    result = SubmissionResult(
        submission_id="SUB-CASE-1",
        status=WorkflowStatus.COMPLETED,
        original_filename=source_path.name,
        extracted_data=data,
        comparison=comparison,
        verification=VerificationResult(
            valid=True,
            confidence_score=0.98,
            checks=[],
        ),
    )
    # Mirror the real workflow boundary where state is serialized to JSON and
    # Decimal values inside the free-form comparison delta rows become strings.
    persisted_result = SubmissionResult.model_validate(
        result.model_dump(mode="json")
    )
    ProfessionalReportService().run(persisted_result, final_path, source_path)

    final_doc = fitz.open(final_path)
    assert final_doc.page_count == 9
    assert "UPLOADED FORM 16 SOURCE" in final_doc[-1].get_text()
    assert "RECOMMENDED: OLD REGIME" in final_doc[0].get_text()
