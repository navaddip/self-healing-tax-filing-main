"""Official CBDT Schema Validation for ITR-1, ITR-2, and ITR-4.

Validates the structure, required fields, Indian regex patterns, and
accounting balance footings for Indian Income Tax Return JSON payloads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
TAN_REGEX = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SchemaValidationError(Exception):
    """Raised when an ITR JSON payload fails schema or mathematical checks."""


class ITRSchemaLoader:
    """Validates ITR payloads against CBDT specifications."""

    def __init__(self, schemas_dir: Path | None = None):
        if schemas_dir is None:
            schemas_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "itr_schemas"
        self.schemas_dir = schemas_dir

    def validate(self, form_name: str, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate an ITR payload dictionary.

        Returns (valid, error_list).
        """
        errors: list[str] = []
        form_upper = form_name.upper().replace("-", "")

        # 1. Root structure check
        if not isinstance(payload, dict) or "ITR" not in payload:
            return False, ["Payload missing root 'ITR' object."]

        itr_root = payload["ITR"]
        if form_upper not in itr_root:
            return False, [f"ITR root missing form section '{form_upper}'."]

        form_data = itr_root[form_upper]

        # 2. Check mandatory sections
        mandatory_sections = ["CreationInfo", "PersonalInfo", "FilingStatus", "TaxPaid", "Verification"]
        for section in mandatory_sections:
            if section not in form_data and f"PartA_GEN" not in form_data:
                errors.append(f"Missing mandatory section: '{section}'")

        # Extract PersonalInfo & FilingStatus
        if "PersonalInfo" in form_data:
            personal = form_data["PersonalInfo"]
            filing = form_data.get("FilingStatus", {})
        elif "PartA_GEN" in form_data:
            personal = form_data["PartA_GEN"].get("PersonalInfo", {})
            filing = form_data["PartA_GEN"].get("FilingStatus", {})
        else:
            personal = {}
            filing = {}

        # 3. PAN validation
        pan = personal.get("PAN")
        if not pan or not PAN_REGEX.match(pan):
            errors.append(f"Invalid PAN format: '{pan}'")

        # 4. DOB validation
        dob = personal.get("DOB")
        if not dob or not DATE_REGEX.match(dob):
            errors.append(f"Invalid DOB format: '{dob}'")

        # 5. Due date & regime choice
        if filing.get("OptOutNewTaxRegime") not in ("Y", "N"):
            errors.append("OptOutNewTaxRegime must be 'Y' or 'N'")

        # 6. Mathematical cross-footing checks
        if form_upper == "ITR1":
            inc = form_data.get("IncomeDeductions", {})
            gti = inc.get("GrossTotIncome", 0)
            ded = inc.get("DeductUndChapVIA", {}).get("TotalChapVIADeductions", 0)
            ti = inc.get("TotalIncome", 0)
            if ti != max(0, gti - ded):
                errors.append(f"ITR-1 TotalIncome ({ti}) does not match GTI ({gti}) - Deductions ({ded})")

            taxes_paid_sec = form_data.get("TaxPaid", {}).get("TaxesPaid", {})
            tot_taxes = taxes_paid_sec.get("TotalTaxesPaid", 0)
            components_sum = (
                taxes_paid_sec.get("AdvanceTax", 0)
                + taxes_paid_sec.get("TDS", 0)
                + taxes_paid_sec.get("SelfAssessmentTax", 0)
            )
            if tot_taxes != components_sum:
                errors.append(f"TotalTaxesPaid ({tot_taxes}) != AdvanceTax + TDS + SAT ({components_sum})")

        elif form_upper == "ITR2":
            part_b_ti = form_data.get("PartB_TI", {})
            gti = part_b_ti.get("GrossTotalIncome", 0)
            ded = part_b_ti.get("TotalDeductions", 0)
            ti = part_b_ti.get("TotalIncome", 0)
            if ti != max(0, gti - ded):
                errors.append(f"ITR-2 TotalIncome ({ti}) != GTI ({gti}) - Deductions ({ded})")

        elif form_upper == "ITR4":
            inc = form_data.get("IncomeDeductions", {})
            gti = inc.get("GrossTotIncome", 0)
            ded = inc.get("TotalChapVIADeductions", 0)
            ti = inc.get("TotalIncome", 0)
            if ti != max(0, gti - ded):
                errors.append(f"ITR-4 TotalIncome ({ti}) != GTI ({gti}) - Deductions ({ded})")

        return len(errors) == 0, errors


def validate_itr_json(form_name: str, payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Convenience wrapper to validate an ITR JSON payload."""
    loader = ITRSchemaLoader()
    return loader.validate(form_name, payload)
