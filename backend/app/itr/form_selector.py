"""ITR form selector router and helper.

Determines the eligible ITR Form (ITR-1, ITR-2, ITR-3, ITR-4) based on the
CBDT rules for AY 2026-27 (FY 2025-26).
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.verification.completeness import select_itr_form
from app.schemas.tax import IndianTaxpayerData, ItrForm

__all__ = ["select_itr_form", "ItrForm"]
