"""Fail-safe filing pre-checks.

Every field required by the pinned CBDT schema must be present or the
caller receives a SchemaValidationError listing exact missing paths.
Filing identity is supplied by the taxpayer, never synthesized.
"""
from __future__ import annotations

from app.itr.schema_loader import MissingFilingData, SchemaValidationError

# CBDT enum values (subset used at pre-check time)
# PE/PESG/PEPS/PEO are pensioner categories; private-sector employees use OTH.
_EMPLOYER_CATEGORIES = {"CGOV", "SGOV", "PSU", "PE", "PESG", "PEPS", "PEO", "OTH", "NA"}
_BANK_ACCOUNT_TYPES = {"SB", "CA", "CC", "OD", "NRO", "OTH"}
_CAPACITY = {"S", "R"}

# Details a Form 16 never carries: taxpayer field -> ITR schema path
TAXPAYER_FIELDS = {
    "date_of_birth": "PersonalInfo.DOB",
    "employer_category": "PersonalInfo.EmployerCategory",
    "address": "PersonalInfo.Address.ResidenceNo",
    "locality_or_area": "PersonalInfo.Address.LocalityOrArea",
    "city": "PersonalInfo.Address.CityOrTownOrDistrict",
    "state_code": "PersonalInfo.Address.StateCode",
    "pin_code": "PersonalInfo.Address.PinCode",
    "mobile": "PersonalInfo.Address.MobileNo",
    "email": "PersonalInfo.Address.EmailAddress",
    "bank_ifsc": "Refund.BankAccountDtls.IFSCCode",
    "bank_name": "Refund.BankAccountDtls.BankName",
    "bank_account_number": "Refund.BankAccountDtls.BankAccountNo",
    "father_name": "Verification.Declaration.FatherName",
    "verification_place": "Verification.Place",
}


def missing_taxpayer_fields(data) -> list[str]:
    """Taxpayer-supplied details still empty; works on the model or its JSON dict."""
    get = data.get if isinstance(data, dict) else lambda key: getattr(data, key, None)
    return [key for key in TAXPAYER_FIELDS if not get(key)]


def require_filing_data(data, tax_result, params):
    """Raise SchemaValidationError with exact missing schema paths.

    The message begins with 'ITR export blocked:'. When the only gaps are
    taxpayer-supplied details, MissingFilingData carries their field keys.
    """
    missing_fields = missing_taxpayer_fields(data)
    missing: list[str] = [TAXPAYER_FIELDS[key] for key in missing_fields]

    for path, value in {
        "PersonalInfo.AssesseeName": data.name,
        "PersonalInfo.PAN": data.pan,
        "PersonalInfo.Address.CountryCodeMobile": data.country_code_mobile,
    }.items():
        if not value:
            missing.append(path)

    if data.employer_category and data.employer_category not in _EMPLOYER_CATEGORIES:
        missing.append(
            f"PersonalInfo.EmployerCategory must be one of {sorted(_EMPLOYER_CATEGORIES)}"
        )
    if data.bank_account_type and data.bank_account_type not in _BANK_ACCOUNT_TYPES:
        missing.append(
            f"Refund.BankAccountDtls.AccountType must be one of {sorted(_BANK_ACCOUNT_TYPES)}"
        )
    if data.verification_capacity and data.verification_capacity not in _CAPACITY:
        missing.append(f"Verification.Capacity must be one of {sorted(_CAPACITY)}")

    # Salary deductor
    for i, form in enumerate(data.form16s):
        if not form.employer_name:
            missing.append(f"TDSonSalaries.TDSonSalary[{i}].EmployerName")
        if not form.employer_tan:
            missing.append(f"TDSonSalaries.TDSonSalary[{i}].TAN")

    # Non-salary TDS and challans require dated evidence we do not synthesise.
    if data.taxes_paid.tds_non_salary:
        missing.append(
            "TDSonOthThanSals: itemised non-salary TDS certificates required (unsupported export)"
        )
    if data.taxes_paid.advance_tax_instalments or data.taxes_paid.self_assessment_tax:
        missing.append(
            "TaxPayments.TaxPayment: dated challan (BSRCode, DateDep, SrlNoOfChaln, Amt) required (unsupported export)"
        )

    if missing:
        message = "ITR export blocked: " + "; ".join(missing)
        if len(missing) == len(missing_fields):
            raise MissingFilingData(message, missing_fields)
        raise SchemaValidationError(message)
    if tax_result is None:
        raise SchemaValidationError("ITR export blocked: missing verified regime calculation")
    if not params.verified or data.assessment_year != params.assessment_year:
        raise SchemaValidationError(
            "ITR export blocked: unverified rule pack or inconsistent assessment year"
        )
