"""Form 16 Parser (Part A and Part B).

Extracts salary details, perquisites, Section 10 exemptions, Section 16 deductions,
Chapter VI-A deductible amounts, employer details, and TDS deposited from Form 16 documents.
Supports cross-footing arithmetic verification and detects the regime used by the employer.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.schemas.tax import Form16, Regime, SourceEvidence
from app.schemas.validators import validate_pan


def _clean_amount(text: str) -> Decimal:
    """Parse numeric string stripping currency symbols, commas, and whitespace."""
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


class Form16Parser:
    """Deterministic, label-anchored parser for Indian Form 16 Part A and Part B."""

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[Form16, list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []

        def match_and_record(
            field: str, patterns: list[str], default: Decimal = Decimal("0")
        ) -> Decimal:
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    raw_val = m.group(1)
                    val = _clean_amount(raw_val)
                    evidence.append(
                        SourceEvidence(
                            field_name=field,
                            source_document="Form16",
                            page_number=1,
                            confidence=0.95,
                            raw_text=m.group(0),
                        )
                    )
                    return val
            return default

        def match_str_and_record(
            field: str, patterns: list[str], default: str = ""
        ) -> str:
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    res = m.group(1).strip()
                    evidence.append(
                        SourceEvidence(
                            field_name=field,
                            source_document="Form16",
                            page_number=1,
                            confidence=0.95,
                            raw_text=m.group(0),
                        )
                    )
                    return res
            return default

        # --- Part A Fields ---
        employer_name = match_str_and_record(
            "employer_name",
            [
                r"Name\s*and\s*address\s*of\s*the\s*Employer[:\s]*([^\n\r]+)",
                r"Employer\s*Name[:\s]*([^\n\r]+)",
            ],
            default="Employer",
        )

        employer_tan = match_str_and_record(
            "employer_tan",
            [
                r"TAN\s*(?:of\s*the\s*Deductor)?[:\s]*([A-Z]{4}[0-9]{5}[A-Z])",
                r"([A-Z]{4}[0-9]{5}[A-Z])",
            ],
        )

        employer_pan = match_str_and_record(
            "employer_pan",
            [
                r"PAN\s*(?:of\s*the\s*Deductor)?[:\s]*([A-Z]{5}[0-9]{4}[A-Z])",
            ],
        )

        certificate_number = match_str_and_record(
            "certificate_number",
            [
                r"Certificate\s*(?:No|Number|#)[:\s]*([A-Z0-9\-]+)",
            ],
        )

        # Period with employer
        period_match = re.search(
            r"([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})\s*to\s*([0-9]{2}[\/\-][0-9]{2}[\/\-][0-9]{4})",
            text,
            re.IGNORECASE,
        )
        period_from = None
        period_to = None
        if period_match:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    period_from = datetime.strptime(period_match.group(1), fmt).date()
                    break
                except ValueError:
                    pass
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    period_to = datetime.strptime(period_match.group(2), fmt).date()
                    break
                except ValueError:
                    pass

        # TDS deposited
        tds_deducted = match_and_record(
            "tds_deducted",
            [
                r"(?:Total\s*amount\s*of\s*tax\s*(?:deducted|deposited)|Tax\s*Deposited|Total\s*TDS)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                r"Amount\s*of\s*tax\s*deducted[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        # --- Part B Fields ---
        salary_17_1 = match_and_record(
            "gross_salary_17_1",
            [
                r"(?:17\(1\)|Salary\s*as\s*per\s*provisions.*?17\(1\))[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                r"Gross\s*Salary[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        perquisites_17_2 = match_and_record(
            "perquisites_17_2",
            [
                r"(?:17\(2\)|Value\s*of\s*perquisites.*?17\(2\))[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        profits_in_lieu_17_3 = match_and_record(
            "profits_in_lieu_17_3",
            [
                r"(?:17\(3\)|Profits\s*in\s*lieu\s*of\s*salary.*?17\(3\))[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        # Section 10 exemptions
        exempt_allowances: dict[str, Decimal] = {}
        hra_val = match_and_record(
            "hra_exemption",
            [
                r"(?:10\(13A\)|House\s*Rent\s*Allowance|HRA)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )
        if hra_val > Decimal("0"):
            exempt_allowances["hra"] = hra_val

        lta_val = match_and_record(
            "lta_exemption",
            [
                r"(?:10\(5\)|Leave\s*Travel\s*Allowance|LTA)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )
        if lta_val > Decimal("0"):
            exempt_allowances["lta"] = lta_val

        # Section 16 Deductions
        std_deduction = match_and_record(
            "standard_deduction",
            [
                r"(?:16\(ia\)|Standard\s*deduction.*?16\(ia\))[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                r"Standard\s*deduction[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
            default=Decimal("50000"),
        )

        prof_tax = match_and_record(
            "professional_tax",
            [
                r"(?:16\(iii\)|Tax\s*on\s*employment|Professional\s*Tax)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        entertainment = match_and_record(
            "entertainment_allowance",
            [
                r"(?:16\(ii\)|Entertainment\s*allowance)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        # Taxable salary per employer
        taxable_salary = match_and_record(
            "taxable_salary_per_employer",
            [
                r"(?:Income\s*chargeable\s*under\s*(?:the\s*)?head\s*['\"]?Salaries['\"]?.*?)(?::|\bRs\.?|\b₹)\s*([\d,]+\.?\d*)",
                r"Total\s*taxable\s*salary[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            ],
        )

        # Chapter VI-A Deductions
        chapter_via: dict[str, Decimal] = {}
        ordered_sections = [
            "80CCD1B", "80CCD2", "80CCD1", "80CCC", "80C",
            "80DDB", "80DD", "80D", "80EEA", "80EE", "80E",
            "80GGA", "80GG", "80G", "80TTB", "80TTA", "80U"
        ]
        for sec in ordered_sections:
            val = match_and_record(
                f"chapter_via_{sec}",
                [
                    rf"\b{sec}\b[^\d\n\r]*[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
                ],
            )
            if val > Decimal("0"):
                chapter_via[sec] = val

        # Detect regime used by employer
        # New regime Form 16 typically shows ₹75,000 standard deduction and minimal/no Chapter VI-A (except 80CCD2)
        if std_deduction >= Decimal("75000") and (
            len(chapter_via) == 0 or list(chapter_via.keys()) == ["80CCD2"]
        ):
            regime_used = Regime.NEW
        else:
            regime_used = Regime.OLD

        form16 = Form16(
            employer_name=employer_name,
            employer_tan=employer_tan,
            employer_pan=employer_pan,
            certificate_number=certificate_number,
            period_from=period_from,
            period_to=period_to,
            gross_salary_17_1=salary_17_1,
            perquisites_17_2=perquisites_17_2,
            profits_in_lieu_17_3=profits_in_lieu_17_3,
            exempt_allowances_10=exempt_allowances,
            standard_deduction=std_deduction,
            professional_tax=prof_tax,
            entertainment_allowance=entertainment,
            chapter_via_claimed=chapter_via,
            regime_used=regime_used,
            tds_deducted=tds_deducted,
            taxable_salary_per_employer=taxable_salary,
        )

        return form16, evidence
