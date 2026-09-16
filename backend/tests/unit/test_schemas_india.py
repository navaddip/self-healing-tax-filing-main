from datetime import date
from decimal import Decimal

import pytest

from app.schemas.tax import (
    Form16,
    HeadwiseIncome,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    RegimeTaxResult,
    ResidentialStatus,
    SalaryBreakup,
    _to_decimal,
)
from app.schemas.validators import (
    AgeBand,
    age_band_from_dob,
    mask_pan,
    validate_ifsc,
    validate_pan,
)


def test_pan_validation_rules():
    # Accepts valid individual PAN: 5 letters (4th 'P'), 4 digits, 1 letter
    assert validate_pan("ABCPD1234E") is True
    # Rejects 4th char other than 'P' for individual (e.g. 'X')
    assert validate_pan("ABCXD1234E") is False
    # Rejects invalid length (9 characters)
    assert validate_pan("ABCP1234E") is False
    # Rejects empty or None
    assert validate_pan("") is False
    assert validate_pan(None) is False


def test_pan_masking():
    assert mask_pan("ABCPD1234E") == "ABC****4E"
    assert mask_pan("ABCPL9999F") == "ABC****9F"
    assert mask_pan("") == ""
    assert mask_pan(None) == ""


def test_ifsc_validation():
    assert validate_ifsc("HDFC0001234") is True
    assert validate_ifsc("SBIN0000300") is True
    assert validate_ifsc("HDFC1001234") is False  # 5th char must be 0
    assert validate_ifsc("HDFC0123") is False      # too short


def test_decimal_coercion():
    assert _to_decimal("₹1,50,000") == Decimal("150000")
    assert _to_decimal("1,50,000.00") == Decimal("150000.00")
    assert _to_decimal("Rs. 75,000") == Decimal("75000")
    assert _to_decimal("INR 2500") == Decimal("2500")
    assert _to_decimal(150000) == Decimal("150000")
    assert _to_decimal(None) == Decimal("0")
    assert _to_decimal("") == Decimal("0")


def test_age_band_boundaries_at_fy_end():
    fy_end = date(2026, 3, 31)

    # Exactly 60 on 31 March 2026 -> SENIOR_60_80
    assert age_band_from_dob(date(1966, 3, 31), fy_end) == AgeBand.SENIOR_60_80

    # Born 1 April 1966 -> 59 on 31 March 2026 -> BELOW_60
    assert age_band_from_dob(date(1966, 4, 1), fy_end) == AgeBand.BELOW_60

    # Exactly 80 on 31 March 2026 -> SUPER_SENIOR_80_PLUS
    assert age_band_from_dob(date(1946, 3, 31), fy_end) == AgeBand.SUPER_SENIOR_80_PLUS

    # Born 1 April 1946 -> 79 on 31 March 2026 -> SENIOR_60_80
    assert age_band_from_dob(date(1946, 4, 1), fy_end) == AgeBand.SENIOR_60_80


def test_indian_taxpayer_data_initialization():
    f16 = Form16(
        employer_name="Acme Corp India",
        employer_tan="DELA12345B",
        gross_salary_17_1="₹15,00,000",
        standard_deduction="50,000",
        tds_deducted="1,45,000",
    )
    assert f16.gross_salary_17_1 == Decimal("1500000")
    assert f16.standard_deduction == Decimal("50000")
    assert f16.tds_deducted == Decimal("145000")

    taxpayer = IndianTaxpayerData(
        name="Ramesh Kumar",
        pan="ABCPK1234A",
        date_of_birth=date(1990, 5, 15),
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        form16s=[f16],
    )
    taxpayer.aggregate_form16s()
    assert taxpayer.masked_pan == "ABC****4A"
    assert taxpayer.taxes_paid.tds_salary == Decimal("145000")
