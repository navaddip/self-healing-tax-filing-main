"""Generate 5 synthetic Form 16 test PDFs (FY 2025-26 / AY 2026-27).

Uses the same layout as fill_original_form16.py on top of "original form 16.pdf".
Every figure is computed from the case inputs so each certificate is internally
consistent (Part A totals == Part B tax payable, per FY 2025-26 rules).
"""

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from fill_original_form16 import draw_cell_amount, draw_center, draw_left, draw_right

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PDF = BASE_DIR / "original form 16.pdf"
COLOR = (0.05, 0.1, 0.45)

NEW_SLABS = [(400000, 0.0), (800000, 0.05), (1200000, 0.10), (1600000, 0.15),
             (2000000, 0.20), (2400000, 0.25), (None, 0.30)]
OLD_SLABS = [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (None, 0.30)]


def inr(value: float) -> str:
    """Format as Indian grouping with 2 decimals; negatives in parentheses."""
    neg = value < 0
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    text = f"{whole}.{frac}"
    return f"({text})" if neg else text


def slab_tax(income: float, slabs) -> float:
    tax, lower = 0.0, 0
    for upper, rate in slabs:
        top = income if upper is None else min(income, upper)
        if top > lower:
            tax += (top - lower) * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return round(tax)


@dataclass
class Case:
    slug: str
    new_regime: bool
    cert_no: str
    employer: str
    employer_addr: str
    employee: str
    employee_addr: str
    pan_deductor: str
    tan: str
    pan_employee: str
    emp_ref: str
    cit_street: str
    cit_area: str
    cit_city: str
    cit_pin: str
    receipts: list[str]
    bsr: str
    challan_date: str
    challan_serial: str
    signer: str
    signer_father: str
    designation: str
    designation_short: str
    place: str
    sign_date: str
    salary_17_1: float
    perq_17_2: float = 0.0
    profit_17_3: float = 0.0
    lta: float = 0.0
    gratuity: float = 0.0
    hra: float = 0.0
    prof_tax: float = 0.0
    hp_income: float = 0.0  # negative = loss (interest on housing loan)
    other_sources: float = 0.0
    # (gross, deductible) pairs
    d80c: tuple[float, float] = (0.0, 0.0)
    d80ccd1b: tuple[float, float] = (0.0, 0.0)
    d80d: tuple[float, float] = (0.0, 0.0)
    d80e: tuple[float, float] = (0.0, 0.0)
    d80tta: tuple[float, float] = (0.0, 0.0)
    computed: dict = field(default_factory=dict)

    def compute(self) -> dict:
        c = {}
        c["gross"] = self.salary_17_1 + self.perq_17_2 + self.profit_17_3
        c["exempt"] = self.lta + self.gratuity + self.hra
        c["salary_net"] = c["gross"] - c["exempt"]
        c["std"] = 75000.0 if self.new_regime else 50000.0
        c["sec16"] = c["std"] + self.prof_tax
        c["salaries"] = c["salary_net"] - c["sec16"]
        c["other_total"] = self.hp_income + self.other_sources
        c["gti"] = c["salaries"] + c["other_total"]
        c["via"] = sum(d for _, d in (self.d80c, self.d80ccd1b, self.d80d, self.d80e, self.d80tta))
        c["taxable"] = c["gti"] - c["via"]
        ti = c["taxable"]

        slabs = NEW_SLABS if self.new_regime else OLD_SLABS
        tax = slab_tax(ti, slabs)
        rebate = 0.0
        if self.new_regime:
            if ti <= 1200000:
                rebate = min(tax, 60000)
            elif tax > ti - 1200000:  # marginal relief u/s 87A
                rebate = tax - (ti - 1200000)
        elif ti <= 500000:
            rebate = min(tax, 12500)

        surcharge = 0.0
        if ti > 5000000:
            rate = 0.10 if ti <= 10000000 else 0.15
            surcharge = round(tax * rate)
            base_limit = slab_tax(5000000 if ti <= 10000000 else 10000000, slabs)
            base_limit += 0 if ti <= 10000000 else round(base_limit * 0.10)
            cap = base_limit + (ti - (5000000 if ti <= 10000000 else 10000000))
            if tax + surcharge > cap:  # marginal relief on surcharge
                surcharge = cap - tax

        c["tax"] = float(tax)
        c["rebate"] = float(rebate)
        c["surcharge"] = float(surcharge)
        c["cess"] = float(round((tax - rebate + surcharge) * 0.04))
        c["payable"] = c["tax"] + c["surcharge"] + c["cess"] - c["rebate"]
        self.computed = c
        return c


