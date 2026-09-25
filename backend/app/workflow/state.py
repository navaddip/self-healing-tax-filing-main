from typing import Any, TypedDict


class TaxWorkflowState(TypedDict, total=False):
    financial_year: str
    submission_id: str
    original_filename: str
    upload_path: str
    upload_paths: list[str]
    report_path: str
    status: str
    extracted_data: dict[str, Any]
    raw_text: str
    computed_income_old: dict[str, Any]
    computed_income_new: dict[str, Any]
    result_old: dict[str, Any]
    result_new: dict[str, Any]
    comparison: dict[str, Any]
    calculation: dict[str, Any]
    verification: dict[str, Any]
    audit_trail: list[dict[str, Any]]
    remediation_attempts: int
    reextraction_passes: int
    needs_reextraction: bool
    transcript: dict[str, Any]
    receipt: dict[str, Any]
    error: str
