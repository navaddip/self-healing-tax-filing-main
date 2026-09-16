"""Unit tests for Milestone 6: Indian Document Reading Agent & Parsers."""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.reading.agent import ReadingAgent
from app.schemas.tax import Regime
from app.services.extraction.india.ais_parser import AISParser
from app.services.extraction.india.broker_pnl_parser import BrokerPnLParser
from app.services.extraction.india.certificate_parsers import (
    HomeLoanCertificateParser,
    InterestCertificateParser,
    RentReceiptParser,
)
from app.services.extraction.india.form16_parser import Form16Parser
from app.services.extraction.india.form26as_parser import Form26ASParser


def test_form16_parser_part_a_and_b():
    sample_text = """
    FORM NO. 16
    PART A
    Certificate under section 203 of the Income-tax Act, 1961
    Employer Name: Tech Solutions India Pvt Ltd
    TAN of the Deductor: BLRT12345A
    PAN of the Deductor: AAABT1234F
    Certificate Number: CERT-2025-001
    Period with the Employer: 01/04/2025 to 31/03/2026
    Total amount of tax deducted: Rs. 1,45,000.00

    PART B
    1. Gross Salary:
    (a) Salary as per provisions contained in section 17(1): Rs. 15,00,000
    (b) Value of perquisites under section 17(2): 0
    (c) Profits in lieu of salary under section 17(3): 0
    2. Less: Allowances to the extent exempt under section 10:
       House Rent Allowance u/s 10(13A): Rs. 2,00,000
    3. Balance (1 - 2): Rs. 13,00,000
    4. Less: Deductions under section 16:
       (a) Standard deduction under section 16(ia): Rs. 50,000
       (c) Tax on employment under section 16(iii): Rs. 2,400
    5. Aggregate of deductions under section 16: Rs. 52,400
    6. Income chargeable under the head 'Salaries' (3 - 5): Rs. 12,47,600
    7. Deductions under Chapter VI-A:
       Section 80C: Rs. 1,50,000
       Section 80D: Rs. 25,000
       Section 80CCD1B: Rs. 50,000
       Section 80CCD2: Rs. 90,000
       Section 80TTA: Rs. 10,000
    """
    parser = Form16Parser()
    form16, ev = parser.parse(sample_text)

    assert form16.employer_name == "Tech Solutions India Pvt Ltd"
    assert form16.employer_tan == "BLRT12345A"
    assert form16.gross_salary_17_1 == Decimal("1500000")
    assert form16.exempt_allowances_10["hra"] == Decimal("200000")
    assert form16.standard_deduction == Decimal("50000")
    assert form16.professional_tax == Decimal("2400")
    assert form16.taxable_salary_per_employer == Decimal("1247600")
    assert form16.tds_deducted == Decimal("145000")
    assert form16.chapter_via_claimed["80C"] == Decimal("150000")
    assert form16.chapter_via_claimed["80CCD2"] == Decimal("90000")
    assert form16.regime_used == Regime.OLD
    assert len(ev) >= 8


def test_form16_new_regime_detection():
    sample_text = """
    FORM NO. 16 PART B
    Gross Salary: Rs. 12,00,000
    Standard deduction under section 16(ia): Rs. 75,000
    Income chargeable under the head 'Salaries': Rs. 11,25,000
    Total amount of tax deducted: Rs. 0
    """
    parser = Form16Parser()
    form16, _ = parser.parse(sample_text)

    assert form16.gross_salary_17_1 == Decimal("1200000")
    assert form16.standard_deduction == Decimal("75000")
    assert form16.regime_used == Regime.NEW


def test_form26as_parser():
    sample_text = """
    FORM 26AS - Annual Tax Statement u/s 206CA
    PART I - Details of Tax Deducted at Source on Salary (192)
    Total TDS Deposited: Rs. 1,45,000

    PART II - Details of Tax Deducted at Source for Other than Salary
    Total TDS Deposited: Rs. 5,000

    PART VI - Details of Tax Collected at Source
    Tax Collected at Source: Rs. 1,200

    PART VIII - Details of Advance Tax and Self Assessment Tax
    Challan BSR Code: 0210045 Date: 15/03/2026 Serial: 00123 Advance Tax: Rs. 25,000
    """
    parser = Form26ASParser()
    taxes_paid, ev = parser.parse(sample_text)

    assert taxes_paid.tds_salary == Decimal("145000")
    assert taxes_paid.tds_non_salary == Decimal("5000")
    assert taxes_paid.tcs == Decimal("1200")
    assert len(taxes_paid.advance_tax_instalments) >= 1
    assert Decimal("25000") in taxes_paid.advance_tax_instalments.values()


