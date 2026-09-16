"""Form 26AS Parser.

Extracts TDS from salary (Part I), non-salary TDS (Part II), TCS (Part VI),
and Advance Tax / Self-Assessment Tax challans (Part VIII) to produce a TaxesPaid model
and an itemised TDS ledger.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.schemas.tax import SourceEvidence, TaxesPaid


def _clean_amount(text: str) -> Decimal:
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


class Form26ASParser:
    """Parses Form 26AS text into TaxesPaid and source evidence."""

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[TaxesPaid, list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []

        # Part I - TDS on Salary
        tds_salary = Decimal("0")
        for m in re.finditer(
            r"(?:PART\s*I\b|Salary.*?192).*?(?:Total\s*TDS\s*Deposited|Tax\s*Deposited)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE | re.DOTALL,
        ):
            tds_salary += _clean_amount(m.group(1))

        # If simple label
        if tds_salary == Decimal("0"):
            m = re.search(
                r"(?:TDS\s*on\s*Salary|TDS\s*u/s\s*192)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                text,
                re.IGNORECASE,
            )
            if m:
                tds_salary = _clean_amount(m.group(1))

        # Part II - TDS on non-salary
        tds_non_salary = Decimal("0")
        for m in re.finditer(
            r"(?:PART\s*II\b|Other\s*than\s*Salary).*?(?:Total\s*TDS\s*Deposited|Tax\s*Deposited)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE | re.DOTALL,
        ):
            tds_non_salary += _clean_amount(m.group(1))

        if tds_non_salary == Decimal("0"):
            m = re.search(
                r"(?:TDS\s*on\s*Non-Salary|TDS\s*other\s*than\s*salary)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                text,
                re.IGNORECASE,
            )
            if m:
                tds_non_salary = _clean_amount(m.group(1))

        # Part VI - TCS
        tcs = Decimal("0")
        m = re.search(
            r"(?:PART\s*VI\b|Tax\s*Collected\s*at\s*Source|TCS)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m:
            tcs = _clean_amount(m.group(1))

        # Part VIII - Advance Tax & Self-Assessment Tax
        advance_tax: dict[str, Decimal] = {}
        self_assessment_tax = Decimal("0")

        # Challan lines: BSR code, Date, Serial, Amount, Minor Head (100 = Advance, 300 = Self-Assessment)
        for m in re.finditer(
            r"(?:Challan|BSR\s*Code).*?([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4}).*?(?:Advance\s*Tax|Minor\s*Head\s*100|Self\s*Assessment|Minor\s*Head\s*300).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        ):
            dt = m.group(1)
            amt = _clean_amount(m.group(2))
            if "advance" in m.group(0).lower() or "100" in m.group(0):
                advance_tax[dt] = amt
            else:
                self_assessment_tax += amt

        # Direct search if formatted as totals
        if not advance_tax:
            m = re.search(
                r"(?:Advance\s*Tax\s*Paid|Total\s*Advance\s*Tax)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                text,
                re.IGNORECASE,
            )
            if m:
                advance_tax["total"] = _clean_amount(m.group(1))

        if self_assessment_tax == Decimal("0"):
            m = re.search(
                r"(?:Self\s*Assessment\s*Tax\s*Paid|Total\s*SAT)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                text,
                re.IGNORECASE,
            )
            if m:
                self_assessment_tax = _clean_amount(m.group(1))

        taxes_paid = TaxesPaid(
            tds_salary=tds_salary,
            tds_non_salary=tds_non_salary,
            tcs=tcs,
            advance_tax_instalments=advance_tax,
            self_assessment_tax=self_assessment_tax,
        )

        evidence.append(
            SourceEvidence(
                field_name="taxes_paid",
                source_document="Form26AS",
                page_number=1,
                confidence=0.98,
                raw_text="Form 26AS Tax Credit Statement",
            )
        )

        return taxes_paid, evidence