CASES = [
    Case(
        slug="case1_new_regime_87A_marginal_relief",
        new_regime=True,
        cert_no="INF/BLR/2025-26/118204", employer="INFOSYS LIMITED",
        employer_addr="Electronics City, Hosur Road, Bengaluru - 560100",
        employee="Priya S. Venkatesh",
        employee_addr="Flat 12B, Lake View Apts, HSR Layout, Bengaluru - 560102",
        pan_deductor="AAACI4798L", tan="BLRI01987G", pan_employee="CQVPV7351M", emp_ref="INF-EMP-118204",
        cit_street="Queens Road, Central Revenue Bldg", cit_area="Vasanth Nagar", cit_city="Bengaluru", cit_pin="560001",
        receipts=["310048271936", "310059382047", "310068493158", "310077504269"],
        bsr="0510032", challan_date="07/04/2026", challan_serial="11873",
        signer="Ramesh K. Iyer", signer_father="K. Iyer", designation="Senior Manager - Payroll",
        designation_short="Sr. Mgr - Payroll", place="Bengaluru", sign_date="02/06/2026",
        salary_17_1=1290000,
    ),
    Case(
        slug="case2_old_regime_87A_zero_tax",
        new_regime=False,
        cert_no="WPR/HYD/2025-26/007731", employer="WIPRO LIMITED",
        employer_addr="Gachibowli, Hyderabad - 500032",
        employee="Mohammed Irfan Khan",
        employee_addr="H.No 3-4-512, Barkatpura, Hyderabad - 500027",
        pan_deductor="AAACW0387R", tan="HYDW00412C", pan_employee="DLKPK2290F", emp_ref="WPR-EMP-007731",
        cit_street="IT Towers, AC Guards", cit_area="Masab Tank", cit_city="Hyderabad", cit_pin="500004",
        receipts=["410031928374", "410042039485", "410053140596", "410064251607"],
        bsr="0006341", challan_date="-", challan_serial="-",
        signer="Lakshmi P. Rao", signer_father="P. Rao", designation="Manager - HR Operations",
        designation_short="Mgr - HR Ops", place="Hyderabad", sign_date="28/05/2026",
        salary_17_1=620000, hra=60000, prof_tax=2400,
        d80c=(150000, 150000), d80d=(25000, 25000),
    ),
    Case(
        slug="case3_old_regime_hp_loss_perquisites",
        new_regime=False,
        cert_no="HCL/NOI/2025-26/052288", employer="HCL TECHNOLOGIES LIMITED",
        employer_addr="Plot 3A, Sector 126, Noida - 201304",
        employee="Ankit Sharma",
        employee_addr="C-1104, Supertech Capetown, Sector 74, Noida - 201301",
        pan_deductor="AAACH1645P", tan="DELH08821B", pan_employee="EXRPS6620J", emp_ref="HCL-EMP-052288",
        cit_street="Aayakar Bhawan, Sector 24", cit_area="Noida", cit_city="Noida", cit_pin="201301",
        receipts=["510027384910", "510038495021", "510049506132", "510050617243"],
        bsr="0004329", challan_date="06/05/2026", challan_serial="20417",
        signer="Neha V. Malhotra", signer_father="V. Malhotra", designation="AVP - Finance & Payroll",
        designation_short="AVP - Finance", place="Noida", sign_date="30/05/2026",
        salary_17_1=2280000, perq_17_2=120000, lta=40000, hra=240000, prof_tax=2500,
        hp_income=-200000,
        d80c=(150000, 150000), d80ccd1b=(50000, 50000), d80d=(60000, 50000), d80tta=(8500, 8500),
    ),
    Case(
        slug="case4_new_regime_surcharge_above_50L",
        new_regime=True,
        cert_no="ACN/PUN/2025-26/300145", employer="ACCENTURE SOLUTIONS PVT LTD",
        employer_addr="Magarpatta City, Hadapsar, Pune - 411013",
        employee="Rohan D. Kulkarni",
        employee_addr="Villa 7, Amanora Park Town, Hadapsar, Pune - 411028",
        pan_deductor="AADCA1701E", tan="PNEA09155K", pan_employee="AJNPK4417Q", emp_ref="ACN-EMP-300145",
        cit_street="Aayakar Bhavan, Akurdi", cit_area="Pimpri Chinchwad", cit_city="Pune", cit_pin="411044",
        receipts=["610019283746", "610020394857", "610031405968", "610042516079"],
        bsr="0180002", challan_date="07/05/2026", challan_serial="31552",
        signer="Sanjay M. Deshpande", signer_father="M. Deshpande", designation="Director - Payroll",
        designation_short="Dir - Payroll", place="Pune", sign_date="31/05/2026",
        salary_17_1=5800000, perq_17_2=400000,
    ),
    Case(
        slug="case5_old_regime_deduction_caps_other_income",
        new_regime=False,
        cert_no="ZOH/CHN/2025-26/064417", employer="ZOHO CORPORATION PVT LTD",
        employer_addr="Estancia IT Park, Vallancheri, Chengalpattu - 603202",
        employee="Karthik Subramanian",
        employee_addr="No 18, 2nd Cross St, Velachery, Chennai - 600042",
        pan_deductor="AAACZ3325N", tan="CHEZ02743D", pan_employee="GHTPS5108A", emp_ref="ZOH-EMP-064417",
        cit_street="121, Mahatma Gandhi Road", cit_area="Nungambakkam", cit_city="Chennai", cit_pin="600034",
        receipts=["710083746192", "710094857203", "710005968314", "710016079425"],
        bsr="0240119", challan_date="05/05/2026", challan_serial="04688",
        signer="Divya R. Natarajan", signer_father="R. Natarajan", designation="Head - Payroll & Compliance",
        designation_short="Head - Payroll", place="Chennai", sign_date="29/05/2026",
        salary_17_1=1560000, perq_17_2=60000, lta=45000, hra=180000, prof_tax=2500,
        other_sources=35000,
        d80c=(182000, 150000), d80ccd1b=(50000, 50000), d80d=(42000, 25000),
        d80e=(60000, 60000), d80tta=(14000, 10000),
    ),
]


