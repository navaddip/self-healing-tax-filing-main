"""Fail-closed validation against pinned, unmodified CBDT schemas."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from jsonschema import Draft4Validator, FormatChecker

class SchemaValidationError(ValueError):
    pass


class MissingFilingData(SchemaValidationError):
    """Export blocked only because taxpayer-supplied details are missing."""

    def __init__(self, message: str, fields: list[str]):
        super().__init__(message)
        self.fields = fields

class ITRSchemaLoader:
    def __init__(self, schemas_dir: Path | None = None):
        self.schemas_dir = schemas_dir or Path(__file__).resolve().parents[2] / "assets" / "itr_schemas"

    def validate(self, form_name: str, payload: dict, assessment_year: str | None = None):
        form = form_name.upper().replace("-", "")
        if form not in {"ITR1", "ITR2", "ITR4"}:
            return False, ["Unsupported ITR form"]
        try:
            year = assessment_year or payload["ITR"][form][f"Form_{form}"]["AssessmentYear"]
            if re.fullmatch(r"[0-9]{4}", year):
                year = f"{year}-{(int(year)+1)%100:02}"
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", year):
                raise ValueError("Invalid assessment year")
            name = f"{form.lower()}_schema_ay{year.replace('-', '_')}.json"
            manifest = json.loads((self.schemas_dir / "manifest.json").read_text())
            raw = (self.schemas_dir / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest[name]["sha256"]:
                raise ValueError("Schema checksum mismatch")
            schema = json.loads(raw)
            Draft4Validator.check_schema(schema)
            errors = [f"/{'/'.join(map(str, e.absolute_path))}: {e.validator} constraint failed"
                      for e in Draft4Validator(schema, format_checker=FormatChecker()).iter_errors(payload)]
            if not payload.get("ITR", {}).get(form):
                errors.append("Missing ITR form payload")
            return not errors, errors
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return False, [f"Official schema unavailable or invalid for {form}: {type(exc).__name__}"]

def validate_itr_json(form_name: str, payload: dict, assessment_year: str | None = None):
    return ITRSchemaLoader().validate(form_name, payload, assessment_year)
