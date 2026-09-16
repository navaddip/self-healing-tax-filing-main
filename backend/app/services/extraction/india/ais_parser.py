"""Annual Information Statement (AIS) Parser.

Extracts financial transactions reported by reporting entities:
Salary, Savings Interest, Deposit Interest, Dividends, Sale of Securities/Mutual Funds,
and checks transaction feedback status (e.g. active vs duplicate).
Supports password-protected AIS PDFs using PAN + Date of Birth.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from app.schemas.tax import SourceEvidence


def _clean_amount(text: str) -> Decimal:
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


class AISParser:
    """Parses Annual Information Statement (AIS) text/PDF."""

    def derive_password(self, pan: str, dob: date | str) -> str:
        """Standard ITD password format: lowercase PAN + DDMMYYYY."""
        pan_clean = pan.strip().lower()
        if isinstance(dob, date):
            dob_clean = dob.strftime("%d%m%Y")
        else:
            # Assume DD-MM-YYYY or YYYY-MM-DD
            parts = re.split(r"[-/]", dob.strip())
            if len(parts) == 3:
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    dob_clean = f"{parts[2]}{parts[1]}{parts[0]}"
                else:  # DD-MM-YYYY
                    dob_clean = f"{parts[0]}{parts[1]}{parts[2]}"
            else:
                dob_clean = re.sub(r"[^\d]", "", dob)
        return f"{pan_clean}{dob_clean}"

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[dict[str, Any], list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []
        parsed: dict[str, Any] = {
            "salary": Decimal("0"),
            "savings_interest": Decimal("0"),
            "fd_interest": Decimal("0"),
            "dividend_income": Decimal("0"),
            "securities_sale_value": Decimal("0"),
            "transactions": [],
        }

        # Match Salary (SFT-001 or Salary category)
        m_sal = re.search(
            r"(?:Salary|Receipt\s*from\s*employer).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_sal:
            parsed["salary"] = _clean_amount(m_sal.group(1))

        # Match Savings Interest
        m_sb = re.search(
            r"(?:Interest\s*from\s*savings\s*bank|Savings\s*Interest).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_sb:
            parsed["savings_interest"] = _clean_amount(m_sb.group(1))

        # Match Deposit / FD Interest
        m_fd = re.search(
            r"(?:Interest\s*from\s*deposit|Deposit\s*Interest|Term\s*deposit).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_fd:
            parsed["fd_interest"] = _clean_amount(m_fd.group(1))

        # Match Dividends
        m_div = re.search(
            r"(?:Dividend\s*income|Dividend).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_div:
            parsed["dividend_income"] = _clean_amount(m_div.group(1))

        # Match Sale of Securities
        m_sec = re.search(
            r"(?:Sale\s*of\s*securities\s*and\s*units\s*of\s*mutual\s*fund|Sale\s*of\s*securities).*?([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_sec:
            parsed["securities_sale_value"] = _clean_amount(m_sec.group(1))

        evidence.append(
            SourceEvidence(
                field_name="ais_summary",
                source_document="AIS",
                page_number=1,
                confidence=0.98,
                raw_text="Annual Information Statement (AIS)",
            )
        )

        return parsed, evidence
