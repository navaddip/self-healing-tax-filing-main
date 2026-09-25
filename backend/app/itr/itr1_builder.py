"""ITR-1 (SAHAJ) Official CBDT JSON Payload Builder for AY 2026-27 (FY 2025-26).

Produces a JSON payload that validates against the pinned CBDT schema
(`backend/assets/itr_schemas/itr1_schema_ay2026_27.json`). Fields that
must not be synthesised (identity, employer TAN, bank account, dated
challans) are surfaced through :mod:`app.itr.requirements`; if any are
missing this builder never returns — it raises
:class:`SchemaValidationError` naming the exact CBDT paths.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

from app.itr.requirements import require_filing_data
from app.itr.schema_loader import SchemaValidationError
from app.schemas.tax import (
    IndianTaxpayerData,
    Regime,
    RegimeTaxResult,
)
from app.tax_rules.params import TaxParams

# Registered CBDT software id (placeholder in absence of official registration
# — regex `SW\d{8}`; both SWCreatedBy and JSONCreatedBy must satisfy it).
_SW_ID = "SW00000000"
_SW_VERSION = "1.0.0"
_SCHEMA_VER = "Ver1.0"
_FORM_VER = "Ver1.0"


def _split_name(full_name: str) -> tuple[str, str]:
    """CBDT AssesseeName splits into optional FirstName + required SurNameOrOrgName."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return "", full_name.strip()


def _split_hp(data: IndianTaxpayerData):
    """Best-effort break-out of self-occupied vs let-out house property."""
    sop_interest = Decimal("0")
    let_out_total = Decimal("0")
    for hp in data.house_properties:
        if hp.is_self_occupied:
            sop_interest += hp.interest_on_loan_24b
        else:
            let_out_total += (
                hp.annual_rent_received
                - hp.municipal_taxes_paid
                - hp.interest_on_loan_24b
            )
    return sop_interest, let_out_total


