"""Generates grounded Indian synthetic taxpayer personas for AY 2026-27 (FY 2025-26).

Implements the 8 distinct test personas specified in Section 7 of INDIA_TAX_MIGRATION.md:
1. Fresher (₹6L)
2. Mid-Career Salaried (₹15L) - Golden Case 1
3. Senior Citizen Pensioner (₹10L)
4. Active Trader (Salary + STCG 111A + LTCG 112A) -> ITR-2
5. Freelance Consultant (44ADA Presumptive) -> ITR-4
6. Multi-Property Landlord -> ITR-2
7. High Earner (₹60L Surcharge)
8. Mid-Year Job Changer (Dual Form 16s)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas.tax import (
    AgeBand,
    CapitalGainItem,
    Form16,
    HouseProperty,
    IndianTaxpayerData,
    PresumptiveBusiness,
    ResidentialStatus,
    SalaryBreakup,
    SourceEvidence,
    TaxesPaid,
)


def synthetic_fresher() -> IndianTaxpayerData:
    """Fresher: Gross ₹6,00,000, 80C ₹50,000. Rebate 87A makes tax ₹0 in both regimes."""
    f16 = Form16(
        employer_name="TCS Innovation Labs",
        employer_tan="BLRT98765A",
        gross_salary_17_1=Decimal("600000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("0"),
    )
    return IndianTaxpayerData(
        name="Aarav Sharma",
        pan="ABCPA1111A",
        bank_ifsc="HDFC0001234",
        bank_account_last4="1001",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        savings_interest=Decimal("8000"),
        deduction_claims={
            "80C": Decimal("50000"),
            "80TTA": Decimal("8000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("0")),
        evidence=[
            SourceEvidence(field_name="gross_salary_17_1", page_number=1, raw_text="600000", confidence=0.99),
            SourceEvidence(field_name="pan", page_number=1, raw_text="ABCPA1111A", confidence=0.99),
        ],
    )


def synthetic_mid_career() -> IndianTaxpayerData:
    """Mid-Career: Gross ₹15L, HRA, 24b ₹2L, 80C ₹1.5L, 80D ₹25k, 80CCD(1B) ₹50k. Old Regime wins."""
    f16 = Form16(
        employer_name="Tech Corp India",
        employer_tan="BLRT12345A",
        gross_salary_17_1=Decimal("1500000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("145000"),
    )
    return IndianTaxpayerData(
        name="Vikram Ramanathan",
        pan="ABCPS1234F",
        bank_ifsc="HDFC0001234",
        bank_account_last4="5678",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        salary_breakup=SalaryBreakup(
            basic=Decimal("900000"),
            hra_received=Decimal("360000"),
            rent_paid_annual=Decimal("290000"),
            landlord_pan="AAABT1234F",
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
        evidence=[
            SourceEvidence(field_name="gross_salary_17_1", page_number=1, raw_text="1500000", confidence=0.99),
            SourceEvidence(field_name="tds_deducted", page_number=1, raw_text="145000", confidence=0.99),
        ],
    )


def synthetic_senior_pensioner() -> IndianTaxpayerData:
    """Senior Citizen: Age 68, Pension ₹8,00,000, FD interest ₹2,00,000, 80TTB ₹50k, 80D ₹50k."""
    f16 = Form16(
        employer_name="State Bank of India (Pension Cell)",
        employer_tan="MUMB00012P",
        gross_salary_17_1=Decimal("800000"),
        professional_tax=Decimal("0"),
        tds_deducted=Decimal("45000"),
    )
    return IndianTaxpayerData(
        name="Ramachandran Iyer",
        pan="ABCPI5555C",
        bank_ifsc="SBIN0001234",
        bank_account_last4="7788",
        date_of_birth=date(1957, 5, 15),
        age_band=AgeBand.SENIOR_60_80,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        fd_interest=Decimal("200000"),
        deduction_claims={
            "80TTB": Decimal("50000"),
            "80D": Decimal("50000"),
        },
        taxes_paid=TaxesPaid(tds_salary=Decimal("45000"), tds_non_salary=Decimal("20000")),
        evidence=[
            SourceEvidence(field_name="gross_salary_17_1", page_number=1, raw_text="800000", confidence=0.99),
            SourceEvidence(field_name="dob", page_number=1, raw_text="1957-05-15", confidence=0.98),
        ],
    )


def synthetic_trader() -> IndianTaxpayerData:
    """Trader: Salary ₹10L + STCG 111A ₹1.5L + LTCG 112A ₹3L. Requires ITR-2."""
    f16 = Form16(
        employer_name="Fintech Solutions Ltd",
        employer_tan="DELF12345A",
        gross_salary_17_1=Decimal("1000000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("60000"),
    )
    return IndianTaxpayerData(
        name="Rohit Verma",
        pan="ABCPV7777D",
        bank_ifsc="ICIC0001234",
        bank_account_last4="9900",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        capital_gains=[
            CapitalGainItem(
                asset_type="listed_equity",
                sale_consideration=Decimal("500000"),
                cost_of_acquisition=Decimal("350000"),
                stt_paid=True,
                gain=Decimal("150000"),
                is_long_term=False,
            ),
            CapitalGainItem(
                asset_type="listed_equity",
                sale_consideration=Decimal("800000"),
                cost_of_acquisition=Decimal("500000"),
                stt_paid=True,
                gain=Decimal("300000"),
                is_long_term=True,
            ),
        ],
        savings_interest=Decimal("12000"),
        deduction_claims={"80C": Decimal("150000")},
        taxes_paid=TaxesPaid(tds_salary=Decimal("60000")),
    )


def synthetic_freelancer_44ada() -> IndianTaxpayerData:
    """Freelance Software Architect: Receipts ₹18L, 50% presumptive profit under 44ADA. Requires ITR-4."""
    return IndianTaxpayerData(
        name="Pooja Kulkarni",
        pan="ABCPK8888E",
        bank_ifsc="KKBK0001234",
        bank_account_last4="4455",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        presumptive=PresumptiveBusiness(
            section="44ADA",
            turnover=Decimal("1800000"),
            declared_profit=Decimal("900000"),
        ),
        savings_interest=Decimal("20000"),
        deduction_claims={"80C": Decimal("150000"), "80D": Decimal("25000")},
        taxes_paid=TaxesPaid(
            tds_non_salary=Decimal("180000"),
            advance_tax_instalments={"Q4": Decimal("30000")},
        ),
    )


def synthetic_landlord_multi_property() -> IndianTaxpayerData:
    """Multi-Property Landlord: 1 self-occupied (24b ₹2L), 1 let-out (rent ₹3.6L). Requires ITR-2."""
    f16 = Form16(
        employer_name="Consulting Group India",
        employer_tan="DELC99887B",
        gross_salary_17_1=Decimal("1800000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("210000"),
    )
    return IndianTaxpayerData(
        name="Ananya Sen",
        pan="ABCPS4444F",
        bank_ifsc="UTIB0001234",
        bank_account_last4="3322",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        house_properties=[
            HouseProperty(
                is_self_occupied=True,
                interest_on_loan_24b=Decimal("200000"),
            ),
            HouseProperty(
                is_self_occupied=False,
                is_let_out=True,
                annual_rent_received=Decimal("360000"),
                municipal_taxes_paid=Decimal("20000"),
                interest_on_loan_24b=Decimal("150000"),
            ),
        ],
        savings_interest=Decimal("25000"),
        deduction_claims={"80C": Decimal("150000"), "80D": Decimal("25000")},
        taxes_paid=TaxesPaid(tds_salary=Decimal("210000")),
    )


def synthetic_high_earner_surcharge() -> IndianTaxpayerData:
    """High Earner: Gross ₹60,00,000. Tests surcharge application (10%) and marginal relief."""
    f16 = Form16(
        employer_name="Global Tech Executive India",
        employer_tan="BLRG11223A",
        gross_salary_17_1=Decimal("6000000"),
        professional_tax=Decimal("2400"),
        tds_deducted=Decimal("1650000"),
    )
    return IndianTaxpayerData(
        name="Deepak Singhal",
        pan="ABCPS9999G",
        bank_ifsc="HDFC0001234",
        bank_account_last4="8899",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16],
        savings_interest=Decimal("80000"),
        deduction_claims={"80C": Decimal("150000"), "80D": Decimal("25000"), "80CCD1B": Decimal("50000")},
        taxes_paid=TaxesPaid(tds_salary=Decimal("1650000")),
    )


def synthetic_job_changer() -> IndianTaxpayerData:
    """Job Changer: Two Form 16s in same financial year (Company A ₹7L, Company B ₹8L)."""
    f16_a = Form16(
        employer_name="Company Alpha Tech",
        employer_tan="BLRA11111A",
        gross_salary_17_1=Decimal("700000"),
        professional_tax=Decimal("1200"),
        tds_deducted=Decimal("35000"),
    )
    f16_b = Form16(
        employer_name="Company Beta Systems",
        employer_tan="BLRB22222B",
        gross_salary_17_1=Decimal("800000"),
        professional_tax=Decimal("1200"),
        tds_deducted=Decimal("55000"),
    )
    return IndianTaxpayerData(
        name="Karan Patel",
        pan="ABCPK3333H",
        bank_ifsc="SBIN0001234",
        bank_account_last4="6677",
        age_band=AgeBand.BELOW_60,
        residential_status=ResidentialStatus.RESIDENT_ORDINARY,
        financial_year="2025-26",
        assessment_year="2026-27",
        form16s=[f16_a, f16_b],
        savings_interest=Decimal("14000"),
        deduction_claims={"80C": Decimal("150000")},
        taxes_paid=TaxesPaid(tds_salary=Decimal("90000")),
    )


PERSONAS = {
    "fresher": synthetic_fresher,
    "mid_career": synthetic_mid_career,
    "senior_pensioner": synthetic_senior_pensioner,
    "trader": synthetic_trader,
    "freelancer_44ada": synthetic_freelancer_44ada,
    "landlord_multi_property": synthetic_landlord_multi_property,
    "high_earner_surcharge": synthetic_high_earner_surcharge,
    "job_changer": synthetic_job_changer,
}


def list_personas() -> list[str]:
    return list(PERSONAS.keys())


def get_persona(name: str) -> IndianTaxpayerData:
    if name not in PERSONAS:
        raise ValueError(f"Unknown persona '{name}'. Available: {', '.join(PERSONAS.keys())}")
    return PERSONAS[name]()


# Backwards-compatibility alias
def synthetic_return(*args, **kwargs) -> IndianTaxpayerData:
    return synthetic_mid_career()


def synthetic_transcript(data: IndianTaxpayerData) -> dict[str, object]:
    tot_sal = sum((f.gross_salary_17_1 for f in data.form16s), Decimal("0"))
    return {
        "pan": data.pan,
        "salary": str(tot_sal),
        "savings_interest": str(data.savings_interest),
        "fd_interest": str(data.fd_interest),
    }
