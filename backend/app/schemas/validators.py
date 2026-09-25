from __future__ import annotations

import re
from datetime import date
from enum import Enum


class AgeBand(str, Enum):
    BELOW_60 = "below_60"
    SENIOR_60_80 = "senior_60_80"
    SENIOR_60_TO_79 = "senior_60_80"
    SUPER_SENIOR_80_PLUS = "super_senior_80_plus"


GENERAL_PAN_REGEX = re.compile(r"^[A-Z]{3}[ABCFGHLJPTK][A-Z][0-9]{4}[A-Z]$")
INDIVIDUAL_PAN_REGEX = re.compile(r"^[A-Z]{3}P[A-Z][0-9]{4}[A-Z]$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def validate_pan(pan: str | None, individual_only: bool = False) -> bool:
    """Validate Permanent Account Number (PAN).
    
    Format: 5 letters, 4 numbers, 1 letter.
    4th character in ABCFGHLJPTK (or strictly 'P' if individual_only=True).
    """
    if not pan:
        return False
    pan = pan.strip().upper()
    if individual_only:
        return bool(INDIVIDUAL_PAN_REGEX.match(pan))
    return bool(GENERAL_PAN_REGEX.match(pan))


def mask_pan(pan: str | None) -> str:
    """Mask PAN as ABC****1F (showing first 3 and last 2 characters)."""
    if not pan:
        return ""
    pan = pan.strip().upper()
    if len(pan) != 10:
        return pan
    return f"{pan[:3]}****{pan[-2:]}"


# Backwards compatibility alias
def mask_ssn(ssn: str | None) -> str:
    if not ssn:
        return ""
    if len(ssn) == 11 and ssn[3] == "-" and ssn[6] == "-":
        return f"***-**-{ssn[-4:]}"
    return mask_pan(ssn)

validate_ssn = validate_pan


def validate_ifsc(code: str | None) -> bool:
    """Validate Indian Financial System Code (IFSC).
    
    Format: 4 uppercase letters, digit 0, 6 alphanumeric characters.
    Regex: ^[A-Z]{4}0[A-Z0-9]{6}$
    """
    if not code:
        return False
    code = code.strip().upper()
    return bool(IFSC_REGEX.match(code))


def age_band_from_dob(
    dob: date | None, fy_end: date | None = None
) -> AgeBand:
    """Determine age band as of financial year end (default: 31 March 2026).
    
    - Below 60 years: BELOW_60
    - 60 to 79 years: SENIOR_60_80
    - 80 years and above: SUPER_SENIOR_80_PLUS
    """
    if dob is None:
        return AgeBand.BELOW_60
    if fy_end is None:
        fy_end = date(2026, 3, 31)

    age = fy_end.year - dob.year - (
        (fy_end.month, fy_end.day) < (dob.month, dob.day)
    )

    if age >= 80:
        return AgeBand.SUPER_SENIOR_80_PLUS
    if age >= 60:
        return AgeBand.SENIOR_60_80
    return AgeBand.BELOW_60
