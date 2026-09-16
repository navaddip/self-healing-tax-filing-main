from __future__ import annotations

import base64
import io
import json
from typing import Any

import httpx
from PIL import Image


class OllamaClient:
    def __init__(self, base_url: str, vision_model: str, coder_model: str):
        self.base_url = base_url.rstrip("/")
        self.vision_model = vision_model
        self.coder_model = coder_model
        self._vision_disabled_reason: str | None = None

    def _image_base64(self, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def extract_tax_fields(
        self, image: Image.Image, ocr_text: str
    ) -> dict[str, Any]:
        if self._vision_disabled_reason:
            return {}
        prompt = """
Extract US tax document fields. Return JSON only with these keys:
employee_name, employer_name, ssn, filing_status, tax_year, wages,
federal_tax_withheld, state_tax_withheld, ss_wages, ss_tax_withheld,
medicare_wages, medicare_tax_withheld, taxable_interest, ordinary_dividends,
qualified_dividends, long_term_capital_gain, short_term_capital_gain,
self_employment_income, other_income, itemized_deductions, state,
field_confidence.
For a W-2: wages=box1, federal_tax_withheld=box2, ss_wages=box3,
ss_tax_withheld=box4, medicare_wages=box5, medicare_tax_withheld=box6,
state_tax_withheld=box17.
Use null for absent values. Never infer a monetary value not visible in the
document. filing_status must be single, married_filing_jointly,
married_filing_separately, or head_of_household.
OCR text follows:
""" + ocr_text[:12000]
        payload = {
            "model": self.vision_model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [self._image_base64(image)],
                }
            ],
            "options": {"temperature": 0, "num_ctx": 2048},
        }
        try:
            with httpx.Client(timeout=180) as client:
                response = client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                response.raise_for_status()
            content = response.json()["message"]["content"]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except httpx.HTTPStatusError as exc:
            self._vision_disabled_reason = exc.response.text[:500]
            return {}
        except httpx.HTTPError as exc:
            self._vision_disabled_reason = str(exc)[:500]
            return {}
        except (KeyError, json.JSONDecodeError):
            return {}

    def classify_remediation(self, errors: list[str]) -> dict[str, Any]:
        payload = {
            "model": self.coder_model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Classify these tax workflow validation errors. Return "
                        "JSON only with root_cause and recommended_action. Do "
                        "not propose or calculate tax values.\n"
                        + "\n".join(errors)
                    ),
                }
            ],
            "options": {"temperature": 0},
        }
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                response.raise_for_status()
            return json.loads(response.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, json.JSONDecodeError):
            return {
                "root_cause": "deterministic_validation_failure",
                "recommended_action": "Apply bounded deterministic remediation",
            }
