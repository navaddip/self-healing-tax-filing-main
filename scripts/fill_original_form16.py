"""Fill original form 16.pdf with realistic, rule-compliant synthetic data.

Provides exact column alignments, proper right-alignment of financial amounts,
and clean vertical placement to prevent overlaps with borders and template labels.
"""

from pathlib import Path
import fitz

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PDF = BASE_DIR / "original form 16.pdf"
OUTPUT_PDF = BASE_DIR / "filled_form_16.pdf"


def draw_right(page, x_right, y_baseline, text, fontname="helv", fontsize=8.0, color=(0.05, 0.1, 0.45)):
    """Draw right-aligned text ending precisely at x_right."""
    w = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    page.insert_text((x_right - w, y_baseline), text, fontname=fontname, fontsize=fontsize, color=color)


def draw_center(page, x_center, y_baseline, text, fontname="helv", fontsize=8.0, color=(0.05, 0.1, 0.45)):
    """Draw centered text centered horizontally at x_center."""
    w = fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    page.insert_text((x_center - w / 2.0, y_baseline), text, fontname=fontname, fontsize=fontsize, color=color)


def draw_left(page, x_left, y_baseline, text, fontname="helv", fontsize=8.0, color=(0.05, 0.1, 0.45)):
    """Draw left-aligned text starting at x_left."""
    page.insert_text((x_left, y_baseline), text, fontname=fontname, fontsize=fontsize, color=color)


def draw_cell_amount(page, col_left, col_right, y_top, y_bottom, baseline, text, fontname="helv", fontsize=8.0, color=(0.05, 0.1, 0.45)):
    """Cleanly whiteout pre-printed dots/Rs inside a cell and right-align financial amount with 4pt margin."""
    page.draw_rect(fitz.Rect(col_left + 0.6, y_top + 0.6, col_right - 0.6, y_bottom - 0.6), color=None, fill=(1, 1, 1))
    draw_right(page, col_right - 4.0, baseline, text, fontname=fontname, fontsize=fontsize, color=color)


