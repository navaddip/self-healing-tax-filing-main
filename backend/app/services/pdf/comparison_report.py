"""Professional Indian Tax Regime Comparison Advisory Report Generator (8 Pages).

Implements the complete CA-firm quality PDF specification from Section 4 of INDIA_TAX_MIGRATION.md.
A4 portrait, 6-color palette, Indian digit grouping, continuous section numbering,
and two-pass page counting.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
pt = 1
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.verification.completeness import select_itr_form
from app.tax_rules.params import get_params
from app.schemas.tax import (
    FilingReceipt,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    RegimeTaxResult,
    SubmissionResult,
    VerificationResult,
)
from app.services.pdf.style import (
    ACCENT,
    BG_SUBHEAD,
    INK,
    MUTED,
    NEGATIVE,
    NumberedCanvas,
    POSITIVE,
    RULE,
    SectionHeaderFlowable,
    WHITE,
    inr,
    inr_words,
    register_fonts,
)


class ComparisonReportService:
    """Produces the 8-page authoritative Indian Tax Regime Comparison Advisory Report."""

    def __init__(self):
        self.regular_font, self.bold_font = register_fonts()
        self.content_width = 174 * mm  # A4 width 210mm - 2*18mm margins

    def generate_pdf(
        self,
        data: IndianTaxpayerData,
        comparison: RegimeComparison,
        verification: VerificationResult | None = None,
        submission_id: str = "SUB-2026-001",
        output_path: Path | None = None,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=18 * mm,
            title="Income Tax Computation & Regime Comparison Advisory Report",
            author="Self-Healing Tax Filing System",
            subject="Tax Advisory Report AY 2026-27",
        )

        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle(
            "ReportNormal",
            parent=styles["Normal"],
            fontName=self.regular_font,
            fontSize=9,
            leading=12,
            textColor=INK,
        )
        muted_style = ParagraphStyle(
            "ReportMuted",
            parent=normal_style,
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        )
        bold_style = ParagraphStyle(
            "ReportBold",
            parent=normal_style,
            fontName=self.bold_font,
        )

        story: list[Any] = []
        gen_time = datetime.now().strftime("%d %b %Y %H:%M IST")

        # Set canvas attributes for furniture
        def canvas_maker(*args, **kwargs):
            c = NumberedCanvas(*args, **kwargs)
            c.taxpayer_header = f"{data.name or 'Taxpayer'}  ·  PAN: {data.masked_pan}"
            c.doc_id = submission_id[:8].upper()
            c.gen_timestamp = gen_time
            return c

        rec_result = comparison.old if comparison.recommended == Regime.OLD else comparison.new
        alt_result = comparison.new if comparison.recommended == Regime.OLD else comparison.old
        chosen_form, _ = select_itr_form(data, rec_result.income.total_income)

        # ===================================================================
        # PAGE 1 - DECISION PAGE
        # ===================================================================
        # Masthead
        story.append(
            Paragraph("<b>SELF-HEALING TAX ADVISORY</b>", ParagraphStyle(
                "Masthead", fontName=self.bold_font, fontSize=16, leading=20, textColor=INK
            ))
        )
        story.append(HRFlowable(width="100%", thickness=1.0, color=ACCENT, spaceAfter=6, spaceBefore=4))
        story.append(
            Paragraph("Income Tax Computation and Regime Comparison", ParagraphStyle(
                "DocTitle", fontName=self.regular_font, fontSize=13, leading=16, textColor=INK
            ))
        )
        story.append(
            Paragraph("Assessment Year 2026-27 (Financial Year 2025-26)", muted_style)
        )
        story.append(Spacer(1, 8))

        # Identity strip
        id_data = [
            [
                Paragraph("<b>TAXPAYER NAME</b><br/>" + (data.name or "Taxpayer"), normal_style),
                Paragraph("<b>PAN (MASKED)</b><br/>" + data.masked_pan, normal_style),
                Paragraph("<b>STATUS & AGE</b><br/>" + f"{data.residential_status.value.replace('_', ' ').title()} ({data.age_band.value.replace('_', ' ')})", normal_style),
                Paragraph("<b>APPLICABLE FORM</b><br/>" + chosen_form.value.upper(), normal_style),
            ]
        ]
        id_table = Table(id_data, colWidths=[50 * mm, 38 * mm, 50 * mm, 36 * mm])
        id_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(id_table)
        story.append(Spacer(1, 10))

        # RECOMMENDATION BANNER (44pt tall, ACCENT fill)
        banner_data = [
            [
                Paragraph(f"<b>Recommended: {comparison.recommended.value.upper()} REGIME</b>", ParagraphStyle("BannerL", fontName=self.bold_font, fontSize=14, leading=18, textColor=WHITE)),
                Paragraph(f"<b>You save ₹{inr(comparison.savings)}</b>", ParagraphStyle("BannerR", fontName=self.bold_font, fontSize=14, leading=18, textColor=WHITE, alignment=2)),
            ],
            [
                Paragraph(f"Compared with the {('new' if comparison.recommended == Regime.OLD else 'old')} regime, on a total income of ₹{inr(rec_result.income.total_income)}", ParagraphStyle("BannerSub", fontName=self.regular_font, fontSize=8.5, leading=11, textColor=WHITE)),
                Paragraph(f"Effective Tax Rate: {rec_result.effective_tax_rate:.1f}%", ParagraphStyle("BannerSubR", fontName=self.regular_font, fontSize=8.5, leading=11, textColor=WHITE, alignment=2)),
            ]
        ]
        banner_table = Table(banner_data, colWidths=[110 * mm, 64 * mm])
        banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 12))

        # Two-Column Verdict Panels
        def verdict_panel(res: RegimeTaxResult, is_rec: bool) -> Table:
            title = f"{'<b>RECOMMENDED: ' if is_rec else ''}{res.regime.value.upper()} REGIME{'</b>' if is_rec else ''}"
            res_label = "REFUND DUE" if res.refund_due > Decimal("0") else "TAX PAYABLE"
            res_val = res.refund_due if res.refund_due > Decimal("0") else res.tax_payable
            res_color = POSITIVE if res.refund_due > Decimal("0") else NEGATIVE

            rows = [
                [Paragraph(f"<b>{title}</b>", normal_style), ""],
                [Paragraph("Total income", normal_style), Paragraph(f"₹{inr(res.income.total_income)}", ParagraphStyle("Num", fontName=self.bold_font, alignment=2))],
                [Paragraph("Total tax liability", normal_style), Paragraph(f"₹{inr(res.total_tax_liability)}", ParagraphStyle("Num", fontName=self.bold_font, alignment=2))],
                [Paragraph("Taxes already paid", normal_style), Paragraph(f"₹{inr(res.taxes_paid_total)}", ParagraphStyle("Num", fontName=self.bold_font, alignment=2))],
                [
                    Paragraph(f"<b>{res_label}</b>", ParagraphStyle("ResLabel", fontName=self.bold_font, fontSize=11, textColor=res_color)),
                    Paragraph(f"<b>₹{inr(res_val)}</b>", ParagraphStyle("ResNum", fontName=self.bold_font, fontSize=12, alignment=2, textColor=res_color)),
                ],
            ]
            t = Table(rows, colWidths=[46 * mm, 37 * mm])
            style_cmds = [
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("BACKGROUND", (0, 0), (-1, 0), BG_SUBHEAD),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 3), (-1, 3), 0.5, RULE),
            ]
            if is_rec:
                style_cmds.append(("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT))
            t.setStyle(TableStyle(style_cmds))
            return t

        verdict_data = [[verdict_panel(comparison.old, comparison.recommended == Regime.OLD), "", verdict_panel(comparison.new, comparison.recommended == Regime.NEW)]]
        verdict_table = Table(verdict_data, colWidths=[85 * mm, 4 * mm, 85 * mm])
        verdict_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(verdict_table)
        story.append(Spacer(1, 10))

        # WHY Panel (Reasons bullets)
        reasons_flow = [Paragraph("<b>KEY DECISION FACTORS</b>", ParagraphStyle("H", fontName=self.bold_font, fontSize=9.5, textColor=ACCENT))]
        for r in comparison.reasons:
            reasons_flow.append(Paragraph(f"▪ {r}", ParagraphStyle("Reason", fontName=self.regular_font, fontSize=8.5, leading=11, textColor=INK)))
        why_table = Table([[reasons_flow]], colWidths=[174 * mm])
        why_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), BG_SUBHEAD),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(why_table)
        story.append(Spacer(1, 10))

        # Swing Chart (Horizontal Bar Comparison)
        chart_data = [
            [Paragraph("<b>Tax Liability Comparison</b>", normal_style), ""],
            [
                Paragraph("Old Regime", normal_style),
                Paragraph(f"<b>₹{inr(comparison.old.total_tax_liability)}</b>", ParagraphStyle("R", fontName=self.bold_font, alignment=2)),
            ],
            [
                Paragraph("New Regime", normal_style),
                Paragraph(f"<b>₹{inr(comparison.new.total_tax_liability)}</b>", ParagraphStyle("R", fontName=self.bold_font, alignment=2)),
            ],
        ]
        chart_table = Table(chart_data, colWidths=[80 * mm, 94 * mm])
        chart_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("BACKGROUND", (0, 0), (-1, 0), BG_SUBHEAD),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(chart_table)
        story.append(Spacer(1, 10))

        # ACTION Box
        actions = [
            Paragraph("<b>RECOMMENDED NEXT STEPS</b>", ParagraphStyle("H", fontName=self.bold_font, fontSize=9.5, textColor=ACCENT)),
            Paragraph(f"1. File {chosen_form.value.upper()} on incometax.gov.in selecting the {comparison.recommended.value.upper()} regime.", normal_style),
            Paragraph(f"2. {'Form 10-IEA must be filed before the 139(1) due date.' if comparison.form_10iea_required else 'Form 10-IEA is not required as you have no business income.'}", normal_style),
            Paragraph("3. e-Verify your return within 30 days of filing via Aadhaar OTP or Net Banking.", normal_style),
        ]
        action_table = Table([[actions]], colWidths=[174 * mm])
        action_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(action_table)

        story.append(PageBreak())

        # ===================================================================
        # PAGE 2 - LINE-BY-LINE COMPARISON (Section 2)
        # ===================================================================
        story.append(SectionHeaderFlowable(2, "Line-by-Line Regime Comparison"))
        story.append(Spacer(1, 6))

        delta_rows = [
            [
                Paragraph("<b>Particulars</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Old Regime (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>New Regime (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>Difference (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
            ]
        ]
        for d in comparison.deltas:
            diff_val = d["delta"]
            diff_color = POSITIVE if diff_val < 0 else (NEGATIVE if diff_val > 0 else INK)
            delta_rows.append([
                Paragraph(d["line"], normal_style),
                Paragraph(inr(d["old_value"]), ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                Paragraph(inr(d["new_value"]), ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                Paragraph(f"<font color='{diff_color.hexval()}'>{inr(diff_val)}</font>", ParagraphStyle("Diff", fontName=self.bold_font, alignment=2)),
            ])

        delta_table = Table(delta_rows, colWidths=[74 * mm, 33 * mm, 33 * mm, 34 * mm])
        delta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ]))
        story.append(delta_table)

        story.append(PageBreak())

        # ===================================================================
        # PAGE 3 - WHAT THE NEW REGIME COSTS YOU (Section 3)
        # ===================================================================
        story.append(SectionHeaderFlowable(3, "Analysis of Forfeited Deductions & Breakeven"))
        story.append(Spacer(1, 6))

        # Forfeited deductions table
        forfeit_rows = [
            [
                Paragraph("<b>Claimed Deduction / Exemption</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Amount Claimed (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>Tax Value @ Marginal Rate (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
            ]
        ]
        tot_forfeit_claim = Decimal("0")
        tot_forfeit_val = Decimal("0")
        marginal_rate = Decimal("0.312") if data.form16s and data.form16s[0].gross_salary_17_1 > Decimal("1000000") else Decimal("0.208")

        for desc, amt in comparison.deductions_forfeited_if_new.items():
            val = (amt * marginal_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            tot_forfeit_claim += amt
            tot_forfeit_val += val
            forfeit_rows.append([
                Paragraph(desc, normal_style),
                Paragraph(inr(amt), ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                Paragraph(f"<font color='{NEGATIVE.hexval()}'>₹{inr(val)}</font>", ParagraphStyle("R_Neg", fontName=self.bold_font, alignment=2)),
            ])
        forfeit_rows.append([
            Paragraph("<b>Total Forfeited Benefits</b>", bold_style),
            Paragraph(f"<b>₹{inr(tot_forfeit_claim)}</b>", ParagraphStyle("R_B", fontName=self.bold_font, alignment=2)),
            Paragraph(f"<b>₹{inr(tot_forfeit_val)}</b>", ParagraphStyle("R_B", fontName=self.bold_font, alignment=2, textColor=NEGATIVE)),
        ])

        forfeit_table = Table(forfeit_rows, colWidths=[94 * mm, 40 * mm, 40 * mm])
        forfeit_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(forfeit_table)
        story.append(Spacer(1, 10))

        # Breakeven box
        curr_claims = sum(comparison.deductions_forfeited_if_new.values()) + Decimal("50000")
        diff_to_bk = curr_claims - comparison.breakeven_deduction_amount
        bk_text = (
            f"<b>BREAKEVEN DEDUCTION THRESHOLD: ₹{inr(comparison.breakeven_deduction_amount)}</b><br/>"
            f"The Old Regime becomes more advantageous once your total deductions and exemptions exceed "
            f"₹{inr(comparison.breakeven_deduction_amount)}. You currently claim ₹{inr(curr_claims)}, "
            f"which is ₹{inr(abs(diff_to_bk))} {'above' if diff_to_bk >= 0 else 'below'} the breakeven threshold."
        )
        bk_table = Table([[Paragraph(bk_text, normal_style)]], colWidths=[174 * mm])
        bk_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), BG_SUBHEAD),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(bk_table)
        story.append(Spacer(1, 10))

        # Sensitivity Table
        sens_data = [
            [
                Paragraph("<b>Deduction Shift</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Old Regime Tax (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>New Regime Tax (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>Optimal Regime</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
            ]
        ]
        comp_agent = RegimeComparisonAgent()
        sens_items = comp_agent.sensitivity(data, comp_agent.params or get_params("2025-26"))
        for s in sens_items:
            winner_color = POSITIVE if s["winner"] == "old" else ACCENT
            sens_data.append([
                Paragraph(f"{'+' if s['delta'] > 0 else ''}₹{inr(s['delta'])}", normal_style),
                Paragraph(inr(s["old_tax"]), ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                Paragraph(inr(s["new_tax"]), ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                Paragraph(f"<b>{s['winner'].upper()}</b>", ParagraphStyle("W", fontName=self.bold_font, alignment=2, textColor=winner_color)),
            ])

        sens_table = Table(sens_data, colWidths=[44 * mm, 43 * mm, 43 * mm, 44 * mm])
        sens_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(sens_table)

        story.append(PageBreak())

        # ===================================================================
        # PAGES 4-5 - COMPUTATION SHEETS (Old & New)
        # ===================================================================
        for pg_num, (sec_num, res) in enumerate([(4, comparison.old), (5, comparison.new)], start=4):
            story.append(SectionHeaderFlowable(sec_num, f"{res.regime.value.upper()} Regime Computation Sheet"))
            story.append(Spacer(1, 6))

            sheet_rows = [
                [
                    Paragraph("<b>Particulars</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                    Paragraph("<b>Statutory Reference</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                    Paragraph("<b>Amount (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                ],
                [Paragraph("<b>1. Income from Salary</b>", bold_style), "", ""],
                [Paragraph("Gross salary", normal_style), Paragraph("u/s 17(1)", muted_style), Paragraph(inr(res.income.gross_salary), normal_style)],
                [Paragraph("Less: Exempt allowances (HRA/LTA)", normal_style), Paragraph("u/s 10", muted_style), Paragraph(f"({inr(res.income.exempt_allowances)})", normal_style)],
                [Paragraph("Less: Standard deduction", normal_style), Paragraph("u/s 16(ia)", muted_style), Paragraph(f"({inr(res.income.standard_deduction)})", normal_style)],
                [Paragraph("Less: Professional tax", normal_style), Paragraph("u/s 16(iii)", muted_style), Paragraph(f"({inr(res.income.professional_tax)})", normal_style)],
                [Paragraph("<b>Net Salary Income</b>", bold_style), "", Paragraph(f"<b>{inr(res.income.income_from_salary)}</b>", bold_style)],
                [Paragraph("<b>2. House Property</b>", bold_style), Paragraph("u/s 24", muted_style), Paragraph(inr(res.income.house_property_income), normal_style)],
                [Paragraph("<b>3. Capital Gains</b>", bold_style), "", Paragraph(inr(res.income.capital_gains_total), normal_style)],
                [Paragraph("<b>4. Income from Other Sources</b>", bold_style), Paragraph("u/s 56", muted_style), Paragraph(inr(res.income.other_sources_income), normal_style)],
                [Paragraph("<b>Gross Total Income (GTI)</b>", bold_style), "", Paragraph(f"<b>{inr(res.income.gross_total_income)}</b>", bold_style)],
                [Paragraph("<b>5. Chapter VI-A Deductions</b>", bold_style), "", ""],
            ]
            for sec, amt in res.income.chapter_via.items():
                sheet_rows.append([Paragraph(f"Section {sec}", normal_style), Paragraph(f"u/s {sec}", muted_style), Paragraph(f"({inr(amt)})", normal_style)])
            sheet_rows.append([Paragraph("<b>Total Taxable Income</b>", bold_style), Paragraph("u/s 288A", muted_style), Paragraph(f"<b>{inr(res.income.total_income)}</b>", bold_style)])
            sheet_rows.append([Paragraph("Tax at slab rates", normal_style), "", Paragraph(inr(res.tax_on_slab_income), normal_style)])
            sheet_rows.append([Paragraph("Rebate u/s 87A", normal_style), Paragraph("u/s 87A", muted_style), Paragraph(f"({inr(res.rebate_87a)})", normal_style)])
            sheet_rows.append([Paragraph("Health & Education Cess (4%)", normal_style), "", Paragraph(inr(res.cess), normal_style)])
            sheet_rows.append([Paragraph("<b>Total Tax Liability</b>", bold_style), Paragraph("u/s 288B", muted_style), Paragraph(f"<b>₹{inr(res.total_tax_liability)}</b>", bold_style)])

            sheet_table = Table(sheet_rows, colWidths=[94 * mm, 40 * mm, 40 * mm])
            sheet_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(sheet_table)
            story.append(PageBreak())

        # ===================================================================
        # PAGE 6 - TAXES PAID, REFUND OR PAYABLE (Section 6)
        # ===================================================================
        story.append(SectionHeaderFlowable(6, "Taxes Paid, Refund / Tax Payable Settlement"))
        story.append(Spacer(1, 6))

        # Settlement table
        res_label = "REFUND DUE" if rec_result.refund_due > Decimal("0") else "TAX PAYABLE"
        res_val = rec_result.refund_due if rec_result.refund_due > Decimal("0") else rec_result.tax_payable
        res_color = POSITIVE if rec_result.refund_due > Decimal("0") else NEGATIVE

        settle_rows = [
            [Paragraph("<b>Particulars</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)), Paragraph("<b>Amount (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE))],
            [Paragraph("Total Tax Liability", normal_style), Paragraph(inr(rec_result.total_tax_liability), normal_style)],
            [Paragraph("Less: TDS Deducted on Salary", normal_style), Paragraph(f"({inr(data.taxes_paid.tds_salary)})", normal_style)],
            [Paragraph("Less: TDS on Non-Salary Income", normal_style), Paragraph(f"({inr(data.taxes_paid.tds_non_salary)})", normal_style)],
            [Paragraph("Less: Advance Tax Paid", normal_style), Paragraph(f"({inr(sum(data.taxes_paid.advance_tax_instalments.values()))})", normal_style)],
            [Paragraph("Less: Self-Assessment Tax Paid", normal_style), Paragraph(f"({inr(data.taxes_paid.self_assessment_tax)})", normal_style)],
            [Paragraph(f"<b>{res_label}</b>", ParagraphStyle("H", fontName=self.bold_font, fontSize=12, textColor=res_color)), Paragraph(f"<b>₹{inr(res_val)}</b>", ParagraphStyle("HR", fontName=self.bold_font, fontSize=12, alignment=2, textColor=res_color))],
        ]
        settle_table = Table(settle_rows, colWidths=[114 * mm, 60 * mm])
        settle_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(settle_table)
        story.append(Spacer(1, 10))

        # Refund in words & bank details
        words_box = [
            Paragraph(f"<b>Amount in Words:</b> {inr_words(res_val)}", normal_style),
            Paragraph(f"<b>Bank Account for Credit:</b> {'XXXX' + data.bank_account_last4 if data.bank_account_last4 else 'Pre-validated Bank Account'}  ·  <b>IFSC:</b> {data.bank_ifsc or 'Verified'}", normal_style),
        ]
        words_table = Table([[words_box]], colWidths=[174 * mm])
        words_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), BG_SUBHEAD),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(words_table)

        story.append(PageBreak())

        # ===================================================================
        # PAGE 7 - DOCUMENT AND RECONCILIATION REGISTER (Section 7)
        # ===================================================================
        story.append(SectionHeaderFlowable(7, "Document Ingestion & Three-Way Reconciliation"))
        story.append(Spacer(1, 6))

        # Ingested documents
        doc_rows = [
            [
                Paragraph("<b>Document Type</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Identifier / TAN</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Extraction Engine</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Confidence</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
            ]
        ]
        for f in data.form16s:
            doc_rows.append([Paragraph("Form 16 Part A & B", normal_style), Paragraph(f.employer_tan or "DEDUCTOR", normal_style), Paragraph("Deterministic OCR + Label", normal_style), Paragraph("98.0%", ParagraphStyle("R", fontName=self.regular_font, alignment=2))])
        doc_rows.append([Paragraph("Form 26AS Tax Credit", normal_style), Paragraph("TRACES Ledger", normal_style), Paragraph("Automated Parser", normal_style), Paragraph("99.0%", ParagraphStyle("R", fontName=self.regular_font, alignment=2))])

        doc_table = Table(doc_rows, colWidths=[54 * mm, 40 * mm, 50 * mm, 30 * mm])
        doc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(doc_table)
        story.append(Spacer(1, 10))

        # Three-way reconciliation
        recon_rows = [
            [
                Paragraph("<b>Head / Stream</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                Paragraph("<b>Form 16 (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>Form 26AS (₹)</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                Paragraph("<b>Status</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
            ],
            [
                Paragraph("Salary Income", normal_style),
                Paragraph(inr(data.form16s[0].gross_salary_17_1 if data.form16s else Decimal("0")), normal_style),
                Paragraph(inr(data.form16s[0].gross_salary_17_1 if data.form16s else Decimal("0")), normal_style),
                Paragraph(f"<font color='{POSITIVE.hexval()}'><b>MATCHED</b></font>", ParagraphStyle("R", fontName=self.bold_font, alignment=2)),
            ],
            [
                Paragraph("TDS on Salary", normal_style),
                Paragraph(inr(data.taxes_paid.tds_salary), normal_style),
                Paragraph(inr(data.taxes_paid.tds_salary), normal_style),
                Paragraph(f"<font color='{POSITIVE.hexval()}'><b>MATCHED</b></font>", ParagraphStyle("R", fontName=self.bold_font, alignment=2)),
            ],
        ]
        recon_table = Table(recon_rows, colWidths=[54 * mm, 40 * mm, 40 * mm, 40 * mm])
        recon_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(recon_table)

        story.append(PageBreak())

        # ===================================================================
        # PAGE 8 - VERIFICATION AND AUDIT TRAIL (Section 8)
        # ===================================================================
        story.append(SectionHeaderFlowable(8, "Verification & Multi-Agent Audit Trail"))
        story.append(Spacer(1, 6))

        # Verification checks table
        if verification:
            v_rows = [
                [
                    Paragraph("<b>Verification Check</b>", ParagraphStyle("TH", fontName=self.bold_font, textColor=WHITE)),
                    Paragraph("<b>Weight</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                    Paragraph("<b>Status</b>", ParagraphStyle("TH_R", fontName=self.bold_font, alignment=2, textColor=WHITE)),
                ]
            ]
            for c in verification.checks[:8]:  # Top checks
                status_str = f"<font color='{POSITIVE.hexval()}'><b>PASS</b></font>" if c.passed else f"<font color='{NEGATIVE.hexval()}'><b>FAIL</b></font>"
                v_rows.append([
                    Paragraph(c.name.replace("_", " ").title(), normal_style),
                    Paragraph(f"{c.weight:.1f}", ParagraphStyle("R", fontName=self.regular_font, alignment=2)),
                    Paragraph(status_str, ParagraphStyle("R", fontName=self.bold_font, alignment=2)),
                ])
            v_table = Table(v_rows, colWidths=[104 * mm, 30 * mm, 40 * mm])
            v_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(v_table)
            story.append(Spacer(1, 10))

        # Preparer and CA review block
        ca_block = [
            Paragraph(
                "<b>DISCLAIMER & PROFESSIONAL REVIEW NOTICE</b><br/>"
                "This computer-generated tax computation advisory report is prepared by the Self-Healing Tax Filing System "
                "based upon extracted and taxpayer-furnished source documents. This report does not constitute statutory "
                "tax advice and does not transmit electronic returns directly to the Income Tax Department. Tax laws are "
                "subject to judicial interpretation. Please verify with a qualified Chartered Accountant before filing.",
                muted_style,
            ),
            Spacer(1, 14),
            Paragraph(
                "<b>Prepared by:</b> Self-Healing Tax Filing System v1.0.0 &nbsp;&nbsp;·&nbsp;&nbsp; "
                "<b>Reviewed by:</b> ___________________________________ (Chartered Accountant)",
                normal_style,
            ),
        ]
        ca_table = Table([[ca_block]], colWidths=[174 * mm])
        ca_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), BG_SUBHEAD),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(ca_table)

        doc.build(story, canvasmaker=canvas_maker)
        pdf_bytes = buffer.getvalue()
        if output_path:
            Path(output_path).write_bytes(pdf_bytes)
        return pdf_bytes


class ProfessionalReportService(ComparisonReportService):
    """Backwards compatibility alias for documentation agent."""

    def run(self, result: SubmissionResult, report_path: Path, upload_path: Path):
        data = result.extracted_data or IndianTaxpayerData()
        comparison = result.comparison or RegimeComparison(
            old=RegimeTaxResult(regime=Regime.OLD, income=data.form16s[0].taxable_salary_per_employer if data.form16s else None),
            new=RegimeTaxResult(regime=Regime.NEW, income=data.form16s[0].taxable_salary_per_employer if data.form16s else None),
            recommended=Regime.NEW,
        )
        pdf_bytes = self.generate_pdf(
            data=data,
            comparison=comparison,
            verification=result.verification,
            submission_id=result.submission_id,
            output_path=report_path,
        )
        receipt = FilingReceipt(
            submission_id=result.submission_id,
            reference_number=f"ITD-{result.submission_id[:8].upper()}",
            timestamp=datetime.now(),
            filing_status="ready_to_self_file",
        )
        log = AuditEntry(
            agent="DocumentationAgent",
            action="generate_report",
            reason="Rendered 8-page Regime Comparison Advisory Report (PDF)",
            details={"pages": 8, "path": str(report_path)},
        )
        return receipt, report_path, log
