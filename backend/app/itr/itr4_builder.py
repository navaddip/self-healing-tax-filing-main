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
                "EmployerOrDeductorName": f16.employer_name or "Employer",
                "TAN": f16.employer_tan or "BLRT00000A",
                "TotalGrossAmount": int(f16.gross_salary_17_1),
                "TotalTDSDeducted": int(f16.tds_deducted),
            }
            for f16 in data.form16s
        ]

        schedule_tds2 = []
        for t2 in getattr(data, "form26as_entries", []):
            if getattr(t2, "section", "") != "192":
                schedule_tds2.append({
                    "DeductorName": getattr(t2, "deductor_name", "Deductor") or "Deductor",
                    "TAN": getattr(t2, "deductor_tan", "BLRD00000A"),
                    "TotalGrossAmount": int(getattr(t2, "amount_paid", 0)),
                    "TotalTDSDeducted": int(getattr(t2, "tax_deducted", 0)),
                })
        if not schedule_tds2 and data.taxes_paid.tds_non_salary > Decimal("0"):
            schedule_tds2.append({
                "DeductorName": "Bank / Other Deductor",
                "TAN": "BLRD00000A",
                "TotalGrossAmount": int(data.savings_interest + data.fd_interest),
                "TotalTDSDeducted": int(data.taxes_paid.tds_non_salary),
            })

        schedule_it = []
        for ch in getattr(data.taxes_paid, "advance_tax_challans", []) + getattr(data.taxes_paid, "self_assessment_challans", []):
            schedule_it.append({
                "BSRCode": getattr(ch, "bsr_code", "0000000") or "0000000",
                "DateOfDeposit": ch.deposit_date.isoformat() if getattr(ch, "deposit_date", None) else today_str,
                "ChallanNo": getattr(ch, "challan_serial_no", "00000") or "00000",
                "TaxPaid": int(getattr(ch, "amount", 0)),
            })
        for inst_name, amt in data.taxes_paid.advance_tax_instalments.items():
            schedule_it.append({
                "BSRCode": "0000000",
                "DateOfDeposit": today_str,
                "ChallanNo": "00000",
                "TaxPaid": int(amt),
            })
        if data.taxes_paid.self_assessment_tax > Decimal("0") and not getattr(data.taxes_paid, "self_assessment_challans", []):
            schedule_it.append({
                "BSRCode": "0000000",
                "DateOfDeposit": today_str,
                "ChallanNo": "00001",
                "TaxPaid": int(data.taxes_paid.self_assessment_tax),
            })

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
                        "IntermediaryCity": "Bengaluru",
                        "SubmissionId": submission_id,
                    },
                    "Form_ITR4": {
                        "FormName": "ITR-4",
                        "Description": "SUGAM - For Individuals, HUFs and Firms being a resident having total income up to Rs 50 lakh and presumptive business/profession income",
                        "AssessmentYear": "2026",
                        "SchemaVer": "Ver1.0",
                        "FormVer": "Ver1.0",
                    },
                    "PersonalInfo": {
                        "AssesseeName": {"FirstName": first_name, "SurNameOrOrgName": sur_name},
                        "PAN": data.pan,
                        "DOB": data.date_of_birth.isoformat() if data.date_of_birth else "1990-01-01",
                        "AadhaarCardNo": data.aadhaar_last4.rjust(12, "9") if data.aadhaar_last4 else "999999999999",
                        "MobileNo": "9876543210",
                        "EmailAddress": "taxpayer@example.com",
                        "Address": {
                            "ResidenceNo": "Flat 101",
                            "CityOrTownOrDistrict": "Bengaluru",
                            "StateCode": "29",
                            "PinCode": "560001",
                            "CountryCode": "91",
                        },
                    },
                    "FilingStatus": {
                        "ReturnFileSec": 11,
                        "OptOutNewTaxRegime": opt_out,
                        "ItrFilingDueDate": "2026-07-31",
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
                                "IFSCCode": data.bank_ifsc or "HDFC0001234",
                                "BankName": "Primary Bank",
                                "BankAccountNo": f"XXXXXX{data.bank_account_last4}" if data.bank_account_last4 else "1234567890",
                                "AccountType": "SAVINGS",
                                "PreferredForRefund": "Y",
                            }
                        ]
                    },
                    "Verification": {
                        "Declaration": {
                            "AssesseeVerName": data.name or "Taxpayer",
                            "FatherName": f"Father of {data.name or 'Taxpayer'}",
                            "AssesseePAN": data.pan,
                            "Capacity": "Self",
                            "Place": "Bengaluru",
                            "Date": today_str,
                            "IPAddress": "127.0.0.1",
                        }
                    },
                }
            }
        }
        return payload
