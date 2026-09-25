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

    @staticmethod
    def _cell_lines(
        page_words: list[list[tuple[float, float, float, float, str]]],
        page_index: int,
        rect: tuple[float, float, float, float],
    ) -> list[str]:
        if page_index >= len(page_words):
            return []
        x0, y0, x1, y1 = rect
        selected = []
        for wx0, wy0, wx1, wy1, word in page_words[page_index]:
            cx = (wx0 + wx1) / 2
            cy = (wy0 + wy1) / 2
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                selected.append((wy0, wx0, word))
        selected.sort()
        lines: list[list[tuple[float, str]]] = []
        line_y: list[float] = []
        for wy0, wx0, word in selected:
            if not line_y or abs(wy0 - line_y[-1]) > 2.5:
                line_y.append(wy0)
                lines.append([])
            lines[-1].append((wx0, word))
        return [
            " ".join(word for _, word in sorted(line)).strip()
            for line in lines
            if line
        ]

    @classmethod
    def extract_employee_name(
        cls,
        page_words: list[list[tuple[float, float, float, float, str]]],
    ) -> str:
        lines = cls._cell_lines(page_words, 0, (276, 251, 540, 274))
        return lines[0] if lines else ""

    @classmethod
    def _extract_official_table_fields(
        cls,
        page_words: list[list[tuple[float, float, float, float, str]]],
    ) -> dict[str, Any]:
        """Read the fixed cells of the current CBDT Form 16 table layout."""
        if len(page_words) < 4:
            return {}

        def first_line(page: int, rect: tuple[float, float, float, float]) -> str:
            lines = cls._cell_lines(page_words, page, rect)
            return lines[0] if lines else ""

        def amount(
            page: int, rect: tuple[float, float, float, float]
        ) -> Decimal:
            for line in cls._cell_lines(page_words, page, rect):
                for token in line.split():
                    if re.fullmatch(r"\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?", token):
                        negative = token.startswith("(") and token.endswith(")")
                        value = _clean_amount(token)
                        return -value if negative else value
            return Decimal("0")

        fields: dict[str, Any] = {
            "certificate_number": first_line(0, (60, 211, 276, 229)),
            "employer_name": first_line(0, (60, 251, 276, 274)),
            "employee_name": first_line(0, (276, 251, 540, 274)),
            "tds_deducted": amount(0, (350, 566, 426, 585)),
            "gross_salary_17_1": amount(1, (430, 507, 547, 530)),
            "perquisites_17_2": amount(1, (430, 529, 547, 565)),
            "profits_in_lieu_17_3": amount(1, (430, 564, 547, 597)),
            "standard_deduction": amount(2, (378, 211, 431, 231)),
            "professional_tax": amount(2, (378, 241, 431, 256)),
            "entertainment_allowance": amount(2, (378, 228, 431, 244)),
            "taxable_salary_per_employer": amount(2, (431, 274, 547, 294)),
        }

        # Fallback to Part B Row 19 (Net TDS deducted) or first summary row
        if fields["tds_deducted"] == Decimal("0") and len(page_words) >= 4:
            fields["tds_deducted"] = amount(3, (430, 483, 547, 510))
        if fields["tds_deducted"] == Decimal("0"):
            fields["tds_deducted"] = amount(0, (350, 526, 426, 548))

        # Row 7(a) & 7(b): Other income / House property loss reported by employee
        hp_loss = amount(2, (430, 303, 547, 328))
        if hp_loss == Decimal("0"):
            hp_loss = amount(2, (378, 303, 431, 328))
        fields["reported_house_property_loss"] = abs(hp_loss)

        other_inc = amount(2, (430, 327, 547, 341))
        if other_inc == Decimal("0"):
            other_inc = amount(2, (378, 327, 431, 341))
        fields["reported_other_income"] = other_inc
        fields["reported_savings_interest"] = amount(3, (333, 110, 378, 151))
        fields["relief_89"] = amount(3, (430, 460, 547, 483))

        hra = amount(1, (430, 711, 547, 744))
        lta = amount(1, (430, 647, 547, 671))
        fields["exempt_allowances_10"] = {
            key: value
            for key, value in (("hra", hra), ("lta", lta))
            if value > Decimal("0")
        }

        deduction_cells = {
            "80C": (2, (431, 414, 547, 459)),
            "80CCC": (2, (431, 457, 547, 498)),
            "80CCD1": (2, (431, 496, 547, 538)),
            "80CCD1B": (2, (431, 561, 547, 603)),
            "80CCD2": (2, (431, 600, 547, 642)),
            "80D": (2, (431, 639, 547, 681)),
            "80E": (2, (431, 678, 547, 721)),
            "80G": (3, (431, 69, 547, 113)),
            "80TTA": (3, (431, 110, 547, 151)),
        }
        fields["chapter_via_claimed"] = {
            section: value
            for section, (page, rect) in deduction_cells.items()
            if (value := amount(page, rect)) > Decimal("0")
        }

        period_lines = cls._cell_lines(page_words, 0, (385, 373, 541, 397))
        dates = re.findall(
            r"\b[0-9]{2}/[0-9]{2}/[0-9]{4}\b", " ".join(period_lines)
        )
        if len(dates) >= 2:
            fields["period_from"] = datetime.strptime(dates[0], "%d/%m/%Y").date()
            fields["period_to"] = datetime.strptime(dates[1], "%d/%m/%Y").date()
        return fields

    @staticmethod
    def extract_employee_pan(text: str) -> str:
        """Return the employee's PAN from regular or table-layout Form 16 text.

        In the official table layout, PDF extraction commonly puts the PAN labels
        before every entered value.  The fallback therefore selects a valid
        individual PAN token (fourth character ``P``), excluding employer PANs.
        """
        labelled_patterns = (
            r"PAN\s*(?:of\s*(?:the\s*)?Employee|of\s*Employee)\s*[:\-]?\s*([A-Z]{5}\s*[0-9]{4}\s*[A-Z])",
            r"Employee\s*PAN\s*[:\-]?\s*([A-Z]{5}\s*[0-9]{4}\s*[A-Z])",
        )
        for pattern in labelled_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = re.sub(r"\s+", "", match.group(1)).upper()
                if validate_pan(candidate, individual_only=True):
                    return candidate

        candidates: list[str] = []
        for match in re.finditer(r"\b([A-Z]{5}\s*[0-9]{4}\s*[A-Z])\b", text, re.IGNORECASE):
            candidate = re.sub(r"\s+", "", match.group(1)).upper()
            if validate_pan(candidate, individual_only=True) and candidate not in candidates:
                candidates.append(candidate)
        return candidates[0] if candidates else ""

    def parse(
        self,
        text: str,
        page_images: list[Any] | None = None,
        page_words: list[list[tuple[float, float, float, float, str]]] | None = None,
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

        employee_pan = self.extract_employee_pan(text)
        if employee_pan:
            evidence.append(
                SourceEvidence(
                    field_name="employee_pan",
                    source_document="Form16",
                    page_number=1,
                    confidence=0.95,
                    raw_text=employee_pan,
                )
            )

        employee_name = match_str_and_record(
            "employee_name",
            [
                r"Name\s*(?:and\s*Designation)?\s*of\s*the\s*Employee\s*[:\s]*([^\n\r]+)",
                r"Employee\s*Name\s*[:\s]*([^\n\r]+)",
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

        table_fields = self._extract_official_table_fields(page_words or [])
        if table_fields:
            employer_name = table_fields.get("employer_name") or employer_name
            certificate_number = (
                table_fields.get("certificate_number") or certificate_number
            )
            period_from = table_fields.get("period_from") or period_from
            period_to = table_fields.get("period_to") or period_to
            salary_17_1 = table_fields.get("gross_salary_17_1", salary_17_1)
            perquisites_17_2 = table_fields.get(
                "perquisites_17_2", perquisites_17_2
            )
            profits_in_lieu_17_3 = table_fields.get(
                "profits_in_lieu_17_3", profits_in_lieu_17_3
            )
            std_deduction = table_fields.get(
                "standard_deduction", std_deduction
            )
            prof_tax = table_fields.get("professional_tax", prof_tax)
            entertainment = table_fields.get(
                "entertainment_allowance", entertainment
            )
            taxable_salary = table_fields.get(
                "taxable_salary_per_employer", taxable_salary
            )
            tds_deducted = table_fields.get("tds_deducted", tds_deducted)
            exempt_allowances = table_fields.get(
                "exempt_allowances_10", exempt_allowances
            )
            chapter_via = table_fields.get(
                "chapter_via_claimed", chapter_via
            )

            for field_name, value in table_fields.items():
                if field_name == "employee_name" or value in (None, "", {}, Decimal("0")):
                    continue
                evidence.append(
                    SourceEvidence(
                        field_name=field_name,
                        source_document="Form16",
                        page_number=1,
                        confidence=0.99,
                        raw_text=str(value),
                    )
                )

        # Detect regime used by employer
        # New regime Form 16 typically shows ₹75,000 standard deduction and minimal/no Chapter VI-A (except 80CCD2)
        if std_deduction >= Decimal("75000") and (
            len(chapter_via) == 0 or list(chapter_via.keys()) == ["80CCD2"]
        ):
            regime_used = Regime.NEW
        else:
            regime_used = Regime.OLD

        reported_hp_loss = (
            table_fields.get("reported_house_property_loss", Decimal("0"))
            if table_fields
            else Decimal("0")
        )
        reported_other_inc = (
            table_fields.get("reported_other_income", Decimal("0"))
            if table_fields
            else Decimal("0")
        )
        reported_savings_interest = (
            table_fields.get("reported_savings_interest", Decimal("0"))
            if table_fields
            else Decimal("0")
        )

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
            reported_house_property_loss=reported_hp_loss,
            reported_other_income=reported_other_inc,
            reported_savings_interest=reported_savings_interest,
            relief_89=table_fields.get("relief_89", Decimal("0")) if table_fields else Decimal("0"),
        )

        return form16, evidence
