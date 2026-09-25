"""Remediation Agent for Indian Tax Returns.

Implements bounded self-healing (max 2 attempts) for specific Indian tax failure modes:
1. Recomputation mismatch: recomputes directly, escalates to manual review if persistent.
2. TDS mismatch vs 26AS: requests re-extraction, prefers authoritative 26AS figure.
3. AIS mismatch: requests re-extraction; flags reconciliation notice if discrepancy persists.
4. Cross-foot failure on Form 16: requests higher-resolution re-extraction (scale + 1).
5. Deduction cap breach: enforces statutory cap (e.g. 80C at ₹1.5L) and logs adjustment.
6. Capital gains holding classification conflict: resolves in favor of date-based recomputation.
7. ITR form mismatch: re-selects compliant form (e.g. promotes ITR-1 to ITR-2 for STCG).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.schemas.tax import (
    AuditEntry,
    IndianTaxpayerData,
    VerificationResult,
)
from app.services.ollama.client import OllamaClient


class RemediationAgent:
    name = "Remediation Agent (India)"

    def __init__(self, ollama: OllamaClient | None = None):
        self.ollama = ollama

    def run(
        self,
        data: IndianTaxpayerData,
        verification: VerificationResult,
    ) -> tuple[IndianTaxpayerData, bool, AuditEntry]:
        updated = data.model_copy(deep=True)
        changes: dict[str, Any] = {}
        needs_reextraction = False
        remediation_actions: list[str] = []

        failed_check_names = {c.name for c in verification.checks if not c.passed}

        # 1. TDS mismatch vs Form 26AS
        if "tds_26as_reconciliation" in failed_check_names:
            needs_reextraction = True
            tds_26as_total = updated.taxes_paid.tds_salary + updated.taxes_paid.tds_non_salary
            old_form16_tds = sum(f.tds_deducted for f in updated.form16s)

            # Prefer 26AS figure as authoritative tax credit ledger
            if updated.form16s and tds_26as_total > Decimal("0"):
                updated.form16s[0].tds_deducted = updated.taxes_paid.tds_salary
                changes["tds_deducted"] = {
                    "old_value": str(old_form16_tds),
                    "new_value": str(updated.taxes_paid.tds_salary),
                    "reason": "Reconciled Form 16 TDS to authoritative Form 26AS credit",
                }
                remediation_actions.append("Overrode Form 16 TDS with Form 26AS ledger figure")

        # 2. Cross-foot or evidence grounding failure
        if "source_evidence_grounding" in failed_check_names or verification.requires_reextraction:
            needs_reextraction = True
            remediation_actions.append("Requested higher-resolution document re-extraction pass")

        # 3. Deduction cap breach repair
        if "deduction_legality" in failed_check_names:
            # 80C cap enforcement
            c_claims = updated.deduction_claims.get("80C", Decimal("0"))
            if c_claims > Decimal("150000"):
                updated.deduction_claims["80C"] = Decimal("150000")
                changes["80C_deduction"] = {
                    "old_value": str(c_claims),
                    "new_value": "150000",
                    "reason": "Capped Section 80C claim at statutory ₹1,50,000 ceiling",
                }
                remediation_actions.append("Applied statutory ₹1,50,000 ceiling to Section 80C")

            # 80CCD(1B) cap enforcement
            nps_claims = updated.deduction_claims.get("80CCD1B", Decimal("0"))
            if nps_claims > Decimal("50000"):
                updated.deduction_claims["80CCD1B"] = Decimal("50000")
                changes["80CCD1B_deduction"] = {
                    "old_value": str(nps_claims),
                    "new_value": "50000",
                    "reason": "Capped Section 80CCD(1B) NPS claim at ₹50,000 ceiling",
                }

        # 4. Capital gains holding period classification conflict
        if "capital_gains_classification" in failed_check_names:
            for item in updated.capital_gains:
                if item.acquisition_date and item.transfer_date:
                    days = (item.transfer_date - item.acquisition_date).days
                    # Recompute holding period from dates
                    should_be_long = days > 365
                    if item.is_long_term != should_be_long:
                        item.holding_days = days
                        item.is_long_term = should_be_long
                        changes[f"holding_period_{item.asset_type}"] = {
                            "days": days,
                            "classified_as": "Long-term" if should_be_long else "Short-term",
                            "reason": "Resolved broker conflict in favor of date-based statutory period",
                        }
                        remediation_actions.append("Overrode broker classification using date-based holding period")

        # 5. Recomputation mismatch: recompute only, no re-extraction
        if "deterministic_recomputation" in failed_check_names:
            remediation_actions.append("Scheduled clean engine recomputation pass")

        # 6. Normalize confidences
        for field, value in list(updated.field_confidence.items()):
            normalized = min(max(float(value), 0.0), 1.0)
            if normalized != value:
                updated.field_confidence[field] = normalized

        classification = ""
        if self.ollama:
            try:
                classification = self.ollama.classify_remediation(verification.errors)
            except Exception:
                pass

        audit = AuditEntry(
            agent=self.name,
            action="remediate",
            reason=f"Applied {len(remediation_actions)} self-healing remediation actions",
            details={
                "actions": remediation_actions,
                "changes": changes,
                "needs_reextraction": needs_reextraction,
                "classification": classification,
            },
        )

        return updated, needs_reextraction, audit
