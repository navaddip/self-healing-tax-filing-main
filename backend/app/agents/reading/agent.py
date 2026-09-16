"""Document Reading Agent for Indian Tax Documents.

Extracts facts from Form 16 (Part A & Part B), Form 26AS, AIS, Broker P&L,
and certificates (Home Loan, Bank Interest, Rent Receipts).
Applies cross-footing arithmetic checks, multi-document merging, and confidence scoring.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.schemas.tax import (
    AuditEntry,
    Form16,
    IndianTaxpayerData,
    SourceEvidence,
    TaxesPaid,
)
from app.services.chroma.service import ChromaService
from app.services.documents.service import DocumentService
from app.services.extraction.india.ais_parser import AISParser
from app.services.extraction.india.broker_pnl_parser import BrokerPnLParser
from app.services.extraction.india.certificate_parsers import (
    HomeLoanCertificateParser,
    InterestCertificateParser,
    RentReceiptParser,
)
from app.services.extraction.india.form16_parser import Form16Parser
from app.services.extraction.india.form26as_parser import Form26ASParser
from app.services.ocr.service import OCRService
from app.services.ollama.client import OllamaClient


class ReadingAgent:
    name = "Reading Agent (India)"

    def __init__(
        self,
        documents: DocumentService | None = None,
        ocr: OCRService | None = None,
        default_state_tax_rate: float = 0.0,
        memory: ChromaService | None = None,
        w2_extractor: Any | None = None,
        ollama: OllamaClient | None = None,
    ):
        self.documents = documents or DocumentService()
        self.ocr = ocr or OCRService()
        self.memory = memory
        self.ollama = ollama

        # Parsers
        self.form16_parser = Form16Parser()
        self.form26as_parser = Form26ASParser()
        self.ais_parser = AISParser()
        self.broker_parser = BrokerPnLParser()
        self.interest_parser = InterestCertificateParser()
        self.home_loan_parser = HomeLoanCertificateParser()
        self.rent_parser = RentReceiptParser()

    def run_many(
        self, paths: list[Path], scale: int = 2
    ) -> tuple[IndianTaxpayerData, str, list[AuditEntry]]:
        """Read several documents and merge them into one IndianTaxpayerData return."""
        datas: list[IndianTaxpayerData] = []
        texts: list[str] = []
        logs: list[AuditEntry] = []

        for path in paths:
            data, text, page_logs = self.run(path, scale=scale)
            datas.append(data)
            texts.append(text)
            logs.extend(page_logs)

        merged = self._merge(datas)
        if len(datas) > 1:
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="merge_documents",
                    reason="Combine Form 16s, 26AS, AIS and statements into unified return",
                    details={
                        "documents_count": len(datas),
                        "form16_count": len(merged.form16s),
                    },
                )
            )
        return merged, "\n".join(texts), logs

    def run(
        self, path: Path, scale: int = 2
    ) -> tuple[IndianTaxpayerData, str, list[AuditEntry]]:
        path = Path(path)
        logs: list[AuditEntry] = []
        combined_text = ""

        # Handle CSV directly (e.g. Broker P&L)
        if path.suffix.lower() in (".csv", ".txt") and "pnl" in path.name.lower():
            try:
                csv_content = path.read_text(encoding="utf-8")
            except Exception:
                csv_content = path.read_text(encoding="latin-1")
            items, ev, warnings = self.broker_parser.parse_csv(csv_content)
            data = IndianTaxpayerData(capital_gains=items, evidence=ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_broker_pnl",
                    reason=f"Parsed {len(items)} capital gain transactions",
                    details={"items": len(items), "warnings": warnings},
                )
            )
            return data, csv_content, logs

        # PDF / Image loading
        pages = self.documents.load(path, scale=scale)
        page_texts: list[str] = []
        page_images = []

        for page in pages:
            image_ocr = self.ocr.extract(page.image, "")
            text = page.embedded_text or image_ocr.text
            page_texts.append(text)
            page_images.append(page.image)

        combined_text = "\n".join(page_texts)

        # Classify document type based on header anchors
        doc_type = self._classify_document(combined_text)

        data = IndianTaxpayerData()

        if doc_type == "Form16":
            form16, ev = self.form16_parser.parse(combined_text, page_images)
            cross_foot_ok = self._verify_form16_cross_foot(form16)
            confidence = 0.98 if cross_foot_ok else 0.70

            for e in ev:
                e.confidence = confidence
                data.field_confidence[e.field_name] = confidence

            data.form16s.append(form16)
            data.evidence.extend(ev)
            data.aggregate_form16s()

            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_form16",
                    reason="Extracted Form 16 Part A/B salary details",
                    details={
                        "employer": form16.employer_name,
                        "gross_salary": str(form16.gross_salary_17_1),
                        "cross_foot_verified": cross_foot_ok,
                    },
                )
            )

        elif doc_type == "Form26AS":
            taxes_paid, ev = self.form26as_parser.parse(combined_text, page_images)
            data.taxes_paid = taxes_paid
            data.evidence.extend(ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_form26as",
                    reason="Extracted Form 26AS tax credits",
                    details={
                        "tds_salary": str(taxes_paid.tds_salary),
                        "tds_non_salary": str(taxes_paid.tds_non_salary),
                    },
                )
            )

        elif doc_type == "AIS":
            ais_dict, ev = self.ais_parser.parse(combined_text, page_images)
            data.savings_interest = ais_dict.get("savings_interest", Decimal("0"))
            data.fd_interest = ais_dict.get("fd_interest", Decimal("0"))
            data.dividend_income = ais_dict.get("dividend_income", Decimal("0"))
            data.evidence.extend(ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_ais",
                    reason="Extracted AIS reported incomes",
                    details=ais_dict,
                )
            )

        elif doc_type == "HomeLoanCertificate":
            hp, ev = self.home_loan_parser.parse(combined_text, page_images)
            data.house_properties.append(hp)
            if hp.principal_repaid_80c > Decimal("0"):
                data.deduction_claims["80C"] = max(
                    data.deduction_claims.get("80C", Decimal("0")),
                    hp.principal_repaid_80c,
                )
            data.evidence.extend(ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_home_loan",
                    reason="Extracted Home Loan interest and principal certificate",
                    details={"interest_24b": str(hp.interest_on_loan_24b)},
                )
            )

        elif doc_type == "InterestCertificate":
            interest_dict, ev = self.interest_parser.parse(combined_text, page_images)
            data.savings_interest += interest_dict.get("savings_interest", Decimal("0"))
            data.fd_interest += interest_dict.get("fd_interest", Decimal("0"))
            data.taxes_paid.tds_non_salary += interest_dict.get("tds_194a", Decimal("0"))
            data.evidence.extend(ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_interest_certificate",
                    reason="Extracted bank interest and TDS",
                    details=interest_dict,
                )
            )

        elif doc_type == "RentReceipt":
            rent_dict, ev = self.rent_parser.parse(combined_text, page_images)
            if data.salary_breakup:
                data.salary_breakup.rent_paid_annual = rent_dict["annual_rent"]
                data.salary_breakup.landlord_pan = rent_dict["landlord_pan"]
                data.salary_breakup.is_metro = rent_dict["is_metro"]
            data.evidence.extend(ev)
            logs.append(
                AuditEntry(
                    agent=self.name,
                    action="extract_rent_receipt",
                    reason="Extracted rent payments and landlord PAN",
                    details=rent_dict,
                )
            )

        else:
            # Fallback: attempt Form 16 extraction
            form16, ev = self.form16_parser.parse(combined_text, page_images)
            if form16.gross_salary_17_1 > Decimal("0"):
                data.form16s.append(form16)
                data.evidence.extend(ev)
                data.aggregate_form16s()

        return data, combined_text, logs

    def _classify_document(self, text: str) -> str:
        """Classifies document by key authoritative anchors."""
        text_lower = text.lower()
        if "form no. 16" in text_lower or "part a" in text_lower and "certificate under section 203" in text_lower or "17(1)" in text:
            return "Form16"
        if "form 26as" in text_lower or "annual tax statement" in text_lower:
            return "Form26AS"
        if "annual information statement" in text_lower or "ais" in text_lower and "sft" in text_lower:
            return "AIS"
        if "housing loan" in text_lower or "home loan" in text_lower and ("principal" in text_lower or "interest" in text_lower):
            return "HomeLoanCertificate"
        if "interest certificate" in text_lower or "tdr interest" in text_lower:
            return "InterestCertificate"
        if "rent receipt" in text_lower or "landlord" in text_lower and "rent" in text_lower:
            return "RentReceipt"
        return "Unknown"

    def _verify_form16_cross_foot(self, form16: Form16) -> bool:
        """Verify internal mathematical consistency of Form 16."""
        # 1. Gross salary cross-foot
        gross = form16.gross_salary_17_1 + form16.perquisites_17_2 + form16.profits_in_lieu_17_3
        # 2. Net salary cross-foot if taxable_salary_per_employer is extracted
        if form16.taxable_salary_per_employer > Decimal("0"):
            sec10_total = sum(form16.exempt_allowances_10.values())
            sec16_total = form16.standard_deduction + form16.professional_tax + form16.entertainment_allowance
            expected_taxable = max(Decimal("0"), gross - sec10_total - sec16_total)
            diff = abs(expected_taxable - form16.taxable_salary_per_employer)
            # Allow minor rounding discrepancy up to ₹10
            return diff <= Decimal("10")
        return True

    def _merge(self, datas: list[IndianTaxpayerData]) -> IndianTaxpayerData:
        """Merge multiple document extractions into one consolidated return."""
        if len(datas) == 1:
            return datas[0]

        merged = datas[0].model_copy(deep=True)

        for d in datas[1:]:
            # Form 16s
            merged.form16s.extend(d.form16s)
            # House properties
            merged.house_properties.extend(d.house_properties)
            # Capital gains
            merged.capital_gains.extend(d.capital_gains)
            # Incomes
            merged.savings_interest += d.savings_interest
            merged.fd_interest += d.fd_interest
            merged.dividend_income += d.dividend_income
            merged.family_pension += d.family_pension
            merged.other_income += d.other_income
            merged.winnings_115bb += d.winnings_115bb

            # Deductions
            for k, v in d.deduction_claims.items():
                merged.deduction_claims[k] = max(
                    merged.deduction_claims.get(k, Decimal("0")), v
                )

            # Taxes Paid
            merged.taxes_paid.tds_salary += d.taxes_paid.tds_salary
            merged.taxes_paid.tds_non_salary += d.taxes_paid.tds_non_salary
            merged.taxes_paid.tcs += d.taxes_paid.tcs
            merged.taxes_paid.self_assessment_tax += d.taxes_paid.self_assessment_tax
            merged.taxes_paid.advance_tax_instalments.update(
                d.taxes_paid.advance_tax_instalments
            )

            # Evidence and confidence
            merged.evidence.extend(d.evidence)
            for k, conf in d.field_confidence.items():
                merged.field_confidence[k] = max(
                    merged.field_confidence.get(k, 0.0), conf
                )

            # Identity details
            if not merged.name and d.name:
                merged.name = d.name
            if not merged.pan and d.pan:
                merged.pan = d.pan
            if not merged.salary_breakup and d.salary_breakup:
                merged.salary_breakup = d.salary_breakup

        merged.aggregate_form16s()
        return merged
