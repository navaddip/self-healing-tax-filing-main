"""Opt-in integration: set TAX_TEST_FORM16 to a consented local Form 16.
The document is never copied into the repository or included in test artifacts.
"""
import os
from pathlib import Path
import pytest
from app.agents.reading.agent import ReadingAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.comparison.agent import RegimeComparisonAgent
from app.schemas.tax import Regime
from app.tax_rules.params import get_params
from app.services.pdf.comparison_report import ComparisonReportService
from app.services.pdf.validation import validate_pdf_bytes

@pytest.mark.skipif(not os.environ.get("TAX_TEST_FORM16"), reason="Private document integration is opt-in")
def test_form16_document_pipeline():
    data, _, evidence = ReadingAgent().run(Path(os.environ["TAX_TEST_FORM16"]))
    assert data.form16s and evidence
    params = get_params(data.financial_year)
    income = IncomeComputationService()
    old = OldRegimeCalculator().calculate(data, income.compute(data, Regime.OLD, params), params, params.filing_due_date)
    new = NewRegimeCalculator().calculate(data, income.compute(data, Regime.NEW, params), params, params.filing_due_date)
    comparison, _ = RegimeComparisonAgent(params).run(data, old, new)
    assert old.income.gross_salary > 0
    pdf = ComparisonReportService().generate_pdf(data, comparison, submission_id="private-integration")
    assert validate_pdf_bytes(pdf, data, comparison, params) == []
