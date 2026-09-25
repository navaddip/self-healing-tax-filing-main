"""ITR-4 (SUGAM) Official CBDT JSON Payload Builder for AY 2026-27 (FY 2025-26).

Used for resident individuals, HUFs, and firms (other than LLP) having total income
up to Rs 50 lakh and having presumptive income from business or profession
under Section 44AD, 44ADA, or 44AE.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.schemas.tax import IndianTaxpayerData, Regime, RegimeTaxResult, ResidentialStatus
from app.tax_rules.params import TaxParams
from app.itr.requirements import require_filing_data


class ITR4Builder:
    """Constructs the canonical CBDT ITR-4 JSON document."""

    def build(
        self,
        data: IndianTaxpayerData,
        tax_result: RegimeTaxResult,
        params: TaxParams,
        submission_id: str = "SUB-2026-004",
    ) -> dict[str, Any]:
        """Build the complete ITR-4 dictionary."""
        require_filing_data(data, tax_result, params)
        today_str = date.today().isoformat()
        name_parts = (data.name or "Taxpayer").split()
        first_name = name_parts[0] if name_parts else "Taxpayer"
        sur_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else first_name

        gross_sal = (
            tax_result.income.salary_income
            + tax_result.income.salary_standard_deduction
            + tax_result.income.salary_professional_tax
        )

        schedule_tds1 = [
            {
                "EmployerOrDeductorName": f16.employer_name,
                "TAN": f16.employer_tan,
                "TotalGrossAmount": int(f16.gross_salary_17_1),
                "TotalTDSDeducted": int(f16.tds_deducted),
            }
            for f16 in data.form16s
        ]

        schedule_tds2 = []
        schedule_it = []

        advance_tax = int(sum((getattr(c, "amount", 0) for c in getattr(data.taxes_paid, "advance_tax_challans", [])), Decimal("0")))
        if not advance_tax:
            advance_tax = int(sum(data.taxes_paid.advance_tax_instalments.values(), Decimal("0")))
        sat_tax = int(sum((getattr(c, "amount", 0) for c in getattr(data.taxes_paid, "self_assessment_challans", [])), Decimal("0")))
        if not sat_tax:
            sat_tax = int(data.taxes_paid.self_assessment_tax)
        total_tds = int(data.taxes_paid.tds_salary + data.taxes_paid.tds_non_salary)

        # Presumptive income details
        presumptive_44ada = int(data.presumptive.turnover if data.presumptive else Decimal("0"))
        deemed_44ada = int(tax_result.income.business_income if tax_result and tax_result.income else Decimal("0"))

        res_code = "RES"
        if data.residential_status == ResidentialStatus.NON_RESIDENT:
            res_code = "NRI"
        elif data.residential_status == ResidentialStatus.RESIDENT_NOT_ORDINARY:
            res_code = "RNOR"

        opt_out = "Y" if tax_result.regime == Regime.OLD else "N"

        payload = {
            "ITR": {
                "ITR4": {
                    "CreationInfo": {
                        "SWVersionNo": "1.0.0",
                        "SWCreatedBy": "SelfHealingTaxIndia",
                        "JSONCreatedBy": "SelfHealingTaxIndia",
                        "JSONCreationDate": today_str,
                        "IntermediaryCity": data.city,
                        "SubmissionId": submission_id,
                    },
                    "Form_ITR4": {
                        "FormName": "ITR-4",
                        "Description": "SUGAM - For Individuals, HUFs and Firms being a resident having total income up to Rs 50 lakh and presumptive business/profession income",
                        "AssessmentYear": params.assessment_year[:4],
                        "SchemaVer": "Ver1.0",
                        "FormVer": "Ver1.0",
                    },
                    "PersonalInfo": {
                        "AssesseeName": {"FirstName": first_name, "SurNameOrOrgName": sur_name},
                        "PAN": data.pan,
                        "DOB": data.date_of_birth.isoformat(),
                        "MobileNo": data.mobile,
                        "EmailAddress": data.email,
                        "Address": {
                            "ResidenceNo": data.address,
                            "CityOrTownOrDistrict": data.city,
                            "StateCode": data.state_code,
                            "PinCode": data.pin_code,
                            "CountryCode": "91",
                        },
                    },
                    "FilingStatus": {
                        "ReturnFileSec": 11,
                        "OptOutNewTaxRegime": opt_out,
                        "ItrFilingDueDate": params.filing_due_date.isoformat(),
                        "ResidentialStatus": res_code,
                    },
                    "IncomeDeductions": {
                        "GrossSalary": int(gross_sal),
                        "IncomeFromSal": int(tax_result.income.salary_income),
                        "TotalIncomeOfHP": int(tax_result.income.house_property_income),
                        "ScheduleBP": {
                            "PresumptiveInc44ADA": {
                                "GrossReceipts": presumptive_44ada,
                                "DeemedProfit": deemed_44ada,
                            },
                            "TotalBusinessIncome": int(tax_result.income.business_income),
                        },
                        "IncomeOthSrc": int(tax_result.income.other_sources_income),
                        "GrossTotIncome": int(tax_result.income.gross_total_income),
                        "DeductUndChapVIA": {
                            k: int(v) for k, v in tax_result.income.chapter_via.items()
                        },
                        "TotalChapVIADeductions": int(tax_result.income.chapter_via_total),
                        "TotalIncome": int(tax_result.income.total_income),
                    },
                    "TaxComputation": {
                        "TotalTaxPayable": int(tax_result.tax_on_slab_income + tax_result.tax_on_special_income),
                        "Rebate87A": int(tax_result.rebate_87a + tax_result.marginal_relief_87a),
                        "TaxPayableOnRebate": int(tax_result.tax_after_rebate),
                        "Surcharge": int(tax_result.surcharge),
                        "EducationCess": int(tax_result.cess),
                        "GrossTaxLiability": int(tax_result.total_tax_liability),
                        "Section234A": int(tax_result.interest_234a),
                        "Section234B": int(tax_result.interest_234b),
                        "Section234C": int(tax_result.interest_234c),
                        "Section234F": int(tax_result.fee_234f),
                        "TotalTaxAndIntPayable": int(
                            tax_result.total_tax_liability
                            + tax_result.interest_234a
                            + tax_result.interest_234b
                            + tax_result.interest_234c
                            + tax_result.fee_234f
                        ),
                    },
                    "TaxPaid": {
                        "TaxesPaid": {
                            "AdvanceTax": advance_tax,
                            "TDS": total_tds,
                            "SelfAssessmentTax": sat_tax,
                            "TotalTaxesPaid": int(tax_result.taxes_paid_total),
                        },
                        "BalTaxPayable": int(tax_result.tax_payable),
                        "RefundDue": int(tax_result.refund_due),
                    },
                    "ScheduleTDS1": schedule_tds1,
                    "ScheduleTDS2": schedule_tds2,
                    "ScheduleIT": schedule_it,
                    "BankAccountDtls": {
                        "AddtnlBankDetails": [
                            {
                                "IFSCCode": data.bank_ifsc,
                                "BankName": data.bank_name,
                                "BankAccountNo": data.bank_account_number,
                                "AccountType": data.bank_account_type or "SB",
                                "UseForRefund": "true",
                            }
                        ]
                    },
                    "Verification": {
                        "Declaration": {
                            "AssesseeVerName": data.name or "Taxpayer",
                            "FatherName": data.father_name,
                            "AssesseeVerPAN": data.pan,
                        },
                        "Capacity": data.verification_capacity or "S",
                        "Place": data.verification_place,
                    },
                }
            }
        }
        return payload
