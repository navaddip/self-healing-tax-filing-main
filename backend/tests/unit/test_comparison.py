"""Unit tests for Milestone 5: Regime Comparison Agent & Workflow Wiring."""

from datetime import date
from decimal import Decimal

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
    TaxesPaid,
)
from app.tax_rules.params import get_params
from app.workflow.graph import TaxWorkflow
from app.workflow.state import TaxWorkflowState


@pytest.fixture
def params():
    return get_params("2025-26")


@pytest.fixture
def income_service():
    return IncomeComputationService()


@pytest.fixture
def old_calculator():
    return OldRegimeCalculator()


@pytest.fixture
def new_calculator():
    return NewRegimeCalculator()


@pytest.fixture
def comparison_agent(params):
    return RegimeComparisonAgent(params)


def test_golden_case_1_comparison(params, income_service, old_calculator, new_calculator, comparison_agent):
    """Case 1: Mid-career salaried, heavy old-regime claims -> OLD wins, saving ₹23,380."""
    data = IndianTaxpayerData(
        name="Mid-Career Salaried",
        pan="ABCPS1234F",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Tech Corp India",
                gross_salary_17_1=Decimal("1500000"),
                professional_tax=Decimal("2400"),
                tds_deducted=Decimal("145000"),
            )
        ],
        salary_breakup=SalaryBreakup(
            basic=Decimal("900000"),
            hra_received=Decimal("360000"),
            rent_paid_annual=Decimal("290000"),
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

    inc_old = income_service.compute(data, Regime.OLD, params)
    inc_new = income_service.compute(data, Regime.NEW, params)

    filing_date = date(2026, 7, 31)
    res_old = old_calculator.calculate(data, inc_old, params, filing_date)
    res_new = new_calculator.calculate(data, inc_new, params, filing_date)

    assert res_old.total_tax_liability == Decimal("62420")
    assert res_new.total_tax_liability == Decimal("85800")
    assert res_old.refund_due == Decimal("82580")
    assert res_new.refund_due == Decimal("59200")

    comparison, audit = comparison_agent.run(data, res_old, res_new)

    assert comparison.recommended == Regime.OLD
    assert comparison.savings == Decimal("23380")
    assert comparison.switch_allowed_annually is True
    assert comparison.form_10iea_required is False

    # Breakeven deduction check: must land on ₹6,65,000 to the rupee
    assert comparison.breakeven_deduction_amount == Decimal("665000")

    # Deltas table must contain all key rows
    delta_lines = [row["line"] for row in comparison.deltas]
    assert "Gross salary" in delta_lines
    assert "Standard deduction" in delta_lines
    assert "Rebate u/s 87A" in delta_lines
    assert "Total tax liability" in delta_lines

    # Forfeited deductions check
    assert "Exempt Allowances (HRA/LTA)" in comparison.deductions_forfeited_if_new
    assert comparison.deductions_forfeited_if_new["Exempt Allowances (HRA/LTA)"] == Decimal("200000")
    assert "Home Loan Interest SOP u/s 24(b)" in comparison.deductions_forfeited_if_new
    assert comparison.deductions_forfeited_if_new["Home Loan Interest SOP u/s 24(b)"] == Decimal("200000")

    # Reasons list check
    assert any("665,000" in r for r in comparison.reasons)
    assert any("124,800" in r for r in comparison.reasons)


def test_golden_case_2_comparison(params, income_service, old_calculator, new_calculator, comparison_agent):
    """Case 2: Salaried ₹12,00,000, thin claims -> NEW wins, saving ₹1,48,200."""
    data = IndianTaxpayerData(
        name="Salaried Junior",
        pan="ABCPS5678G",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="ABC Ltd",
                gross_salary_17_1=Decimal("1200000"),
            )
        ],
        deduction_claims={
            "80C": Decimal("50000"),
        },
    )

    inc_old = income_service.compute(data, Regime.OLD, params)
    inc_new = income_service.compute(data, Regime.NEW, params)

    filing_date = date(2026, 7, 31)
    res_old = old_calculator.calculate(data, inc_old, params, filing_date)
    res_new = new_calculator.calculate(data, inc_new, params, filing_date)

    assert res_old.total_tax_liability == Decimal("148200")
    assert res_new.total_tax_liability == Decimal("0")

    comparison, audit = comparison_agent.run(data, res_old, res_new)

    assert comparison.recommended == Regime.NEW
    assert comparison.savings == Decimal("148200")
    assert any("rebate wipes out your entire liability" in r for r in comparison.reasons)


def test_sensitivity_table(params, comparison_agent):
    """Test sensitivity analysis produces monotonic old tax with deduction changes."""
    data = IndianTaxpayerData(
        name="Sensitivity Test",
        pan="ABCPS1234F",
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Corp",
                gross_salary_17_1=Decimal("1500000"),
            )
        ],
        deduction_claims={"80C": Decimal("150000")},
    )

    deltas = [Decimal("-50000"), Decimal("0"), Decimal("50000"), Decimal("100000")]
    sens = comparison_agent.sensitivity(data, params, deltas)

    assert len(sens) == 4
    # As deduction increases, old tax must decrease or remain constant
    for i in range(len(sens) - 1):
        assert sens[i]["old_tax"] >= sens[i + 1]["old_tax"]


def test_workflow_execution_graph(params):
    """Test full LangGraph execution visiting income computation, dual engines, and comparison."""
    workflow = TaxWorkflow()

    sample_data = IndianTaxpayerData(
        name="Workflow Test User",
        pan="ABCPS9999Z",
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Acme Corp",
                gross_salary_17_1=Decimal("1500000"),
                professional_tax=Decimal("2400"),
                tds_deducted=Decimal("145000"),
            )
        ],
        salary_breakup=SalaryBreakup(
            basic=Decimal("900000"),
            hra_received=Decimal("360000"),
            rent_paid_annual=Decimal("290000"),
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

    initial_state: TaxWorkflowState = {
        "submission_id": "test-sub-001",
        "original_filename": "form16.pdf",
        "upload_path": "dummy.pdf",
        "extracted_data": sample_data.model_dump(mode="json"),
    }

    final_state = workflow.run(initial_state)

    assert "comparison" in final_state
    assert final_state["comparison"]["recommended"] == "old"
    assert Decimal(str(final_state["comparison"]["savings"])) == Decimal("23380")
    assert final_state["status"] == "completed"
