"""Styling, Indian currency formatting, palette, fonts, and furniture for the PDF advisory report.

Matches the professional, high-grade TaxMind Pro / CA-Grade specification.
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
pt = 1
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable

logger = logging.getLogger(__name__)

# TaxMind Pro Authoritative Color Palette
PRIMARY_NAVY = HexColor("#152C4E")    # Deep Navy Blue for primary brand & headers
NAVY_DARK = HexColor("#0F2038")       # Darkest navy
NAVY_REGIME = HexColor("#1E3A5F")     # Old regime header blue
TEAL_REGIME = HexColor("#064E3B")     # New regime header green
BG_LIGHT = HexColor("#F8FAFC")        # Clean background for alternating table rows
BG_SUBHEAD = HexColor("#F1F5F9")      # Subheading background
BORDER_COLOR = HexColor("#CBD5E1")    # Subtle slate border
BORDER_LIGHT = HexColor("#E2E8F0")    # Very light border
ACCENT_BLUE = HexColor("#2563EB")     # Accent link/badge blue
LIGHT_BLUE = HexColor("#EFF6FF")      # Light blue box fill
GREEN_SUCCESS = HexColor("#059669")   # Recommended regime green
GREEN_DARK = HexColor("#065F46")      # Deep forest green text
LIGHT_GREEN = HexColor("#ECFDF5")     # Green card background fill
RED_ALERT = HexColor("#DC2626")       # Tax payable / alert red
LIGHT_RED = HexColor("#FEF2F2")       # Alert card background fill
TEXT_DARK = HexColor("#1E293B")       # Dark slate body text
TEXT_MUTED = HexColor("#64748B")      # Muted slate secondary text
WHITE = HexColor("#FFFFFF")

# Backward-compatibility color aliases
INK = TEXT_DARK
MUTED = TEXT_MUTED
RULE = BORDER_COLOR
ACCENT = PRIMARY_NAVY
POSITIVE = GREEN_SUCCESS
NEGATIVE = RED_ALERT


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
    win_fonts = Path("C:/Windows/Fonts")

    # Priority 1: Segoe UI (Windows native with excellent Rupee support)
    if (win_fonts / "segoeui.ttf").exists() and (win_fonts / "segoeuib.ttf").exists():
        try:
            pdfmetrics.registerFont(TTFont("SegoeUI", str(win_fonts / "segoeui.ttf")))
            pdfmetrics.registerFont(TTFont("SegoeUI-Bold", str(win_fonts / "segoeuib.ttf")))
            return "SegoeUI", "SegoeUI-Bold"
        except Exception as exc:
            logger.warning("Could not register SegoeUI font: %s", exc)

    # Priority 2: Arial (Windows native with Rupee symbol)
    if (win_fonts / "arial.ttf").exists() and (win_fonts / "arialbd.ttf").exists():
        try:
            pdfmetrics.registerFont(TTFont("Arial", str(win_fonts / "arial.ttf")))
            pdfmetrics.registerFont(TTFont("Arial-Bold", str(win_fonts / "arialbd.ttf")))
            return "Arial", "Arial-Bold"
        except Exception as exc:
            logger.warning("Could not register Arial font: %s", exc)

    # Priority 3: SourceSans3 vendored font
    if (font_dir / "SourceSans3-Regular.ttf").exists():
        try:
            pdfmetrics.registerFont(TTFont("SourceSans3", str(font_dir / "SourceSans3-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("SourceSans3-Bold", str(font_dir / "SourceSans3-Bold.ttf")))
            return "SourceSans3", "SourceSans3-Bold"
        except Exception as exc:
            logger.warning("Could not register SourceSans3 font: %s", exc)

    return "Helvetica", "Helvetica-Bold"


class SectionHeaderFlowable(Flowable):
    """Section header on a 22pt-tall PRIMARY_NAVY bar spanning full content width (182mm)."""

    def __init__(self, number: int, title: str, subtitle: str = "", width: float = 182 * mm):
        super().__init__()
        self.number = number
        self.title = title
        self.subtitle = subtitle
        self.width = width
        self.height = 24 * pt if subtitle else 20 * pt

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        # Draw background Navy bar
        self.canv.setFillColor(PRIMARY_NAVY)
        self.canv.roundRect(0, 0, self.width, self.height, 2, fill=1, stroke=0)

        # Draw white title text
        self.canv.setFillColor(WHITE)
        self.canv.setFont("Helvetica-Bold", 10.5)
        text = f"{self.number}. {self.title.upper()}"

        if self.subtitle:
            self.canv.drawString(8 * pt, 12 * pt, text)
            self.canv.setFont("Helvetica", 7.5)
            self.canv.setFillColor(HexColor("#BFDBFE"))
            self.canv.drawString(8 * pt, 3.5 * pt, self.subtitle)
        else:
            self.canv.drawString(8 * pt, 6 * pt, text)

        self.canv.restoreState()


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvasmaker providing top running header and bottom footer on all pages."""

    def __init__(self, *args, **kwargs):
        self.year_label = kwargs.pop("year_label", "")
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
        margin_x = 14 * mm

        # -------------------------------------------------------------
        # TOP RUNNING HEADER ON ALL PAGES
        # -------------------------------------------------------------
        top_y = height - 12 * mm

        # Logo / Brand mark (Circle icon)
        self.setFillColor(PRIMARY_NAVY)
        self.circle(margin_x + 5.5 * mm, top_y + 1 * mm, 5 * mm, fill=1, stroke=0)
        self.setFillColor(WHITE)
        self.setFont("Helvetica-Bold", 7.5)
        self.drawCentredString(margin_x + 5.5 * mm, top_y - 1.5 * pt, "TM")

        # Brand Text
        self.setFillColor(PRIMARY_NAVY)
        self.setFont("Helvetica-Bold", 11)
        self.drawString(margin_x + 12.5 * mm, top_y + 1.5 * mm, "TaxMind Pro")
        self.setFont("Helvetica", 6.5)
        self.setFillColor(TEXT_MUTED)
        self.drawString(margin_x + 12.5 * mm, top_y - 2 * mm, "Deterministic Tax Advisory")

        # Document Title (Right of Center)
        self.setFillColor(PRIMARY_NAVY)
        self.setFont("Helvetica-Bold", 9.5)
        self.drawRightString(width - margin_x, top_y + 2 * mm, "CA-Grade Tax Regime Comparison Advisory Report")

        # Subtitle & Page Number
        self.setFont("Helvetica", 7.0)
        self.setFillColor(TEXT_MUTED)
        self.drawRightString(width - margin_x - 22 * mm, top_y - 2 * mm, self.year_label)

        # Page X of Y Badge
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(PRIMARY_NAVY)
        self.drawRightString(width - margin_x, top_y - 2 * mm, f"Page {self._pageNumber} of {total_pages}")

        # Top divider line
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.6)
        self.line(margin_x, top_y - 4.5 * mm, width - margin_x, top_y - 4.5 * mm)

        # -------------------------------------------------------------
        # BOTTOM RUNNING FOOTER ON ALL PAGES
        # -------------------------------------------------------------
        bot_y = 10 * mm

        # Bottom divider line
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.6)
        self.line(margin_x, bot_y + 3.5 * mm, width - margin_x, bot_y + 3.5 * mm)

        # Footer text
        self.setFont("Helvetica", 6.5)
        self.setFillColor(TEXT_MUTED)
        self.drawString(margin_x, bot_y, "Technology Meets Compliance  |  Your Trusted Tax Partner")
        self.drawRightString(width - margin_x, bot_y, "Confidential  |  For Taxpayer Use Only")

        self.restoreState()