def render(case: Case, output: Path) -> None:
    c = case.compute()
    tds = c["payable"]
    q_tds = [round(tds / 4, 2)] * 3
    q_tds.append(round(tds - sum(q_tds), 2))
    q_paid = [round(c["gross"] / 4, 2)] * 3
    q_paid.append(round(c["gross"] - sum(q_paid), 2))

    doc = fitz.open(INPUT_PDF)
    kw = dict(fontname="helv", color=COLOR)

    # PAGE 1 --------------------------------------------------------
    p1 = doc[0]
    draw_left(p1, 68, 223.5, case.cert_no, fontsize=8.5, **kw)
    draw_left(p1, 380, 223.5, case.sign_date, fontsize=8.5, **kw)
    draw_left(p1, 68, 263.8, case.employer, fontsize=7.5, **kw)
    draw_left(p1, 68, 271.0, case.employer_addr, fontsize=6.5, **kw)
    draw_left(p1, 284, 263.8, case.employee, fontsize=7.5, **kw)
    draw_left(p1, 284, 271.0, case.employee_addr, fontsize=6.5, **kw)
    draw_center(p1, 105.1, 345.5, case.pan_deductor, fontsize=8.5, **kw)
    draw_center(p1, 213.7, 345.5, case.tan, fontsize=8.5, **kw)
    draw_center(p1, 328.6, 345.5, case.pan_employee, fontsize=8.5, **kw)
    draw_center(p1, 457.7, 345.5, case.emp_ref, fontsize=8.5, **kw)
    draw_left(p1, 110, 374.0, case.cit_street, fontsize=7.5, **kw)
    draw_left(p1, 75, 385.0, case.cit_area, fontsize=7.5, **kw)
    draw_left(p1, 95, 396.0, case.cit_city, fontsize=7.5, **kw)
    draw_left(p1, 115, 407.5, case.cit_pin, fontsize=7.5, **kw)
    draw_center(p1, 328.6, 388.0, "2026-27", fontsize=9, **kw)
    draw_center(p1, 418.9, 388.0, "01/04/2025", fontsize=8, **kw)
    draw_center(p1, 496.1, 388.0, "31/03/2026", fontsize=8, **kw)

    p1.draw_rect(fitz.Rect(59.8, 530.3, 534.8, 565.6), color=None, fill=(1, 1, 1))
    for divider_y in (539.1, 548.0, 556.8):
        p1.draw_line(fitz.Point(59.7, divider_y), fitz.Point(534.9, divider_y), color=(0.7, 0.7, 0.7), width=0.3)
    for vx in (155.1, 276.8, 354.2, 427.5):
        p1.draw_line(fitz.Point(vx, 530.2), fitz.Point(vx, 565.7), color=(0.7, 0.7, 0.7), width=0.3)
    for i, y in enumerate((537.5, 546.0, 554.5, 563.0)):
        draw_center(p1, 107.4, y, f"Q{i + 1}", fontsize=7.5, **kw)
        draw_center(p1, 215.9, y, case.receipts[i], fontsize=7.5, **kw)
        draw_right(p1, 348.2, y, inr(q_paid[i]), fontsize=7.5, **kw)
        draw_right(p1, 421.5, y, inr(q_tds[i]), fontsize=7.5, **kw)
        draw_right(p1, 528.9, y, inr(q_tds[i]), fontsize=7.5, **kw)
    draw_right(p1, 348.2, 575.5, inr(c["gross"]), fontsize=8, **kw)
    draw_right(p1, 421.5, 575.5, inr(tds), fontsize=8, **kw)
    draw_right(p1, 528.9, 575.5, inr(tds), fontsize=8, **kw)

    # PAGE 2 --------------------------------------------------------
    p2 = doc[1]
    if tds > 0:
        draw_center(p2, 72.3, 244.5, "1", fontsize=7.5, **kw)
        draw_right(p2, 206.0, 244.5, inr(tds), fontsize=7.5, **kw)
        draw_center(p2, 261.0, 244.5, case.bsr, fontsize=7.5, **kw)
        draw_center(p2, 360.0, 244.5, case.challan_date, fontsize=7.5, **kw)
        draw_center(p2, 440.0, 244.5, case.challan_serial, fontsize=7.5, **kw)
        draw_center(p2, 502.8, 244.5, "F", fontsize=7.5, **kw)
    draw_right(p2, 206.0, 261.5, inr(tds), fontsize=8, **kw)

    draw_left(p2, 75, 311.0, case.signer, fontsize=7.5, **kw)
    draw_left(p2, 295, 311.0, case.signer_father, fontsize=7.5, **kw)
    draw_left(p2, 60, 324.5, case.designation_short, fontsize=7.0, **kw)
    draw_left(p2, 350, 324.5, inr(tds), fontsize=7.5, **kw)
    draw_left(p2, 135, 382.5, case.place, fontsize=8, **kw)
    draw_left(p2, 135, 400.5, case.sign_date, fontsize=8, **kw)
    draw_left(p2, 135, 428.5, case.designation, fontsize=8, **kw)
    draw_left(p2, 320, 428.5, case.signer, fontsize=8, **kw)

    # Opting out of 115BAC(1A)? YES = old regime
    draw_center(p2, 486.0, 492.0, "NO" if case.new_regime else "YES", fontsize=9, **kw)

    c2_l, c2_r = 332.8, 377.8
    c3_l, c3_r = 377.8, 430.9
    c4_l, c4_r = 430.9, 546.8

    draw_cell_amount(p2, c4_l, c4_r, 514.6, 530.9, 524.5, inr(case.salary_17_1))
    draw_cell_amount(p2, c4_l, c4_r, 530.9, 563.6, 549.0, inr(case.perq_17_2))
    draw_cell_amount(p2, c4_l, c4_r, 563.6, 596.5, 581.5, inr(case.profit_17_3))
    draw_cell_amount(p2, c4_l, c4_r, 596.5, 612.7, 606.5, inr(c["gross"]), fontsize=8.5)
    draw_cell_amount(p2, c4_l, c4_r, 612.7, 636.2, 626.5, inr(0))
    draw_cell_amount(p2, c4_l, c4_r, 652.7, 668.9, 662.5, inr(case.lta))
    draw_cell_amount(p2, c4_l, c4_r, 668.9, 685.2, 678.5, inr(case.gratuity))
    draw_cell_amount(p2, c4_l, c4_r, 724.9, 741.1, 734.5, inr(case.hra))

    # PAGE 3 --------------------------------------------------------
    p3 = doc[2]
    draw_cell_amount(p3, c4_l, c4_r, 154.4, 179.2, 168.0, inr(c["exempt"]), fontsize=8.5)
    draw_cell_amount(p3, c4_l, c4_r, 179.2, 202.8, 191.0, inr(c["salary_net"]), fontsize=8.5)
    draw_cell_amount(p3, c3_l, c3_r, 215.8, 228.7, 224.0, inr(c["std"]))
    draw_cell_amount(p3, c3_l, c3_r, 228.7, 241.7, 237.0, inr(0))
    draw_cell_amount(p3, c3_l, c3_r, 241.7, 254.8, 250.0, inr(case.prof_tax))
    draw_cell_amount(p3, c4_l, c4_r, 254.8, 278.2, 268.0, inr(c["sec16"]), fontsize=8.5)
    draw_cell_amount(p3, c4_l, c4_r, 278.2, 291.2, 286.0, inr(c["salaries"]), fontsize=8.5)
    draw_cell_amount(p3, c3_l, c3_r, 304.2, 327.8, 316.0, inr(case.hp_income))
    draw_cell_amount(p3, c4_l, c4_r, 304.2, 327.8, 316.0, inr(case.hp_income))
    draw_cell_amount(p3, c3_l, c3_r, 327.8, 340.8, 335.5, inr(case.other_sources))
    draw_cell_amount(p3, c4_l, c4_r, 327.8, 340.8, 335.5, inr(case.other_sources))
    draw_cell_amount(p3, c4_l, c4_r, 340.8, 366.9, 354.0, inr(c["other_total"]), fontsize=8.5)
    draw_cell_amount(p3, c4_l, c4_r, 366.9, 380.0, 375.0, inr(c["gti"]), fontsize=8.5)

    for (gross, ded), (y0, y1, base) in (
        (case.d80c, (432.2, 445.3, 440.0)),
        (case.d80c, (549.7, 562.6, 557.5)),  # 10(d) total of 80C/80CCC/80CCD(1)
        (case.d80ccd1b, (575.7, 588.8, 584.0)),
        (case.d80d, (654.1, 667.1, 662.0)),
        (case.d80e, (693.4, 706.4, 701.0)),
    ):
        draw_cell_amount(p3, c3_l, c3_r, y0, y1, base, inr(gross))
        draw_cell_amount(p3, c4_l, c4_r, y0, y1, base, inr(ded))

    # PAGE 4 --------------------------------------------------------
    p4 = doc[3]
    gross, ded = case.d80tta
    draw_cell_amount(p4, c2_l, c2_r, 112.0, 125.0, 120.0, inr(gross))
    draw_cell_amount(p4, c3_l, c3_r, 112.0, 125.0, 120.0, inr(ded))
    draw_cell_amount(p4, c4_l, c4_r, 112.0, 125.0, 120.0, inr(ded))

    draw_cell_amount(p4, c4_l, c4_r, 315.0, 361.6, 338.0, inr(c["via"]), fontsize=8.5)
    draw_cell_amount(p4, c4_l, c4_r, 361.6, 377.9, 371.0, inr(c["taxable"]), fontsize=8.5)
    draw_cell_amount(p4, c4_l, c4_r, 377.9, 394.1, 387.0, inr(c["tax"]))
    draw_cell_amount(p4, c4_l, c4_r, 394.1, 410.3, 403.0, inr(c["rebate"]))
    draw_cell_amount(p4, c4_l, c4_r, 410.3, 426.7, 419.0, inr(c["surcharge"]))
    draw_cell_amount(p4, c4_l, c4_r, 426.7, 440.2, 434.5, inr(c["cess"]))
    draw_cell_amount(p4, c4_l, c4_r, 440.2, 454.5, 448.0, inr(c["payable"]), fontsize=8.5)
    draw_cell_amount(p4, c4_l, c4_r, 467.5, 483.2, 476.0, inr(0))
    draw_cell_amount(p4, c4_l, c4_r, 483.2, 509.3, 496.0, inr(tds), fontsize=8.5)
    draw_cell_amount(p4, c4_l, c4_r, 509.3, 532.3, 521.0, inr(0))
    draw_cell_amount(p4, c4_l, c4_r, 532.3, 545.3, 540.0, inr(c["payable"] - tds), fontsize=8.5)

    draw_left(p4, 82, 575.0, case.signer, fontsize=7.5, **kw)
    draw_left(p4, 280, 575.0, case.signer_father, fontsize=7.5, **kw)
    draw_left(p4, 82, 586.5, case.designation, fontsize=7.0, **kw)
    draw_left(p4, 110, 611.0, case.place, fontsize=8.0, **kw)
    draw_left(p4, 110, 622.0, case.sign_date, fontsize=8.0, **kw)
    draw_left(p4, 358, 622.0, case.signer, fontsize=8.0, **kw)

    doc.save(output)
    doc.close()


def main() -> None:
    for i, case in enumerate(CASES, start=1):
        out = BASE_DIR / f"form16_test_{case.slug}.pdf"
        render(case, out)
        c = case.computed
        print(f"[{i}] {out.name}")
        print(f"    regime={'NEW' if case.new_regime else 'OLD'} gross={inr(c['gross'])} "
              f"taxable={inr(c['taxable'])} tax={inr(c['tax'])} rebate={inr(c['rebate'])} "
              f"surcharge={inr(c['surcharge'])} cess={inr(c['cess'])} payable={inr(c['payable'])}")


if __name__ == "__main__":
    main()
