"""Styling, Indian currency formatting, palette, fonts, and furniture for the PDF advisory report."""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
pt = 1
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

# Six-color authoritative palette
INK = HexColor("#10151B")
MUTED = HexColor("#5B6672")
RULE = HexColor("#D8DEE5")
ACCENT = HexColor("#0B3D5C")
POSITIVE = HexColor("#0F7B4F")
NEGATIVE = HexColor("#A8342A")
BG_SUBHEAD = HexColor("#F6F8FA")
WHITE = HexColor("#FFFFFF")


def inr(value: Any, decimals: int = 0) -> str:
    """Format an amount with Indian digit grouping (lakhs & crores).
    
    Negative values are formatted in parentheses: (45,300), never with a minus sign.
    Examples:
        1234567 -> '12,34,567'
        100000  -> '1,00,000'
        -45300  -> '(45,300)'
    """
    if value is None:
        return "0"
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception:
            return "0"

    is_negative = value < 0
    val_abs = abs(value)

    if decimals > 0:
        val_abs = val_abs.quantize(
            Decimal(10) ** -decimals, rounding=ROUND_HALF_UP
        )
        parts = f"{val_abs:.{decimals}f}".split(".")
        int_part = parts[0]
        dec_part = "." + parts[1]
    else:
        val_abs = val_abs.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        int_part = str(int(val_abs))
        dec_part = ""

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rem = int_part[:-3]
        groups = []
        while len(rem) > 2:
            groups.insert(0, rem[-2:])
            rem = rem[:-2]
        if rem:
            groups.insert(0, rem)
        formatted_int = ",".join(groups) + "," + last3

    res = formatted_int + dec_part
    if is_negative:
        return f"({res})"
    return res


_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen"
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
]


def _two_digits_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens = _TENS[n // 10]
    ones = _ONES[n % 10]
    return f"{tens} {ones}".strip() if ones else tens


def _three_digits_words(n: int) -> str:
    hundreds = n // 100
    rem = n % 100
    res = []
    if hundreds:
        res.append(f"{_ONES[hundreds]} Hundred")
    if rem:
        res.append(_two_digits_words(rem))
    return " ".join(res)


def inr_words(value: Any) -> str:
    """Convert rupee integer into words according to Indian number system."""
    try:
        val = int(Decimal(str(value)))
    except Exception:
        return "Rupees Zero only"

    if val == 0:
        return "Rupees Zero only"

    is_negative = val < 0
    val = abs(val)

    crore = val // 10000000
    val %= 10000000
    lakh = val // 100000
    val %= 100000
    thousand = val // 1000
    val %= 1000
    hundreds = val

    parts = []
    if crore:
        parts.append(f"{_two_digits_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two_digits_words(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two_digits_words(thousand)} Thousand")
    if hundreds:
        parts.append(_three_digits_words(hundreds))

    words = " ".join(parts).strip()
    prefix = "Negative Rupees " if is_negative else "Rupees "
    return f"{prefix}{words} only"


def register_fonts() -> tuple[str, str]:
    """Register fonts or fallback cleanly to Helvetica."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "fonts"
    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"

    # Attempt to load vendored fonts if present
    if (font_dir / "SourceSans3-Regular.ttf").exists():
        try:
            pdfmetrics.registerFont(TTFont("SourceSans3", str(font_dir / "SourceSans3-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("SourceSans3-Bold", str(font_dir / "SourceSans3-Bold.ttf")))
            pdfmetrics.registerFont(TTFont("SourceSans3-Semibold", str(font_dir / "SourceSans3-Semibold.ttf")))
            regular_font = "SourceSans3"
            bold_font = "SourceSans3-Bold"
        except Exception as exc:
            logger.warning("Could not register SourceSans3 font: %s. Falling back to Helvetica.", exc)

    return regular_font, bold_font


class SectionHeaderFlowable(Flowable):
    """Section header on a 16pt-tall ACCENT bar spanning full content width (174mm)."""

    def __init__(self, number: int, title: str, width: float = 174 * mm):
        super().__init__()
        self.number = number
        self.title = title
        self.width = width
        self.height = 18 * pt

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        # Draw background ACCENT bar
        self.canv.setFillColor(ACCENT)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # Draw white header text
        self.canv.setFillColor(WHITE)
        self.canv.setFont("Helvetica-Bold", 10.5)
        text = f"{self.number}. {self.title}"
        self.canv.drawString(6 * pt, 4.5 * pt, text)
        self.canv.restoreState()


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvasmaker counting total pages for 'Page X of Y' footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_furniture(num_pages)
            super().showPage()
        super().save()

    def draw_page_furniture(self, total_pages: int):
        self.saveState()
        width, height = self._pagesize

        # Running Header on page 2 and later
        if self._pageNumber > 1:
            self.setFont("Helvetica", 7.5)
            self.setFillColor(MUTED)
            taxpayer_str = getattr(self, "taxpayer_header", "Taxpayer Advisory Report")
            self.drawString(18 * mm, height - 12 * mm, taxpayer_str)
            self.drawRightString(width - 18 * mm, height - 12 * mm, "Assessment Year 2026-27 (Financial Year 2025-26)")

            # Hairline beneath header
            self.setStrokeColor(RULE)
            self.setLineWidth(0.5)
            self.line(18 * mm, height - 13.5 * mm, width - 18 * mm, height - 13.5 * mm)

        # Running Footer on all pages
        self.setFont("Helvetica", 7.0)
        self.setFillColor(MUTED)

        # Left footer: Document ID and timestamp
        doc_id = getattr(self, "doc_id", "DOC-ADVISORY")
        timestamp = getattr(self, "gen_timestamp", "15 Sep 2026 12:00 IST")
        self.drawString(18 * mm, 12 * mm, f"Document ID: {doc_id}  ·  Generated {timestamp}")

        # Centre footer: Page X of Y
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawCentredString(width / 2.0, 12 * mm, page_str)

        # Right footer: Disclaimer
        disclaimer = "Computer-generated advisory. Not tax advice. Verify with a CA."
        self.drawRightString(width - 18 * mm, 12 * mm, disclaimer)

        # Hairline above footer
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)

        self.restoreState()