def test_ais_parser_and_password():
    parser = AISParser()
    pwd = parser.derive_password("ABCPS1234F", "15-08-1990")
    assert pwd == "abcps1234f15081990"

    pwd_date = parser.derive_password("ABCPS1234F", date(1990, 8, 15))
    assert pwd_date == "abcps1234f15081990"

    sample_text = """
    Annual Information Statement (AIS)
    Salary: Rs. 15,00,000
    Interest from savings bank: Rs. 15,000
    Interest from deposit: Rs. 40,000
    Dividend income: Rs. 8,000
    Sale of securities and units of mutual fund: Rs. 2,50,000
    """
    parsed, ev = parser.parse(sample_text)
    assert parsed["salary"] == Decimal("1500000")
    assert parsed["savings_interest"] == Decimal("15000")
    assert parsed["fd_interest"] == Decimal("40000")
    assert parsed["dividend_income"] == Decimal("8000")
    assert parsed["securities_sale_value"] == Decimal("250000")


def test_broker_pnl_parser():
    csv_text = """Symbol,ISIN,Buy Date,Buy Value,Sell Date,Sell Value,Charges,Term
RELIANCE,INE002A01018,10-01-2023,100000,15-02-2026,160000,200,Long Term
TCS,INE467B01029,01-01-2026,50000,15-02-2026,58000,100,Short Term
INFY,INE009A01021,01-01-2026,80000,10-02-2026,75000,100,Long Term
"""
    parser = BrokerPnLParser()
    items, ev, warnings = parser.parse_csv(csv_text)

    assert len(items) == 3
    # RELIANCE: 2023 to 2026 is > 365 days -> is_pre_23jul2024 is True
    assert items[0].cost_of_acquisition == Decimal("100000")
    assert items[0].sale_consideration == Decimal("160000")
    assert items[0].transfer_expenses == Decimal("200")
    assert items[0].stt_paid is True
    assert items[0].is_pre_23jul2024 is True

    # TCS: 01-01-2026 to 15-02-2026 is short term
    assert items[1].cost_of_acquisition == Decimal("50000")
    assert items[1].is_pre_23jul2024 is False

    # INFY: bought 01-01-2026, sold 10-02-2026 (40 days) but declared Long Term -> warning generated!
    assert len(warnings) >= 1
    assert any("INFY" in w and "40 days" in w for w in warnings)


def test_certificate_parsers():
    # Interest Certificate
    int_parser = InterestCertificateParser()
    int_text = """
    State Bank of India - Interest Certificate
    Savings Bank Account Interest Credited: Rs. 15,000
    Fixed Deposit / TDR Interest: Rs. 45,000
    TDS deducted u/s 194A: Rs. 4,500
    """
    int_res, _ = int_parser.parse(int_text)
    assert int_res["savings_interest"] == Decimal("15000")
    assert int_res["fd_interest"] == Decimal("45000")
    assert int_res["tds_194a"] == Decimal("4500")

    # Home Loan Certificate
    hl_parser = HomeLoanCertificateParser()
    hl_text = """
    HDFC Bank - Housing Loan Provisional Certificate
    Principal Repaid u/s 80C: Rs. 1,20,000
    Interest Paid u/s 24(b): Rs. 2,00,000
    Ownership Share: 100%
    """
    hp, _ = hl_parser.parse(hl_text)
    assert hp.is_self_occupied is True
    assert hp.principal_repaid_80c == Decimal("120000")
    assert hp.interest_on_loan_24b == Decimal("200000")
    assert hp.co_owner_share == Decimal("1")

    # Rent Receipt
    rent_parser = RentReceiptParser()
    rent_text = """
    RENT RECEIPT
    Received a sum of Rs. 25,000 per month for flat in Mumbai
    Landlord PAN: ABCDE1234F
    """
    rent_res, _ = rent_parser.parse(rent_text)
    assert rent_res["monthly_rent"] == Decimal("25000")
    assert rent_res["annual_rent"] == Decimal("300000")
    assert rent_res["landlord_pan"] == "ABCDE1234F"
    assert rent_res["is_metro"] is True
