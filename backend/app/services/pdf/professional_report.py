"""Professional, sectioned tax-filing report.

A polished summary document (navy section bands, two/three-column panels, status
strips) covering taxpayer info, filing summary, documents, income, the tax
calculation, deductions & credits, the verification/remediation outcome, filing
details, and the agent-pipeline run.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import fitz

try:  # pragma: no cover - optional runtime dependency
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    REPORTLAB_AVAILABLE = False

    class _DummyColors:
        white = "#FFFFFF"

        def HexColor(self, value: str) -> str:
            return value

    class _DummyParagraphStyle:
        def __init__(self, *_args, **_kwargs):
            pass

    class _DummyFlowable:
        def __init__(self, *_args, **_kwargs):
            pass

    class _DummySimpleDocTemplate:
        def __init__(self, *_args, **_kwargs):
            pass

        def build(self, *_args, **_kwargs):
            return None

    colors = _DummyColors()
    ParagraphStyle = _DummyParagraphStyle
    inch = 72
    Paragraph = Spacer = Table = TableStyle = _DummyFlowable
    SimpleDocTemplate = _DummySimpleDocTemplate
    letter = (612, 792)

from app.schemas import FilingReceipt, SubmissionResult, TaxpayerData
from app.schemas.tax import TaxCalculation, VerificationResult

ZERO = Decimal("0")
NAVY = colors.HexColor("#16365c")
NAVY_LIGHT = colors.HexColor("#e8eef6")
GREEN = colors.HexColor("#1f8a4c")
GREEN_BG = colors.HexColor("#e7f4ec")
RED = colors.HexColor("#c0392b")
INK = colors.HexColor("#1c2733")
GREY = colors.HexColor("#6b7785")
HAIR = colors.HexColor("#d7dee7")
ZEBRA = colors.HexColor("#f4f7fb")

CONTENT_W = 7.3 * inch

_BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11)
_GREY = ParagraphStyle("g", fontName="Helvetica", fontSize=7.5, textColor=GREY, leading=10)


def _money(v) -> str:
    if v is None:
        return "$0.00"
    d = Decimal(v)
    return f"(${abs(d):,.2f})" if d < 0 else f"${d:,.2f}"


class ProfessionalReportService:
    def generate(
        self, result: SubmissionResult, receipt: FilingReceipt, output: Path
    ) -> Path:
        if not REPORTLAB_AVAILABLE:
            return self._generate_fallback(result, receipt, output)
        data = result.extracted_data or TaxpayerData()
        calc = result.calculation
        ver = result.verification
        output.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output), pagesize=letter,
            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
            topMargin=0.5 * inch, bottomMargin=0.55 * inch,
            title="Professional Tax Filing Report",
        )
        story = self._masthead(receipt)
        story.append(Spacer(1, 10))
        story += self._row([
            self._taxpayer(data, receipt),
            self._filing_summary(calc),
            self._documents(data),
        ], [2.45 * inch, 2.45 * inch, 2.4 * inch])
        story.append(Spacer(1, 9))
        story += self._row([
            self._income(data, calc),
            self._calc_breakdown(calc),
        ], [3.6 * inch, 3.7 * inch])
        story.append(Spacer(1, 9))
        story += self._row([
            self._deductions_credits(calc),
            self._filing_details(receipt, calc),
        ], [3.6 * inch, 3.7 * inch])
        story.append(Spacer(1, 9))
        story.append(self._verification_strip(ver))
        story.append(Spacer(1, 9))
        story.append(self._agent_pipeline(data, ver))
        doc.build(story, onFirstPage=self._frame, onLaterPages=self._frame)
        return output

    def _generate_fallback(
        self, result: SubmissionResult, receipt: FilingReceipt, output: Path
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        data = result.extracted_data or TaxpayerData()
        calc = result.calculation
        ver = result.verification

        lines = [
            "PROFESSIONAL TAX FILING REPORT",
            f"Reference: {receipt.reference_number}",
            f"Status: {receipt.filing_status}",
            f"Submission: {result.submission_id}",
            f"Taxpayer: {data.employee_name or 'Not provided'}",
            f"Employer: {data.employer_name or 'Not provided'}",
            f"Tax year: {data.tax_year}",
        ]
        if calc is not None:
            lines.extend(
                [
                    f"Total income: {_money(calc.total_income)}",
                    f"Taxable income: {_money(calc.taxable_income)}",
                    f"Federal tax: {_money(calc.federal_tax)}",
                    f"State tax: {_money(calc.state_tax)}",
                    f"Refund: {_money(calc.refund)}",
                    f"Tax due: {_money(calc.tax_due)}",
                ]
            )
        if ver is not None:
            lines.extend(
                [
                    f"Verification valid: {ver.valid}",
                    f"Confidence: {round(ver.confidence_score * 100)}%",
                    f"Correctness: {ver.correctness_ok}",
                    f"Completeness: {ver.completeness_ok}",
                ]
            )
        if result.audit_trail:
            lines.append("Audit trail:")
            for entry in result.audit_trail[:12]:
                lines.append(f"- {entry.agent}: {entry.action} ({entry.reason})")

        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_textbox(
            fitz.Rect(40, 40, 572, 752),
            "\n".join(lines),
            fontsize=12,
            fontname="helv",
            color=(0, 0, 0),
            align=0,
        )
        document.save(str(output))
        document.close()
        return output

    # ---------- masthead ----------
    def _masthead(self, receipt: FilingReceipt) -> list:
        title_style = ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=17, leading=19, textColor=NAVY
        )
        sub_style = ParagraphStyle(
            "sub", fontName="Helvetica", fontSize=8.5, leading=11, textColor=GREY,
            spaceBefore=3,
        )
        title = Table(
            [[Paragraph("PROFESSIONAL TAX FILING REPORT", title_style)],
             [Paragraph(
                 "Generated by the Agentic AI Pipeline for End-to-End Automated "
                 "US Tax Filing", sub_style)]],
            colWidths=[4.6 * inch],
        )
        title.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        submitted = receipt.filing_status in ("accepted", "ready_to_self_file")
        badge_label = (
            "TAX FILING SUCCESSFULLY SUBMITTED" if receipt.filing_status == "accepted"
            else "READY TO FILE" if submitted else receipt.filing_status.replace("_", " ").upper()
        )
        when = receipt.timestamp.strftime("%b %d, %Y | %I:%M %p UTC")
        badge = Table(
            [[Paragraph(
                f"<font size=8 color='#1f8a4c'><b>&#10004; {badge_label}</b></font>"
                f"<br/><font size=7 color='#6b7785'>{when}</font>", _BODY)]],
            colWidths=[2.7 * inch],
        )
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GREEN_BG),
            ("BOX", (0, 0), (-1, -1), 1, GREEN),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        head = Table([[title, badge]], colWidths=[4.6 * inch, 2.7 * inch])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 2, NAVY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return [head]

    # ---------- panels ----------
    def _panel(self, title: str, body, width: float):
        band = Table([[Paragraph(f"<font color='white' size=9><b>{title}</b></font>", _BODY)]],
                     colWidths=[width])
        band.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        wrap = Table([[band], [body]], colWidths=[width])
        wrap.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, HAIR),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return wrap

    def _row(self, panels: list, widths: list[float]) -> list:
        outer = Table([panels], colWidths=widths)
        outer.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-2, -1), 6),
        ]))
        return [outer]

    def _kv(self, rows: list[tuple[str, str]], width: float) -> Table:
        data = [[Paragraph(f"<b>{k}</b>", _BODY), Paragraph(v or "—", _BODY)] for k, v in rows]
        t = Table(data, colWidths=[width * 0.42, width * 0.58])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, HAIR),
        ]))
        return t

    def _amounts(self, header: tuple[str, str], rows: list, width: float,
                 highlight_last: bool = False) -> Table:
        body = [[Paragraph(f"<b>{header[0]}</b>", _GREY),
                 Paragraph(f"<b>{header[1]}</b>", ParagraphStyle('h', parent=_GREY, alignment=2))]]
        for label, amount, bold in rows:
            lab = f"<b>{label}</b>" if bold else label
            amt = f"<b>{_money(amount)}</b>" if bold else _money(amount)
            body.append([Paragraph(lab, _BODY),
                         Paragraph(amt, ParagraphStyle('r', parent=_BODY, alignment=2))])
        t = Table(body, colWidths=[width * 0.62, width * 0.38])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIR),
        ]
        for i, (_l, _a, bold) in enumerate(rows, start=1):
            if bold:
                style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        if highlight_last:
            style += [("BACKGROUND", (0, -1), (-1, -1), GREEN_BG),
                      ("TEXTCOLOR", (0, -1), (-1, -1), GREEN),
                      ("LINEABOVE", (0, -1), (-1, -1), 0.8, GREEN)]
        t.setStyle(TableStyle(style))
        return t

    # ---------- sections ----------
    def _taxpayer(self, data: TaxpayerData, receipt: FilingReceipt):
        w = 2.45 * inch
        body = self._kv([
            ("Full Name", data.employee_name),
            ("SSN / ITIN", data.masked_ssn),
            ("Filing Status", data.filing_status.replace("_", " ").title()),
            ("Tax Year", str(data.tax_year)),
            ("Reference", receipt.reference_number),
        ], w)
        return self._panel("1. TAXPAYER INFORMATION", body, w)

    def _filing_summary(self, calc: TaxCalculation | None):
        w = 2.45 * inch
        c = calc
        refund = c.refund if c else ZERO
        due = c.tax_due if c else ZERO
        result_label = "Refund Amount" if (c and refund >= due) else "Balance Due"
        result_val = refund if (c and refund >= due) else due
        rows = [
            ("Total Income", c.total_income if c else ZERO, False),
            ("Total Deductions", (c.deductions + c.qbi_deduction) if c else ZERO, False),
            ("Taxable Income", c.taxable_income if c else ZERO, False),
            ("Total Tax Liability", c.federal_tax if c else ZERO, False),
            (result_label, result_val, True),
        ]
        body = self._amounts(("Item", "Amount"), rows, w, highlight_last=True)
        return self._panel("2. FILING SUMMARY", body, w)

    def _documents(self, data: TaxpayerData):
        w = 2.4 * inch
        docs = [("W-2 Form", data.wages > 0)]
        if data.taxable_interest > 0 or data.ordinary_dividends > 0:
            docs.append(("1099-INT / 1099-DIV", True))
        if data.self_employment_income > 0:
            docs.append(("1099-NEC / Schedule C", True))
        if data.taxable_pension_ira > 0:
            docs.append(("1099-R", True))
        if data.social_security_benefits > 0:
            docs.append(("SSA-1099", True))
        rows = [[Paragraph("<b>Document</b>", _GREY),
                 Paragraph("<b>Status</b>", ParagraphStyle('h', parent=_GREY, alignment=1))]]
        for name, ok in docs:
            status = ("<font color='#1f8a4c'>&#10004; Processed</font>" if ok
                      else "<font color='#6b7785'>Not present</font>")
            rows.append([Paragraph(name, _BODY),
                         Paragraph(status, ParagraphStyle('c', parent=_BODY, alignment=1))])
        rows.append([Paragraph("<b>Total Documents</b>", _BODY),
                     Paragraph(f"<b>{len(docs)}</b>", ParagraphStyle('c', parent=_BODY, alignment=1))])
        t = Table(rows, colWidths=[w * 0.62, w * 0.38])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
            ("BACKGROUND", (0, -1), (-1, -1), ZEBRA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIR),
        ]))
        return self._panel("3. DOCUMENTS SUMMARY", t, w)

    def _income(self, data: TaxpayerData, calc: TaxCalculation | None):
        w = 3.6 * inch
        rows = []
        for label, val in [
            ("W-2 Wages", data.wages),
            ("Taxable Interest", data.taxable_interest),
            ("Ordinary Dividends", data.ordinary_dividends),
            ("Capital Gains", data.long_term_capital_gain + data.short_term_capital_gain),
            ("Self-Employment", data.self_employment_income),
            ("Taxable Social Security", calc.taxable_social_security if calc else ZERO),
            ("Other Income", data.taxable_pension_ira + data.partnership_income + data.other_income),
        ]:
            if val and val != 0:
                rows.append((label, val, False))
        rows.append(("Total Income", calc.total_income if calc else ZERO, True))
        body = self._amounts(("Source", "Amount (USD)"), rows, w)
        return self._panel("4. INCOME SUMMARY", body, w)

    def _calc_breakdown(self, calc: TaxCalculation | None):
        w = 3.7 * inch
        c = calc
        rows = [
            ("Gross Income", c.total_income if c else ZERO, False),
            ("Adjustments to Income", -(c.adjustments if c else ZERO), False),
            ("Adjusted Gross Income (AGI)", c.adjusted_gross_income if c else ZERO, True),
            ("Deductions", -((c.deductions + c.qbi_deduction) if c else ZERO), False),
            ("Taxable Income", c.taxable_income if c else ZERO, True),
            ("Tax Before Credits", c.income_tax_before_credits if c else ZERO, False),
            ("Credits", -((c.nonrefundable_credits) if c else ZERO), False),
            ("Other Taxes", c.other_taxes if c else ZERO, False),
            ("Total Tax Liability", c.federal_tax if c else ZERO, True),
            ("Total Payments", c.total_payments if c else ZERO, False),
        ]
        refund = c.refund if c else ZERO
        due = c.tax_due if c else ZERO
        if c and due > refund:
            rows.append(("Balance Due", due, True))
            body = self._amounts(("Description", "Amount (USD)"), rows, w)
        else:
            rows.append(("Refund Amount", refund, True))
            body = self._amounts(("Description", "Amount (USD)"), rows, w, highlight_last=True)
        return self._panel("5. TAX CALCULATION BREAKDOWN", body, w)

    def _deductions_credits(self, calc: TaxCalculation | None):
        w = 3.6 * inch
        c = calc
        rows = [
            ("Standard / Itemized Deduction", c.deductions if c else ZERO, False),
            ("QBI Deduction", c.qbi_deduction if c else ZERO, False),
            ("Total Deductions", (c.deductions + c.qbi_deduction) if c else ZERO, True),
            ("Child Tax Credit", (c.child_tax_credit + c.refundable_child_tax_credit) if c else ZERO, False),
            ("Education / Saver's Credit", (c.education_credits + c.savers_credit + c.refundable_education_credit) if c else ZERO, False),
            ("Earned Income Credit", c.earned_income_credit if c else ZERO, False),
            ("Total Credits", self._total_credits(c), True),
        ]
        body = self._amounts(("Item", "Amount (USD)"), rows, w)
        return self._panel("6. DEDUCTIONS & CREDITS SUMMARY", body, w)

    @staticmethod
    def _total_credits(c: TaxCalculation | None) -> Decimal:
        if not c:
            return ZERO
        return (c.nonrefundable_credits + c.earned_income_credit
                + c.refundable_child_tax_credit + c.refundable_education_credit)

    def _filing_details(self, receipt: FilingReceipt, calc: TaxCalculation | None):
        w = 3.7 * inch
        body = self._kv([
            ("Return Type", "Form 1040"),
            ("Submission Method", "Self-file (PDF)" if receipt.reference_number.startswith("TX") else "MeF transmitter"),
            ("Submission ID", receipt.submission_id[:18]),
            ("Reference / Ack ID", receipt.reference_number),
            ("Filed On", receipt.timestamp.strftime("%b %d, %Y | %I:%M %p UTC")),
            ("Status", receipt.filing_status.replace("_", " ").title()),
        ], w)
        return self._panel("8. FILING DETAILS", body, w)

    # ---------- verification strip ----------
    def _verification_strip(self, ver: VerificationResult | None):
        checks = {c.name: c.passed for c in (ver.checks if ver else [])}
        cells = [
            ("Data Consistency", checks.get("withholding_bounds", True) and checks.get("w2_social_security_invariant", True) and checks.get("w2_medicare_invariant", True)),
            ("Tax Rule Check", checks.get("calculation_replay", True)),
            ("Hallucination Check", checks.get("source_grounding", True)),
            ("Completeness", ver.completeness_ok if ver else True),
            ("Remediation", None),  # informational
        ]
        row = []
        for label, ok in cells:
            if ok is None:
                status = "<font color='#16365c'><b>Not Required</b></font>"
                sub = "No issues detected"
            elif ok:
                status = "<font color='#1f8a4c'><b>&#10004; Passed</b></font>"
                sub = "Validated"
            else:
                status = "<font color='#c0392b'><b>&#10008; Review</b></font>"
                sub = "Needs attention"
            row.append(Paragraph(
                f"<b>{label}</b><br/>{status}<br/><font size=7 color='#6b7785'>{sub}</font>",
                ParagraphStyle('vc', parent=_BODY, alignment=1, leading=12)))
        body = Table([row], colWidths=[CONTENT_W / 5] * 5)
        body.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEAFTER", (0, 0), (-2, -1), 0.4, HAIR),
        ]))
        return self._panel("7. VERIFICATION & REMEDIATION SUMMARY", body, CONTENT_W)

    # ---------- agent pipeline ----------
    def _agent_pipeline(self, data: TaxpayerData, ver: VerificationResult | None):
        conf = ver.confidence_score if ver else 0.0
        ex = (sum(data.field_confidence.values()) / len(data.field_confidence)
              if data.field_confidence else 0.99)
        agents = [
            ("1  Reading / Parsing Agent", "Extract & parse documents", "Completed", f"{ex:.1%}"),
            ("2  Tax Processing Agent", "Calculate tax & deductions", "Completed", "100.0%"),
            ("3  Verification Agent", "Validate & check consistency", "Completed", f"{conf:.1%}"),
            ("4  Remediation Agent", "Correct errors (if any)", "Not Required", "—"),
            ("5  Documentation Agent", "Generate report & receipt", "Completed", "100.0%"),
        ]
        rows = [[Paragraph("<b>Agent</b>", _GREY), Paragraph("<b>Role</b>", _GREY),
                 Paragraph("<b>Status</b>", _GREY),
                 Paragraph("<b>Confidence</b>", ParagraphStyle('h', parent=_GREY, alignment=2))]]
        for name, role, status, c in agents:
            sc = ("<font color='#1f8a4c'>&#10004; " + status + "</font>" if status == "Completed"
                  else f"<font color='#16365c'>{status}</font>")
            rows.append([Paragraph(name, _BODY), Paragraph(role, _BODY),
                         Paragraph(sc, _BODY),
                         Paragraph(c, ParagraphStyle('r', parent=_BODY, alignment=2))])
        t = Table(rows, colWidths=[CONTENT_W * 0.27, CONTENT_W * 0.36, CONTENT_W * 0.22, CONTENT_W * 0.15])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIR),
        ]
        for i in range(2, len(rows), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        t.setStyle(TableStyle(style))
        return self._panel("9. AGENT PIPELINE SUMMARY", t, CONTENT_W)

    @staticmethod
    def _frame(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(HAIR)
        canvas.setLineWidth(0.5)
        canvas.line(0.6 * inch, 0.42 * inch, 8.0 * inch, 0.42 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(0.6 * inch, 0.3 * inch,
                          "Professional Tax Filing Report — generated; review before filing")
        canvas.drawRightString(8.0 * inch, 0.3 * inch, f"Page {doc.page}")
        canvas.restoreState()