def _compute_digest(payload: dict) -> str:
    """44-char base64(SHA-256) of the payload with Digest replaced by '-'.

    Satisfies CreationInfo.Digest pattern `-|.{44}`.
    """
    payload_copy = json.loads(json.dumps(payload))
    payload_copy["ITR"]["ITR1"]["CreationInfo"]["Digest"] = "-"
    canonical = json.dumps(payload_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(hashlib.sha256(canonical).digest()).decode("ascii")


def _chapter_via_block(chapter_via: dict[str, Decimal], total: Decimal, include_optional: bool = False) -> dict[str, int]:
    """DeductUndChapVIAType requires all sections zero-filled; UsrDeductUndChapVIAType
    is nearly identical (Section80EEA/EEB optional there). We fill all keys
    with the value from ``chapter_via`` or zero — deductions the taxpayer did
    not claim must be present as 0.
    """
    keys = [
        "Section80C", "Section80CCC", "Section80CCDEmployeeOrSE", "Section80CCD1B",
        "Section80CCDEmployer", "Section80D", "Section80DD", "Section80DDB",
        "Section80E", "Section80EE", "Section80EEA", "Section80EEB",
        "Section80G", "Section80GG", "Section80GGA", "Section80GGC",
        "Section80TTA", "Section80TTB", "Section80U", "AnyOthSec80CCH",
    ]
    block = {k: int(chapter_via.get(k, Decimal("0"))) for k in keys}
    block["TotalChapVIADeductions"] = int(total)
    return block


class ITR1Builder:
    """Constructs a schema-valid CBDT ITR-1 JSON document."""

    def build(
        self,
        data: IndianTaxpayerData,
        tax_result: RegimeTaxResult,
        params: TaxParams,
        submission_id: str = "SUB-2026-001",
    ) -> dict[str, Any]:
        require_filing_data(data, tax_result, params)

        today_str = date.today().isoformat()
        first_name, sur_name = _split_name(data.name)

        # PinCode / mobile must be integers per schema
        try:
            pin_code_int = int(data.pin_code)
            mobile_int = int(data.mobile)
            country_code_mobile_int = int(data.country_code_mobile)
        except (TypeError, ValueError) as exc:
            raise SchemaValidationError(
                "ITR export blocked: numeric field could not be coerced "
                f"({exc}). Expected digits in pin_code, mobile, country_code_mobile."
            ) from exc

        # Salary aggregation
        gross_sal_1 = sum((f.gross_salary_17_1 for f in data.form16s), Decimal("0"))
        perks_17_2 = sum((f.perquisites_17_2 for f in data.form16s), Decimal("0"))
        profits_17_3 = sum((f.profits_in_lieu_17_3 for f in data.form16s), Decimal("0"))
        gross_salary = gross_sal_1 + perks_17_2 + profits_17_3
        std_ded = tax_result.income.salary_standard_deduction
        prof_tax = tax_result.income.salary_professional_tax
        deduction_us_16 = int(std_ded + prof_tax)
        net_salary = int(gross_salary - Decimal("0"))  # after Sec10 exemptions (none itemised here)
        income_from_sal = int(tax_result.income.salary_income)

        gti = int(tax_result.income.gross_total_income)
        ltcg_112a_taxable = int(tax_result.income.ltcg_112a_taxable)
        gti_inc_ltcg = gti + ltcg_112a_taxable  # GrossTotIncomeIncLTCG112A

        total_income = int(tax_result.income.total_income)

        # TDS on salaries (Schedule TDS1 in ITR-1 = TDSonSalaries)
        tds_on_salary_items = []
        total_tds_sal = 0
        for f16 in data.form16s:
            item_tds = int(f16.tds_deducted)
            total_tds_sal += item_tds
            tds_on_salary_items.append({
                "EmployerOrDeductorOrCollectDetl": {
                    "TAN": f16.employer_tan,
                    "EmployerOrDeductorOrCollecterName": f16.employer_name,
                },
                "IncChrgSal": int(f16.gross_salary_17_1),
                "TotalTDSSal": item_tds,
            })

        # Tax paid components
        total_tds = int(data.taxes_paid.tds_salary + data.taxes_paid.tds_non_salary)
        tcs = int(data.taxes_paid.tcs)
        advance_tax = int(sum(data.taxes_paid.advance_tax_instalments.values(), Decimal("0")))
        sat_tax = int(data.taxes_paid.self_assessment_tax)
        total_taxes_paid = advance_tax + total_tds + tcs + sat_tax

        # Reconciliation: total_taxes_paid must equal component sum (business rule)
        computed_paid_total = int(tax_result.taxes_paid_total)
        if computed_paid_total != total_taxes_paid:
            raise SchemaValidationError(
                "ITR export blocked: TaxesPaid.TotalTaxesPaid mismatch — "
                f"components sum to {total_taxes_paid} but engine reports {computed_paid_total}"
            )

        gross_tax_liability = int(tax_result.total_tax_liability)
        section_89 = int(getattr(tax_result, "relief_89", 0) or 0)
        net_tax_liability = max(0, gross_tax_liability - section_89)
        total_interest = int(
            tax_result.interest_234a + tax_result.interest_234b + tax_result.interest_234c
        )
        tot_tax_plus_interest = net_tax_liability + total_interest + int(tax_result.fee_234f)
        bal_tax_payable = max(0, tot_tax_plus_interest - total_taxes_paid)
        refund_due = max(0, total_taxes_paid - tot_tax_plus_interest)

        # Business validation: total income = GTI (+LTCG112A netted for computation only) - VIA
        via_total = int(tax_result.income.chapter_via_total)
        expected_total_income = gti - via_total
        if total_income != expected_total_income:
            raise SchemaValidationError(
                "ITR export blocked: TotalIncome mismatch — "
                f"expected GrossTotIncome({gti}) - ChapterVIA({via_total}) = {expected_total_income}, "
                f"engine reports {total_income}"
            )

        # AssessmentYear pattern is exactly 4 chars (e.g. '2026' for AY 2026-27)
        ay_short = params.assessment_year[:4]

        payload: dict[str, Any] = {
            "ITR": {
                "ITR1": {
                    "CreationInfo": {
                        "SWVersionNo": _SW_VERSION,
                        "SWCreatedBy": _SW_ID,
                        "JSONCreatedBy": _SW_ID,
                        "JSONCreationDate": today_str,
                        "IntermediaryCity": (data.city or "NA")[:25],
                        "Digest": "-",  # replaced below
                    },
                    "Form_ITR1": {
                        "FormName": "ITR-1",
                        "Description": (
                            "For Individuals being a resident (other than not ordinarily "
                            "resident) having total income up to Rs 50 lakh"
                        )[:75],
                        "AssessmentYear": ay_short,
                        "SchemaVer": _SCHEMA_VER,
                        "FormVer": _FORM_VER,
                    },
                    "PersonalInfo": {
                        "AssesseeName": {
                            **({"FirstName": first_name} if first_name else {}),
                            "SurNameOrOrgName": sur_name,
                        },
                        "PAN": data.pan,
                        "Address": {
                            "ResidenceNo": data.address[:50],
                            "LocalityOrArea": data.locality_or_area[:50],
                            "CityOrTownOrDistrict": data.city[:50],
                            "StateCode": data.state_code,
                            "CountryCode": "91",
                            "PinCode": pin_code_int,
                            "CountryCodeMobile": country_code_mobile_int,
                            "MobileNo": mobile_int,
                            "EmailAddress": data.email,
                        },
                        "SecondaryAdd": "N",
                        "DOB": data.date_of_birth.isoformat(),
                        "EmployerCategory": data.employer_category,
                    },
                    "FilingStatus": {
                        "ReturnFileSec": 11,  # 139(1) on or before due date
                        "OptOutNewTaxRegime": "Y" if tax_result.regime == Regime.OLD else "N",
                        "AsseseeRepFlg": "N",
                        "ItrFilingDueDate": params.filing_due_date.isoformat(),
                    },
                    "ITR1_IncomeDeductions": {
                        "GrossSalary": int(gross_salary),
                        "NetSalary": net_salary,
                        "DeductionUs16": deduction_us_16,
                        "DeductionUs16ia": int(std_ded),
                        "ProfessionalTaxUs16iii": int(prof_tax),
                        "IncomeFromSal": income_from_sal,
                        "IncomeOthSrc": int(tax_result.income.other_sources_income),
                        "GrossTotIncome": gti,
                        "GrossTotIncomeIncLTCG112A": gti_inc_ltcg,
                        "UsrDeductUndChapVIA": _chapter_via_block(
                            tax_result.income.chapter_via, tax_result.income.chapter_via_total
                        ),
                        "DeductUndChapVIA": _chapter_via_block(
                            tax_result.income.chapter_via, tax_result.income.chapter_via_total
                        ),
                        "TotalIncome": total_income,
                    },
                    "ITR1_TaxComputation": {
                        "TotalTaxPayable": int(
                            tax_result.tax_on_slab_income + tax_result.tax_on_special_income
                        ),
                        "Rebate87A": int(tax_result.rebate_87a + tax_result.marginal_relief_87a),
                        "TaxPayableOnRebate": int(tax_result.tax_after_rebate),
                        "EducationCess": int(tax_result.cess),
                        "GrossTaxLiability": gross_tax_liability,
                        "Section89": section_89,
                        "NetTaxLiability": net_tax_liability,
                        "TotalIntrstPay": total_interest,
                        "IntrstPay": {
                            "IntrstPayUs234A": int(tax_result.interest_234a),
                            "IntrstPayUs234B": int(tax_result.interest_234b),
                            "IntrstPayUs234C": int(tax_result.interest_234c),
                            "LateFilingFee234F": int(tax_result.fee_234f),
                        },
                        "TotTaxPlusIntrstPay": tot_tax_plus_interest,
                    },
                    "TaxPaid": {
                        "TaxesPaid": {
                            "AdvanceTax": advance_tax,
                            "TDS": total_tds,
                            "TCS": tcs,
                            "SelfAssessmentTax": sat_tax,
                            "TotalTaxesPaid": total_taxes_paid,
                        },
                        "BalTaxPayable": bal_tax_payable,
                    },
                    "Refund": {
                        "RefundDue": refund_due,
                        "BankAccountDtls": {
                            "AddtnlBankDetails": [
                                {
                                    "IFSCCode": data.bank_ifsc,
                                    "BankName": data.bank_name,
                                    "BankAccountNo": data.bank_account_number,
                                    "AccountType": data.bank_account_type,
                                    "UseForRefund": "true",
                                }
                            ]
                        },
                    },
                    "TDSonSalaries": {
                        "TDSonSalary": tds_on_salary_items,
                        "TotalTDSonSalaries": total_tds_sal,
                    },
                    "Verification": {
                        "Declaration": {
                            "AssesseeVerName": data.name,
                            "FatherName": data.father_name,
                            "AssesseeVerPAN": data.pan,
                        },
                        "Capacity": data.verification_capacity,
                        "Place": data.verification_place[:50],
                    },
                }
            }
        }

        # Compute and set the Digest last, over the exact payload minus Digest.
        payload["ITR"]["ITR1"]["CreationInfo"]["Digest"] = _compute_digest(payload)
        return payload
