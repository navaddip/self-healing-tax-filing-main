"""Synthetic Indian taxpayer data for demos, tests, and eval ground truth.

Fabricated data with realistic statutory cross-footings for AY 2026-27 (FY 2025-26).
"""

from app.synthetic.generator import (
    PERSONAS,
    get_persona,
    list_personas,
    synthetic_freelancer_44ada,
    synthetic_fresher,
    synthetic_high_earner_surcharge,
    synthetic_job_changer,
    synthetic_landlord_multi_property,
    synthetic_mid_career,
    synthetic_return,
    synthetic_senior_pensioner,
    synthetic_trader,
    synthetic_transcript,
)

__all__ = [
    "PERSONAS",
    "get_persona",
    "list_personas",
    "synthetic_fresher",
    "synthetic_mid_career",
    "synthetic_senior_pensioner",
    "synthetic_trader",
    "synthetic_freelancer_44ada",
    "synthetic_landlord_multi_property",
    "synthetic_high_earner_surcharge",
    "synthetic_job_changer",
    "synthetic_return",
    "synthetic_transcript",
]
