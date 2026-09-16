"""Certificate and Receipt Parsers.

Extracts:
1. Bank Interest Certificates (savings interest, term deposit interest, TDS 194A).
2. Home Loan Provisional/Interest Certificates (principal 80C, interest 24(b), co-ownership).
3. Rent Receipts (monthly rent, landlord PAN, landlord name, address).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.schemas.tax import HouseProperty, SalaryBreakup, SourceEvidence


def _clean_amount(text: str) -> Decimal:
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


class InterestCertificateParser:
    """Parses Bank Interest Certificates."""

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[dict[str, Decimal], list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []
        result = {
            "savings_interest": Decimal("0"),
            "fd_interest": Decimal("0"),
            "tds_194a": Decimal("0"),
        }

        # Savings interest
        m_sb = re.search(
            r"(?:Savings\s*(?:Bank\s*)?(?:Account\s*)?(?:Interest\s*(?:Credited)?)?|SB\s*Interest|Interest\s*Credited\s*on\s*Savings)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_sb:
            result["savings_interest"] = _clean_amount(m_sb.group(1))

        # FD / Term deposit interest
        m_fd = re.search(
            r"(?:Fixed\s*Deposit|Term\s*Deposit|FD\s*Interest|TDR\s*Interest)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_fd:
            result["fd_interest"] = _clean_amount(m_fd.group(1))

        # TDS u/s 194A
        m_tds = re.search(
            r"(?:TDS\s*(?:deducted)?\s*u/s\s*194A|TDS\s*Amount)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_tds:
            result["tds_194a"] = _clean_amount(m_tds.group(1))

        evidence.append(
            SourceEvidence(
                field_name="interest_certificate",
                source_document="InterestCertificate",
                page_number=1,
                confidence=0.95,
                raw_text="Bank Interest Certificate",
            )
        )

        return result, evidence


class HomeLoanCertificateParser:
    """Parses Home Loan Interest Certificates."""

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[HouseProperty, list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []

        # Principal repaid (eligible u/s 80C)
        principal = Decimal("0")
        m_p = re.search(
            r"(?:Principal.*?(?:Repaid|Amount|component)?.*?)(?::|\bRs\.?|\b₹)\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_p:
            principal = _clean_amount(m_p.group(1))

        # Interest paid/payable (eligible u/s 24(b))
        interest = Decimal("0")
        m_i = re.search(
            r"(?:Interest.*?(?:Paid|Payable|component)?.*?)(?::|\bRs\.?|\b₹)\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_i:
            interest = _clean_amount(m_i.group(1))

        # Co-owner share
        share = Decimal("1")
        m_share = re.search(
            r"(?:Share|Ownership\s*Share)[:\s]*([\d.]+)%?",
            text,
            re.IGNORECASE,
        )
        if m_share:
            val = _clean_amount(m_share.group(1))
            if val > Decimal("1"):
                share = val / Decimal("100")
            elif val > Decimal("0"):
                share = val

        # Self-occupied vs let-out
        is_self_occupied = True
        if re.search(r"Let[- ]out", text, re.IGNORECASE):
            is_self_occupied = False

        hp = HouseProperty(
            is_self_occupied=is_self_occupied,
            is_let_out=not is_self_occupied,
            interest_on_loan_24b=interest,
            principal_repaid_80c=principal,
            co_owner_share=share,
        )

        evidence.append(
            SourceEvidence(
                field_name="house_property_loan",
                source_document="HomeLoanCertificate",
                page_number=1,
                confidence=0.95,
                raw_text=f"Home loan interest: ₹{interest}, Principal: ₹{principal}, Share: {share}",
            )
        )

        return hp, evidence


class RentReceiptParser:
    """Parses Rent Receipts."""

    def parse(
        self, text: str, page_images: list[Any] | None = None
    ) -> tuple[dict[str, Any], list[SourceEvidence]]:
        evidence: list[SourceEvidence] = []
        result = {
            "annual_rent": Decimal("0"),
            "monthly_rent": Decimal("0"),
            "landlord_pan": "",
            "landlord_name": "",
            "is_metro": False,
        }

        m_amt = re.search(
            r"(?:Rent\s*Paid|Amount|Received\s*a\s*sum\s*of)[:\s]*(?:₹|Rs\.?)?\s*([\d,]+\.?\d*)",
            text,
            re.IGNORECASE,
        )
        if m_amt:
            amt = _clean_amount(m_amt.group(1))
            if "per month" in text.lower() or "monthly" in text.lower():
                result["monthly_rent"] = amt
                result["annual_rent"] = amt * Decimal("12")
            else:
                result["annual_rent"] = amt
                result["monthly_rent"] = amt / Decimal("12")

        # Landlord PAN
        m_pan = re.search(
            r"(?:Landlord\s*PAN|PAN\s*of\s*Landlord|PAN)[:\s]*([A-Z]{5}[0-9]{4}[A-Z])",
            text,
            re.IGNORECASE,
        )
        if m_pan:
            result["landlord_pan"] = m_pan.group(1).upper()

        # Metro check
        if re.search(r"\b(Mumbai|Delhi|Kolkata|Chennai|New Delhi)\b", text, re.IGNORECASE):
            result["is_metro"] = True

        evidence.append(
            SourceEvidence(
                field_name="rent_receipts",
                source_document="RentReceipt",
                page_number=1,
                confidence=0.95,
                raw_text=f"Rent: ₹{result['annual_rent']}, Landlord PAN: {result['landlord_pan']}",
            )
        )

        return result, evidence