def fill_form_16():
    doc = fitz.open(INPUT_PDF)

    font_regular = "helv"
    font_bold = "helv"
    text_color = (0.05, 0.1, 0.45)  # Professional dark navy blue print

    # -------------------------------------------------------------
    # PAGE 1: PART A Details & Quarterly TDS Summary
    # -------------------------------------------------------------
    p1 = doc[0]

    # Certificate details in blank row (y0=213.2, y1=229.8)
    draw_left(p1, 68, 223.5, "TCS/MUM/2025-26/049182", fontname=font_regular, fontsize=8.5, color=text_color)
    draw_left(p1, 380, 223.5, "25/05/2026", fontname=font_regular, fontsize=8.5, color=text_color)

    # Employer Details (y0=256.7, y1=273.8)
    draw_left(p1, 68, 263.8, "TATA CONSULTANCY SERVICES LIMITED", fontname=font_bold, fontsize=7.5, color=text_color)
    draw_left(p1, 68, 271.0, "TCS House, Raveline Street, Fort, Mumbai - 400001", fontname=font_regular, fontsize=6.5, color=text_color)

    # Employee Details (y0=256.7, y1=273.8)
    draw_left(p1, 284, 263.8, "Aditya R. Ramanathan", fontname=font_bold, fontsize=7.5, color=text_color)
    draw_left(p1, 284, 271.0, "A-402, Green Glen Layout, Bellandur, Bengaluru - 560103", fontname=font_regular, fontsize=6.5, color=text_color)

    # Tax Identifiers Row (y0=334.7, y1=351.8) - centered in each cell
    draw_center(p1, 105.1, 345.5, "AAACT1948B", fontname=font_bold, fontsize=8.5, color=text_color)
    draw_center(p1, 213.7, 345.5, "MUMB01234E", fontname=font_bold, fontsize=8.5, color=text_color)
    draw_center(p1, 328.6, 345.5, "BNZPR8492K", fontname=font_bold, fontsize=8.5, color=text_color)
    draw_center(p1, 457.7, 345.5, "TCS-EMP-409182", fontname=font_regular, fontsize=8.5, color=text_color)

    # CIT (TDS) & Period with Employer (y0=365.0, y1=429.3)
    draw_left(p1, 110, 374.0, "TCS House, Raveline Street", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_left(p1, 75, 385.0, "Fort", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_left(p1, 95, 396.0, "Mumbai", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_left(p1, 115, 407.5, "400001", fontname=font_regular, fontsize=7.5, color=text_color)

    # Assessment Year
    draw_center(p1, 328.6, 388.0, "2026-27", fontname=font_bold, fontsize=9, color=text_color)
    # Period with Employer (From / To)
    draw_center(p1, 418.9, 388.0, "01/04/2025", fontname=font_regular, fontsize=8, color=text_color)
    draw_center(p1, 496.1, 388.0, "31/03/2026", fontname=font_regular, fontsize=8, color=text_color)

    # Summary Table: Quarters 1 to 4
    # Clean white background for 4 quarters to remove squeezed template text
    p1.draw_rect(fitz.Rect(59.8, 530.3, 534.8, 565.6), color=None, fill=(1, 1, 1))

    quarters_data = [
        ("Q1", "210048192831", "4,50,000.00", "28,605.00", "28,605.00", 537.5),
        ("Q2", "210059281742", "4,50,000.00", "28,605.00", "28,605.00", 546.0),
        ("Q3", "210068391024", "4,50,000.00", "28,605.00", "28,605.00", 554.5),
        ("Q4", "210077492815", "4,50,000.00", "28,605.00", "28,605.00", 563.0),
    ]

    for divider_y in (539.1, 548.0, 556.8):
        p1.draw_line(fitz.Point(59.7, divider_y), fitz.Point(534.9, divider_y), color=(0.7, 0.7, 0.7), width=0.3)
    for vx in (155.1, 276.8, 354.2, 427.5):
        p1.draw_line(fitz.Point(vx, 530.2), fitz.Point(vx, 565.7), color=(0.7, 0.7, 0.7), width=0.3)

    for q, rec, paid, ded, dep, y in quarters_data:
        draw_center(p1, 107.4, y, q, fontname=font_regular, fontsize=7.5, color=text_color)
        draw_center(p1, 215.9, y, rec, fontname=font_regular, fontsize=7.5, color=text_color)
        draw_right(p1, 348.2, y, paid, fontname=font_regular, fontsize=7.5, color=text_color)
        draw_right(p1, 421.5, y, ded, fontname=font_regular, fontsize=7.5, color=text_color)
        draw_right(p1, 528.9, y, dep, fontname=font_regular, fontsize=7.5, color=text_color)

    # Total Summary (y=565.7 to 580.4, baseline 575.5)
    draw_right(p1, 348.2, 575.5, "18,00,000.00", fontname=font_bold, fontsize=8, color=text_color)
    draw_right(p1, 421.5, 575.5, "1,14,420.00", fontname=font_bold, fontsize=8, color=text_color)
    draw_right(p1, 528.9, 575.5, "1,14,420.00", fontname=font_bold, fontsize=8, color=text_color)

    # -------------------------------------------------------------
    # PAGE 2: Part A Challans & Part B Salary / Exemptions
    # -------------------------------------------------------------
    p2 = doc[1]

    # Challan Details Row in Table II (Row 1 is y0=233.6, y1=251.2, baseline 244.5)
    draw_center(p2, 72.3, 244.5, "1", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_right(p2, 206.0, 244.5, "1,14,420.00", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_center(p2, 261.0, 244.5, "0210045", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_center(p2, 360.0, 244.5, "30/04/2026", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_center(p2, 440.0, 244.5, "09241", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_center(p2, 502.8, 244.5, "F", fontname=font_regular, fontsize=7.5, color=text_color)

    # Total Row (y0=251.2, y1=268.1, baseline 261.5)
    draw_right(p2, 206.0, 261.5, "1,14,420.00", fontname=font_bold, fontsize=8, color=text_color)

    # Part A Verification (Lines sit neatly on top of the dots)
    draw_left(p2, 75, 311.0, "Suresh N. Krishnamurthy", fontname=font_bold, fontsize=7.5, color=text_color)
    draw_left(p2, 295, 311.0, "N. Krishnamurthy", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_left(p2, 60, 324.5, "VP - Finance", fontname=font_regular, fontsize=7.0, color=text_color)
    draw_left(p2, 350, 324.5, "1,14,420.00", fontname=font_regular, fontsize=7.5, color=text_color)

    # Place, Date, Designation, Full Name
    draw_left(p2, 135, 382.5, "Mumbai", fontname=font_regular, fontsize=8, color=text_color)
    draw_left(p2, 135, 400.5, "25/05/2026", fontname=font_regular, fontsize=8, color=text_color)
    draw_left(p2, 135, 428.5, "Vice President - Finance", fontname=font_regular, fontsize=8, color=text_color)
    draw_left(p2, 320, 428.5, "Suresh N. Krishnamurthy", fontname=font_bold, fontsize=8, color=text_color)

    # PART B (Annexure-I)
    # Opting out of 115BAC(1A)? [YES/NO] -> YES
    draw_center(p2, 486.0, 492.0, "YES", fontname=font_bold, fontsize=9, color=text_color)

    # Part B Grid Column Boundaries
    c2_l, c2_r = 332.8, 377.8
    c3_l, c3_r = 377.8, 430.9
    c4_l, c4_r = 430.9, 546.8

    # 1. Gross Salary
    # (a) Salary u/s 17(1) (y0=514.6, y1=530.9)
    draw_cell_amount(p2, c4_l, c4_r, 514.6, 530.9, 524.5, "18,00,000.00")
    # (b) Perquisites u/s 17(2) (y0=530.9, y1=563.6)
    draw_cell_amount(p2, c4_l, c4_r, 530.9, 563.6, 549.0, "0.00")
    # (c) Profits in lieu u/s 17(3) (y0=563.6, y1=596.5)
    draw_cell_amount(p2, c4_l, c4_r, 563.6, 596.5, 581.5, "0.00")
    # (d) Total Gross Salary (y0=596.5, y1=612.7)
    draw_cell_amount(p2, c4_l, c4_r, 596.5, 612.7, 606.5, "18,00,000.00", fontsize=8.5)
    # (e) Salary from other employers (y0=612.7, y1=636.2)
    draw_cell_amount(p2, c4_l, c4_r, 612.7, 636.2, 626.5, "0.00")

    # 2. Section 10 Exemptions
    # (a) LTA 10(5) (y0=652.7, y1=668.9)
    draw_cell_amount(p2, c4_l, c4_r, 652.7, 668.9, 662.5, "0.00")
    # (b) Gratuity 10(10) (y0=668.9, y1=685.2)
    draw_cell_amount(p2, c4_l, c4_r, 668.9, 685.2, 678.5, "0.00")
    # (e) HRA u/s 10(13A) (y0=724.9, y1=741.1)
    draw_cell_amount(p2, c4_l, c4_r, 724.9, 741.1, 734.5, "3,00,000.00")

    # -------------------------------------------------------------
    # PAGE 3: Section 10 Total, Section 16 Deductions & Chapter VI-A
    # -------------------------------------------------------------
    p3 = doc[2]

    # 2(i) Total Section 10 exemptions (y0=154.4, y1=179.2)
    draw_cell_amount(p3, c4_l, c4_r, 154.4, 179.2, 168.0, "3,00,000.00", fontsize=8.5)
    # 3. Total salary from current employer [1(d)-2(i)] (y0=179.2, y1=202.8)
    draw_cell_amount(p3, c4_l, c4_r, 179.2, 202.8, 191.0, "15,00,000.00", fontsize=8.5)

    # 4. Deductions under section 16 (in Col 3)
    draw_cell_amount(p3, c3_l, c3_r, 215.8, 228.7, 224.0, "50,000.00")
    draw_cell_amount(p3, c3_l, c3_r, 228.7, 241.7, 237.0, "0.00")
    draw_cell_amount(p3, c3_l, c3_r, 241.7, 254.8, 250.0, "2,400.00")

    # 5. Total Section 16 Deductions (in Col 4, y0=254.8, y1=278.2)
    draw_cell_amount(p3, c4_l, c4_r, 254.8, 278.2, 268.0, "52,400.00", fontsize=8.5)

    # 6. Income chargeable under the head 'Salaries' (y0=278.2, y1=291.2)
    draw_cell_amount(p3, c4_l, c4_r, 278.2, 291.2, 286.0, "14,47,600.00", fontsize=8.5)

    # 7. Other income reported (House property / Other sources)
    # (a) Income (or admissible loss) from house property (y0=304.2, y1=327.8)
    draw_cell_amount(p3, c3_l, c3_r, 304.2, 327.8, 316.0, "(2,00,000.00)")
    draw_cell_amount(p3, c4_l, c4_r, 304.2, 327.8, 316.0, "(2,00,000.00)")

    # (b) Other sources (y0=327.8, y1=340.8)
    draw_cell_amount(p3, c3_l, c3_r, 327.8, 340.8, 335.5, "0.00")
    draw_cell_amount(p3, c4_l, c4_r, 327.8, 340.8, 335.5, "0.00")

    # 8. Total other income (y0=340.8, y1=366.9)
    draw_cell_amount(p3, c4_l, c4_r, 340.8, 366.9, 354.0, "(2,00,000.00)", fontsize=8.5)

    # 9. Gross total income (6+8) (y0=366.9, y1=380.0)
    draw_cell_amount(p3, c4_l, c4_r, 366.9, 380.0, 375.0, "12,47,600.00", fontsize=8.5)

    # 10. Deductions under Chapter VI-A (Headers: Col 3 is Gross Amount, Col 4 is Deductible Amount)
    # (a) Section 80C (Sub-row 1: y0=432.2, y1=445.3)
    draw_cell_amount(p3, c3_l, c3_r, 432.2, 445.3, 440.0, "1,50,000.00")
    draw_cell_amount(p3, c4_l, c4_r, 432.2, 445.3, 440.0, "1,50,000.00")

    # (d) Total deduction 80C, 80CCC, 80CCD(1) (y0=549.7, y1=562.6)
    draw_cell_amount(p3, c3_l, c3_r, 549.7, 562.6, 557.5, "1,50,000.00")
    draw_cell_amount(p3, c4_l, c4_r, 549.7, 562.6, 557.5, "1,50,000.00")

    # (e) Section 80CCD(1B) - NPS Employee Additional (Sub-row 1: y0=575.7, y1=588.8)
    draw_cell_amount(p3, c3_l, c3_r, 575.7, 588.8, 584.0, "50,000.00")
    draw_cell_amount(p3, c4_l, c4_r, 575.7, 588.8, 584.0, "50,000.00")

    # (g) Section 80D - Health Insurance (Sub-row 1: y0=654.1, y1=667.1)
    draw_cell_amount(p3, c3_l, c3_r, 654.1, 667.1, 662.0, "25,000.00")
    draw_cell_amount(p3, c4_l, c4_r, 654.1, 667.1, 662.0, "25,000.00")

    # (h) Section 80E - Higher Education Loan Interest (Sub-row 1: y0=693.4, y1=706.4)
    draw_cell_amount(p3, c3_l, c3_r, 693.4, 706.4, 701.0, "25,000.00")
    draw_cell_amount(p3, c4_l, c4_r, 693.4, 706.4, 701.0, "25,000.00")

    # -------------------------------------------------------------
    # PAGE 4: Total Chapter VI-A, Tax Settlement & Part B Verification
    # -------------------------------------------------------------
    p4 = doc[3]

    # (l) Section 80TTA (Sub-row 1: y0=112.0, y1=125.0)
    draw_cell_amount(p4, c2_l, c2_r, 112.0, 125.0, 120.0, "10,000.00")
    draw_cell_amount(p4, c3_l, c3_r, 112.0, 125.0, 120.0, "10,000.00")
    draw_cell_amount(p4, c4_l, c4_r, 112.0, 125.0, 120.0, "10,000.00")

    # 11. Aggregate of deductible amount under Chapter VI-A (y0=315.0, y1=361.6)
    draw_cell_amount(p4, c4_l, c4_r, 315.0, 361.6, 338.0, "2,60,000.00", fontsize=8.5)

    # 12. Total taxable income (9-11) (y0=361.6, y1=377.9)
    draw_cell_amount(p4, c4_l, c4_r, 361.6, 377.9, 371.0, "9,87,600.00", fontsize=8.5)

    # 13. Tax on total income (y0=377.9, y1=394.1)
    draw_cell_amount(p4, c4_l, c4_r, 377.9, 394.1, 387.0, "1,10,020.00")

    # 14. Rebate under section 87A (y0=394.1, y1=410.3)
    draw_cell_amount(p4, c4_l, c4_r, 394.1, 410.3, 403.0, "0.00")

    # 15. Surcharge (y0=410.3, y1=426.7)
    draw_cell_amount(p4, c4_l, c4_r, 410.3, 426.7, 419.0, "0.00")

    # 16. Health and education cess @ 4% (y0=426.7, y1=440.2)
    draw_cell_amount(p4, c4_l, c4_r, 426.7, 440.2, 434.5, "4,400.00")

    # 17. Tax payable (13+15+16-14) (y0=440.2, y1=454.5)
    draw_cell_amount(p4, c4_l, c4_r, 440.2, 454.5, 448.0, "1,14,420.00", fontsize=8.5)

    # 18. Relief u/s 89 (y0=467.5, y1=483.2)
    draw_cell_amount(p4, c4_l, c4_r, 467.5, 483.2, 476.0, "0.00")

    # 19. Net tax deducted at source (y0=483.2, y1=509.3)
    draw_cell_amount(p4, c4_l, c4_r, 483.2, 509.3, 496.0, "1,14,420.00", fontsize=8.5)

    # 20. Tax collected at source (y0=509.3, y1=532.3)
    draw_cell_amount(p4, c4_l, c4_r, 509.3, 532.3, 521.0, "0.00")

    # 21. Net tax payable (y0=532.3, y1=545.3)
    draw_cell_amount(p4, c4_l, c4_r, 532.3, 545.3, 540.0, "0.00", fontsize=8.5)

    # Verification Block on Page 4 (cleanly placed on dotted lines, above Annexure II)
    draw_left(p4, 82, 575.0, "Suresh N. Krishnamurthy", fontname=font_bold, fontsize=7.5, color=text_color)
    draw_left(p4, 280, 575.0, "N. Krishnamurthy", fontname=font_regular, fontsize=7.5, color=text_color)
    draw_left(p4, 82, 586.5, "Vice President - Finance", fontname=font_regular, fontsize=7.0, color=text_color)
    draw_left(p4, 110, 611.0, "Mumbai", fontname=font_regular, fontsize=8.0, color=text_color)
    draw_left(p4, 110, 622.0, "25/05/2026", fontname=font_regular, fontsize=8.0, color=text_color)
    draw_left(p4, 358, 622.0, "Suresh N. Krishnamurthy", fontname=font_bold, fontsize=8.0, color=text_color)

    # Save to filled_form_16.pdf
    doc.save(OUTPUT_PDF)
    doc.close()
    print(f"Successfully generated filled Form 16 at: {OUTPUT_PDF}")


if __name__ == "__main__":
    fill_form_16()

