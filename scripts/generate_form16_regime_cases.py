"""Generate 10 synthetic Form 16 PDFs covering new- and old-regime recommendations.

All people, PANs and employers are fictional. Each certificate is internally
consistent (Part A TDS == Part B tax payable under the regime the employee chose).
Output: synthetic_form16/NN_<scenario>.pdf
"""

from pathlib import Path

from generate_form16_test_cases import BASE_DIR, Case, inr, render

OUT_DIR = BASE_DIR / "synthetic_form16"


def case(n, slug, new_regime, employee, pan, employer, tan, city, pin, **amounts):
    code = f"SYN{n:02d}"
    return Case(
        slug=f"{n:02d}_{slug}", new_regime=new_regime,
        cert_no=f"{code}/{city[:3].upper()}/2025-26/{100200 + n}", employer=employer,
        employer_addr=f"Plot {10 + n}, Tech Park Road, {city} - {pin}",
        employee=employee, employee_addr=f"Flat {n}0{n}, Sample Residency, {city} - {pin}",
        pan_deductor=f"AABCS{1000 + n}K", tan=tan, pan_employee=pan, emp_ref=f"{code}-EMP-{5000 + n}",
        cit_street="Aayakar Bhawan, Main Road", cit_area="Central Revenue", cit_city=city, cit_pin=pin,
        receipts=[f"8{n:02d}{q}000000{q}" for q in range(1, 5)],
        bsr="0510032", challan_date="07/04/2026", challan_serial=f"{2000 + n}",
        signer="Test Signatory", signer_father="T. Signatory", designation="Payroll Manager",
        designation_short="Payroll Mgr", place=city, sign_date="30/05/2026",
        **amounts,
    )


FULL_DEDUCTIONS = dict(prof_tax=2500, hp_income=-200000,
                       d80c=(150000, 150000), d80ccd1b=(50000, 50000), d80d=(25000, 25000))

CASES = [
    # --- New regime recommended ------------------------------------------------
    case(1, "new_low_income_zero_tax", True, "Anjali M. Rao", "AAKPR1001A",
         "NIMBUS SOFTWORKS PVT LTD", "BLRN10001A", "Bengaluru", "560001",
         salary_17_1=700000),
    case(2, "new_87A_marginal_relief", True, "Vikram S. Nair", "ABKPN1002B",
         "ORBIT ANALYTICS PVT LTD", "KOCO10002B", "Kochi", "682001",
         salary_17_1=1320000),
    case(3, "new_mid_salary_no_deductions", True, "Sneha P. Joshi", "ACKPJ1003C",
         "LUMEN DIGITAL SERVICES LTD", "PNEL10003C", "Pune", "411001",
         salary_17_1=1650000, perq_17_2=150000),
    case(4, "new_salary_plus_other_income", True, "Farhan A. Siddiqui", "ADKPS1004D",
         "CEDAR FINTECH PVT LTD", "HYDC10004D", "Hyderabad", "500001",
         salary_17_1=1500000, other_sources=60000),
    case(5, "new_high_income_surcharge", True, "Meera K. Iyer", "AEKPI1005E",
         "SUMMIT CAPITAL ADVISORS LTD", "MUMS10005E", "Mumbai", "400001",
         salary_17_1=6500000, perq_17_2=1000000),
    case(6, "new_better_but_employer_used_old", False, "Rahul V. Menon", "AFKPM1006F",
         "HARBOR LOGISTICS PVT LTD", "CHEH10006F", "Chennai", "600001",
         salary_17_1=1600000, prof_tax=0, d80c=(150000, 150000)),
    # --- Old regime recommended ------------------------------------------------
    case(7, "old_hra_home_loan_deductions", False, "Pooja R. Kulkarni", "AGKPK1007G",
         "VERTEX ENGINEERING LTD", "PNEV10007G", "Pune", "411014",
         salary_17_1=2000000, hra=360000, lta=40000, **FULL_DEDUCTIONS),
    case(8, "old_mid_salary_home_loan", False, "Arjun T. Reddy", "AHKPR1008H",
         "QUARTZ HEALTHCARE PVT LTD", "HYDQ10008H", "Hyderabad", "500081",
         salary_17_1=1400000, hra=240000, **FULL_DEDUCTIONS),
    case(9, "old_heavy_deductions_30L", False, "Kavya N. Shetty", "AJKPS1009J",
         "BRIDGEWAY CONSULTING LTD", "BLRB10009J", "Bengaluru", "560066",
         salary_17_1=3000000, hra=600000, lta=50000, **FULL_DEDUCTIONS),
    case(10, "old_high_salary_metro_hra", False, "Siddharth G. Kapoor", "AKKPK1010K",
         "MERIDIAN MEDIA NETWORKS LTD", "DELM10010K", "New Delhi", "110001",
         salary_17_1=5000000, hra=1000000, lta=100000, **FULL_DEDUCTIONS),
]


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for c in CASES:
        out = OUT_DIR / f"{c.slug}.pdf"
        render(c, out)
        v = c.computed
        print(f"{out.name:48} employer regime={'NEW' if c.new_regime else 'OLD'} "
              f"taxable={inr(v['taxable'])} TDS={inr(v['payable'])}")


if __name__ == "__main__":
    main()
