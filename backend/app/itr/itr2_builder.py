"""ITR-2 Official CBDT JSON Payload Builder for AY 2026-27 (FY 2025-26).

Used for individuals and HUFs having income from Capital Gains, multiple
House Properties, or foreign assets, but no business income.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.schemas.tax import IndianTaxpayerData, Regime, RegimeTaxResult, ResidentialStatus
from app.tax_rules.params import TaxParams
from app.itr.requirements import require_filing_data


class ITR2Builder:
    """Constructs the canonical CBDT ITR-2 JSON document."""

    def build(
        self,
        data: IndianTaxpayerData,
        tax_result: RegimeTaxResult,
        params: TaxParams,
        submission_id: str = "SUB-2026-002",
    ) -> dict[str, Any]:
        """Build the complete ITR-2 dictionary."""
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

        properties = []
        for idx, hp in enumerate(data.house_properties):
            properties.append({
                "PropertyIndex": idx + 1,
                "TypeOfHP": "S" if hp.is_self_occupied else "L",
                "GrossRentReceived": int(hp.annual_lettable_value),
                "MunicipalTaxes": int(hp.municipal_taxes_paid),
                "InterestOnBorrowedCapital": int(hp.interest_on_loan_24b),
            })

        schedule_cg = {
            "ShortTermCapGain": {
                "Sec111A": int(tax_result.income.stcg_111a),
                "OtherSTCG": int(tax_result.income.stcg_slab),
                "TotalSTCG": int(tax_result.income.stcg_111a + tax_result.income.stcg_slab),
            },
            "LongTermCapGain": {
                "Sec112A": {
                    "GrossAmount": int(tax_result.income.ltcg_112a_gross),
                    "Deduction112A": int(tax_result.income.ltcg_112a_exempt),
                    "TaxableAmount": int(tax_result.income.ltcg_112a_taxable),
                },
                "Sec112": int(tax_result.income.ltcg_112),
                "TotalLTCG": int(tax_result.income.ltcg_112a_taxable + tax_result.income.ltcg_112),
            },
            "TotalCapGains": int(tax_result.income.capital_gains_total),
        }

        res_code = "RES"
        if data.residential_status == ResidentialStatus.NON_RESIDENT:
            res_code = "NRI"
        elif data.residential_status == ResidentialStatus.RESIDENT_NOT_ORDINARY:
            res_code = "RNOR"

        opt_out = "Y" if tax_result.regime == Regime.OLD else "N"

        payload = {
            "ITR": {
                "ITR2": {
                    "CreationInfo": {
                        "SWVersionNo": "1.0.0",
                        "SWCreatedBy": "SelfHealingTaxIndia",
                        "JSONCreatedBy": "SelfHealingTaxIndia",
                        "JSONCreationDate": today_str,
                        "IntermediaryCity": data.city,
                        "SubmissionId": submission_id,
                    },
                    "Form_ITR2": {
                        "FormName": "ITR-2",
                        "Description": "For Individuals and HUFs not having income from profits and gains of business or profession",
                        "AssessmentYear": params.assessment_year[:4],
                        "SchemaVer": "Ver1.0",
                        "FormVer": "Ver1.0",
                    },
                    "PartA_GEN": {
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
                    },
                    "ScheduleSalary": {
                        "GrossSalary": int(gross_sal),
                        "DeductionUs16ia": int(tax_result.income.salary_standard_deduction),
                        "ProfessionalTax": int(tax_result.income.salary_professional_tax),
                        "NetSalary": int(tax_result.income.salary_income),
                    },
                    "ScheduleHP": {
                        "Properties": properties,
                        "TotalIncomeHP": int(tax_result.income.house_property_income),
                    },
                    "ScheduleCG": schedule_cg,
                    "ScheduleOS": {
                        "SavingsInterest": int(data.savings_interest),
                        "TotalOtherSources": int(tax_result.income.other_sources_income),
                    },
                    "ScheduleVIA": {
                        "Deductions": {
                            k: int(v) for k, v in tax_result.income.chapter_via.items()
                        },
                        "TotalVIA": int(tax_result.income.chapter_via_total),
                    },
                    "PartB_TI": {
                        "GrossTotalIncome": int(tax_result.income.gross_total_income),
                        "TotalDeductions": int(tax_result.income.chapter_via_total),
                        "TotalIncome": int(tax_result.income.total_income),
                    },
                    "PartB_TTI": {
                        "TaxOnSpecialRates": int(tax_result.tax_on_special_income),
                        "TaxOnNormalRates": int(tax_result.tax_on_slab_income),
                        "GrossTaxPayable": int(tax_result.tax_on_slab_income + tax_result.tax_on_special_income),
                        "Rebate87A": int(tax_result.rebate_87a + tax_result.marginal_relief_87a),
                        "Surcharge": int(tax_result.surcharge),
                        "Cess": int(tax_result.cess),
                        "TotalTaxLiability": int(tax_result.total_tax_liability),
                        "Interest234A": int(tax_result.interest_234a),
                        "Interest234B": int(tax_result.interest_234b),
                        "Interest234C": int(tax_result.interest_234c),
                        "Fee234F": int(tax_result.fee_234f),
                        "TotalPayable": int(
                            tax_result.total_tax_liability
                            + tax_result.interest_234a
                            + tax_result.interest_234b
                            + tax_result.interest_234c
                            + tax_result.fee_234f
                        ),
                        "TaxesPaid": {
                            "AdvanceTax": advance_tax,
                            "TDS": total_tds,
                            "SelfAssessmentTax": sat_tax,
                            "TotalTaxesPaid": int(tax_result.taxes_paid_total),
                        },
                        "BalanceTaxPayable": int(tax_result.tax_payable),
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
