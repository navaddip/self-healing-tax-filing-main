"""ITR JSON builders and schema validation for Indian Income Tax Returns (ITR-1, ITR-2, ITR-4)."""

from app.itr.form_selector import ItrForm, select_itr_form
from app.itr.itr1_builder import ITR1Builder
from app.itr.itr2_builder import ITR2Builder
from app.itr.itr4_builder import ITR4Builder
from app.itr.schema_loader import ITRSchemaLoader, validate_itr_json

__all__ = [
    "ItrForm",
    "select_itr_form",
    "ITR1Builder",
    "ITR2Builder",
    "ITR4Builder",
    "ITRSchemaLoader",
    "validate_itr_json",
]
