"""Unit tests for ITR JSON builders (ITR-1, ITR-2, ITR-4), schema validation, and e-file backends."""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.comparison.agent import RegimeComparisonAgent
from app.itr.form_selector import ItrForm, select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.itr2_builder import ITR2Builder
from app.itr.itr4_builder import ITR4Builder
from app.itr.schema_loader import ITRSchemaLoader, validate_itr_json
from app.schemas.tax import (
    CapitalGainItem,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    PresumptiveBusiness,
    Regime,
    SubmissionResult,
    TaxesPaid,
    VerificationCheck,
    VerificationResult,
    WorkflowStatus,
)
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.services.efile.backends import JsonSelfFileBackend, MockEriBackend, get_backend
from app.agents.income.computation import IncomeComputationService
from app.tax_rules.params import get_params


@pytest.fixture
def base_salaried_data():
    return IndianTaxpayerData(
        name="Aditi Sharma",
        pan="ABCPA1234E",
        bank_ifsc="SBIN0001234",
        bank_account_last4="4321",
        financial_year="2025-26",
        form16s=[
            Form16(
                employer_name="Infosys Ltd",
                employer_tan="BLRI00123A",
                gross_salary_17_1=Decimal("1500000"),
                professional_tax=Decimal("2400"),
                tds_deducted=Decimal("145000"),
            )
        ],
        savings_interest=Decimal("12000"),
        deduction_claims={
            "80C": Decimal("150000"),
            "80D": Decimal("25000"),
            "80CCD1B": Decimal("50000"),
            "80TTA": Decimal("10000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("145000")),
    )


def test_itr1_builder_and_validation(base_salaried_data):
    """Verify ITR-1 builder generates a compliant JSON payload passing schema checks."""
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    calc_new = NewRegimeCalculator()

    inc = inc_svc.compute(base_salaried_data, Regime.NEW, params)
    tax_res = calc_new.calculate(base_salaried_data, inc, params, date(2026, 7, 31))

    builder = ITR1Builder()
    payload = builder.build(base_salaried_data, tax_res, params, "SUB-TEST-001")

    assert "ITR" in payload
    assert "ITR1" in payload["ITR"]
    itr1 = payload["ITR"]["ITR1"]

    assert itr1["PersonalInfo"]["PAN"] == "ABCPA1234E"
    assert itr1["FilingStatus"]["OptOutNewTaxRegime"] == "N"
    assert itr1["IncomeDeductions"]["TotalIncome"] == int(tax_res.income.total_income)

    valid, errors = validate_itr_json("ITR-1", payload)
    assert valid is True, f"Validation errors: {errors}"


def test_itr2_builder_capital_gains(base_salaried_data):
    """Verify ITR-2 builder generates Schedule CG and passes schema checks."""
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    calc_new = NewRegimeCalculator()

    # Add capital gains and second property
    base_salaried_data.house_properties.append(
        HouseProperty(is_self_occupied=False, annual_rent_received=Decimal("240000"), is_let_out=True)
    )
    base_salaried_data.capital_gains = [
        CapitalGainItem(
            asset_type="listed_equity",
            sale_consideration=Decimal("150000"),
            cost_of_acquisition=Decimal("100000"),
            stt_paid=True,
            gain=Decimal("50000"),
            is_long_term=False,
        ),
        CapitalGainItem(
            asset_type="listed_equity",
            sale_consideration=Decimal("500000"),
            cost_of_acquisition=Decimal("300000"),
            stt_paid=True,
            gain=Decimal("200000"),
            is_long_term=True,
        ),
    ]

    inc = inc_svc.compute(base_salaried_data, Regime.NEW, params)
    tax_res = calc_new.calculate(base_salaried_data, inc, params, date(2026, 7, 31))

    builder = ITR2Builder()
    payload = builder.build(base_salaried_data, tax_res, params, "SUB-TEST-002")

    assert "ITR" in payload
    assert "ITR2" in payload["ITR"]
    itr2 = payload["ITR"]["ITR2"]

    assert "ScheduleCG" in itr2
    assert itr2["ScheduleCG"]["ShortTermCapGain"]["Sec111A"] == 50000
    assert itr2["ScheduleCG"]["LongTermCapGain"]["Sec112A"]["TaxableAmount"] == 75000  # 200k - 125k

    valid, errors = validate_itr_json("ITR-2", payload)
    assert valid is True, f"Validation errors: {errors}"


def test_itr4_builder_presumptive(base_salaried_data):
    """Verify ITR-4 builder generates Schedule BP for 44ADA freelance income."""
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    calc_new = NewRegimeCalculator()

    base_salaried_data.presumptive = PresumptiveBusiness(
        section="44ADA",
        turnover=Decimal("1200000"),
        declared_profit=Decimal("600000"),
    )

    inc = inc_svc.compute(base_salaried_data, Regime.NEW, params)
    tax_res = calc_new.calculate(base_salaried_data, inc, params, date(2026, 7, 31))

    builder = ITR4Builder()
    payload = builder.build(base_salaried_data, tax_res, params, "SUB-TEST-004")

    assert "ITR" in payload
    assert "ITR4" in payload["ITR"]
    itr4 = payload["ITR"]["ITR4"]

    assert "ScheduleBP" in itr4["IncomeDeductions"]
    assert itr4["IncomeDeductions"]["ScheduleBP"]["PresumptiveInc44ADA"]["GrossReceipts"] == 1200000
    assert itr4["IncomeDeductions"]["ScheduleBP"]["PresumptiveInc44ADA"]["DeemedProfit"] == 600000

    valid, errors = validate_itr_json("ITR-4", payload)
    assert valid is True, f"Validation errors: {errors}"


def test_json_self_file_backend(base_salaried_data, tmp_path):
    """Test JsonSelfFileBackend produces instructions, hash, and receipt."""
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    calc_old = OldRegimeCalculator()
    calc_new = NewRegimeCalculator()
    comp_agent = RegimeComparisonAgent(params)

    inc_old = inc_svc.compute(base_salaried_data, Regime.OLD, params)
    inc_new = inc_svc.compute(base_salaried_data, Regime.NEW, params)
    res_old = calc_old.calculate(base_salaried_data, inc_old, params, date(2026, 7, 31))
    res_new = calc_new.calculate(base_salaried_data, inc_new, params, date(2026, 7, 31))

    comparison, _ = comp_agent.run(base_salaried_data, res_old, res_new)

    sub_result = SubmissionResult(
        submission_id="SUB-TEST-SELF",
        status=WorkflowStatus.REVIEW_READY,
        original_filename="form16.pdf",
        extracted_data=base_salaried_data,
        comparison=comparison,
    )

    backend = JsonSelfFileBackend()
    ack = backend.submit(sub_result, output_dir=tmp_path)

    assert ack.accepted is True
    assert ack.channel == "json_self_file"
    assert ack.status == "ready_to_self_file"
    assert ack.itr_form == "ITR-1"
    assert ack.json_hash is not None
    assert "incometax.gov.in" in ack.instructions

    assert sub_result.receipt is not None
    assert sub_result.receipt.filing_type == "json_self_file"
    assert sub_result.receipt.payload_hash == ack.json_hash

    # Check written file
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert "ABCPA1234E_ITR-1_AY2026-27.json" in files[0].name


def test_mock_eri_backend(base_salaried_data):
    """Test MockEriBackend rejects unverified returns and produces 15-digit ack for valid returns."""
    backend = MockEriBackend()

    # Case 1: Unverified return -> Rejected
    unverified_result = SubmissionResult(
        submission_id="SUB-UNVERIFIED",
        status=WorkflowStatus.REVIEW_READY,
        original_filename="test.pdf",
        extracted_data=base_salaried_data,
        verification=VerificationResult(
            valid=False,
            confidence_score=0.4,
            checks=[VerificationCheck(name="TDS Check", passed=False, message="Mismatch")],
        ),
    )
    ack_fail = backend.submit(unverified_result)
    assert ack_fail.accepted is False
    assert ack_fail.status == "rejected"
    assert ack_fail.reject_codes is not None

    # Case 2: Verified return -> Accepted with 15-digit acknowledgement
    params = get_params("2025-26")
    inc_svc = IncomeComputationService()
    calc_new = NewRegimeCalculator()
    inc_new = inc_svc.compute(base_salaried_data, Regime.NEW, params)
    res_new = calc_new.calculate(base_salaried_data, inc_new, params, date(2026, 7, 31))
    comp_agent = RegimeComparisonAgent(params)
    comparison, _ = comp_agent.run(base_salaried_data, res_new, res_new)

    verified_result = SubmissionResult(
        submission_id="SUB-VERIFIED-123",
        status=WorkflowStatus.APPROVED,
        original_filename="test.pdf",
        extracted_data=base_salaried_data,
        comparison=comparison,
        verification=VerificationResult(
            valid=True,
            confidence_score=1.0,
            checks=[VerificationCheck(name="Math Check", passed=True, message="All checks passed")],
        ),
    )
    ack_pass = backend.submit(verified_result)
    assert ack_pass.accepted is True
    assert ack_pass.status == "accepted"
    assert ack_pass.acknowledgement_id is not None
    assert len(ack_pass.acknowledgement_id) == 15
    assert ack_pass.acknowledgement_id.startswith("20260731")

    # Factory test
    assert isinstance(get_backend("json_self_file"), JsonSelfFileBackend)
    assert isinstance(get_backend("mock_eri"), MockEriBackend)
