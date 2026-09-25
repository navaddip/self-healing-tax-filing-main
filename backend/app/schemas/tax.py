from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import AgeBand, mask_pan, validate_ifsc


class Regime(str, Enum):
    OLD = "old"
    NEW = "new"


class ResidentialStatus(str, Enum):
    RESIDENT_ORDINARY = "resident_ordinary"
    RESIDENT_NOT_ORDINARY = "resident_not_ordinary"
    NON_RESIDENT = "non_resident"


class ITRForm(str, Enum):
    ITR1 = "ITR-1"
    ITR2 = "ITR-2"
    ITR3 = "ITR-3"
    ITR4 = "ITR-4"


ItrForm = ITRForm


class WorkflowStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    COMPUTING_INCOME = "computing_income"
    CALCULATING_OLD = "calculating_old"
    CALCULATING_NEW = "calculating_new"
    COMPARING = "comparing"
    VERIFYING = "verifying"
    REMEDIATING = "remediating"
    REVIEW_READY = "review_ready"
    APPROVED = "approved"
    COMPLETED = "completed"
    MANUAL_REVIEW = "manual_review"
    FAILED = "failed"


def _to_decimal(value: Any) -> Decimal:
    """Coerce currency strings and numbers to Decimal."""
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        # Remove currency symbols (INR ₹, $, Rs., etc.), commas, and whitespace
        cleaned = re.sub(r"[₹$,\s]|Rs\.?|INR", "", value, flags=re.IGNORECASE).strip()
        if not cleaned:
            return Decimal("0")
        return Decimal(cleaned)
    return Decimal(str(value))


class SourceEvidence(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str = Field(..., alias="field_name")
    page: int = Field(default=1, alias="page_number")
    raw_text: str = ""
    source: str = Field(default="ocr", alias="source_document")
    confidence: float = Field(default=0.0, ge=0, le=1)


class Form16(BaseModel):
    employer_name: str = ""
    employer_tan: str = ""
    employer_pan: str = ""
    certificate_number: str = ""
    period_from: date | None = None
    period_to: date | None = None
    gross_salary_17_1: Decimal = Decimal("0")
    perquisites_17_2: Decimal = Decimal("0")
    profits_in_lieu_17_3: Decimal = Decimal("0")
    exempt_allowances_10: dict[str, Decimal] = Field(default_factory=dict)
    standard_deduction: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    entertainment_allowance: Decimal = Decimal("0")
    chapter_via_claimed: dict[str, Decimal] = Field(default_factory=dict)
    regime_used: Regime = Regime.NEW
    tds_deducted: Decimal = Decimal("0")
    taxable_salary_per_employer: Decimal = Decimal("0")
    reported_house_property_loss: Decimal = Decimal("0")
    reported_other_income: Decimal = Decimal("0")
    # Gross amount of the 80TTA row, i.e. the savings interest the deduction was computed on.
    reported_savings_interest: Decimal = Decimal("0")
    relief_89: Decimal = Decimal("0")

    @field_validator(
        "gross_salary_17_1",
        "perquisites_17_2",
        "profits_in_lieu_17_3",
        "standard_deduction",
        "professional_tax",
        "entertainment_allowance",
        "tds_deducted",
        "taxable_salary_per_employer",
        "reported_house_property_loss",
        "reported_other_income",
        "reported_savings_interest",
        "relief_89",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)

    @field_validator("exempt_allowances_10", "chapter_via_claimed", mode="before")
    @classmethod
    def _coerce_dict_decimals(cls, v: Any) -> dict[str, Decimal]:
        if not isinstance(v, dict):
            return {}
        return {k: _to_decimal(val) for k, val in v.items()}


class SalaryBreakup(BaseModel):
    basic: Decimal = Decimal("0")
    dearness_allowance: Decimal = Decimal("0")
    hra_received: Decimal = Decimal("0")
    lta_received: Decimal = Decimal("0")
    other_allowances: Decimal = Decimal("0")
    rent_paid_annual: Decimal = Decimal("0")
    landlord_pan: str = ""
    is_metro: bool = False
    months_in_service: int = 12

    @field_validator(
        "basic",
        "dearness_allowance",
        "hra_received",
        "lta_received",
        "other_allowances",
        "rent_paid_annual",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)


class HouseProperty(BaseModel):
    is_self_occupied: bool = True
    annual_rent_received: Decimal = Decimal("0")
    municipal_taxes_paid: Decimal = Decimal("0")
    interest_on_loan_24b: Decimal = Decimal("0")
    principal_repaid_80c: Decimal = Decimal("0")
    is_let_out: bool = False
    co_owner_share: Decimal = Decimal("1")

    @model_validator(mode="after")
    def _let_out_is_not_self_occupied(self) -> "HouseProperty":
        if self.is_let_out:
            self.is_self_occupied = False
        return self

    @field_validator(
        "annual_rent_received",
        "municipal_taxes_paid",
        "interest_on_loan_24b",
        "principal_repaid_80c",
        "co_owner_share",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)

    @property
    def annual_lettable_value(self) -> Decimal:
        return self.annual_rent_received


class CapitalGainItem(BaseModel):
    asset_type: Literal[
        "listed_equity",
        "equity_mf",
        "immovable_property",
        "unlisted_shares",
        "gold",
        "debt_mf",
        "other",
    ]
    acquisition_date: date | None = None
    transfer_date: date | None = None
    cost_of_acquisition: Decimal = Decimal("0")
    cost_of_improvement: Decimal = Decimal("0")
    transfer_expenses: Decimal = Decimal("0")
    sale_consideration: Decimal = Decimal("0")
    stt_paid: bool = False
    is_pre_23jul2024: bool = False
    holding_days: int = 0
    is_long_term: bool = False
    indexed_cost: Decimal = Decimal("0")
    gain: Decimal = Decimal("0")

    @field_validator(
        "cost_of_acquisition",
        "cost_of_improvement",
        "transfer_expenses",
        "sale_consideration",
        "indexed_cost",
        "gain",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)


class PresumptiveBusiness(BaseModel):
    section: Literal["44AD", "44ADA", "44AE"]
    turnover: Decimal = Decimal("0")
    digital_receipts: Decimal = Decimal("0")
    cash_receipts: Decimal = Decimal("0")
    declared_profit: Decimal = Decimal("0")
    vehicles: list[dict[str, Any]] | None = None

    @field_validator(
        "turnover",
        "digital_receipts",
        "cash_receipts",
        "declared_profit",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)


class TaxesPaid(BaseModel):
    tds_salary: Decimal = Decimal("0")
    tds_non_salary: Decimal = Decimal("0")
    tcs: Decimal = Decimal("0")
    advance_tax_instalments: dict[str, Decimal] = Field(default_factory=dict)
    self_assessment_tax: Decimal = Decimal("0")
    relief_89: Decimal = Decimal("0")
    relief_90_91: Decimal = Decimal("0")

    @field_validator(
        "tds_salary",
        "tds_non_salary",
        "tcs",
        "self_assessment_tax",
        "relief_89",
        "relief_90_91",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)

    @field_validator("advance_tax_instalments", mode="before")
    @classmethod
    def _coerce_dict_decimals(cls, v: Any) -> dict[str, Decimal]:
        if not isinstance(v, dict):
            return {}
        return {k: _to_decimal(val) for k, val in v.items()}


class DonationClaim(BaseModel):
    amount: Decimal = Field(ge=0)
    percentage: int = Field(default=50)
    qualifying_limit: bool = True
    cash: bool = False
    eligible: bool = False

    @field_validator("percentage")
    @classmethod
    def valid_percentage(cls, value):
        if value not in (50, 100):
            raise ValueError("Donation percentage must be 50 or 100")
        return value


class IndianTaxpayerData(BaseModel):
    # Identity
    name: str = ""
    pan: str = ""
    aadhaar_last4: str = ""
    date_of_birth: date | None = None
    residential_status: ResidentialStatus = ResidentialStatus.RESIDENT_ORDINARY
    age_band: AgeBand = AgeBand.BELOW_60
    email: str = ""
    mobile: str = ""
    address: str = ""
    bank_account_last4: str = ""
    bank_ifsc: str = ""
    bank_account_number: str = ""
    bank_name: str = ""
    bank_account_type: str = "SB"  # CBDT: SB, CA, CC, OD, NRO, OTH
    father_name: str = ""
    city: str = ""
    state_code: str = ""
    pin_code: str = ""
    locality_or_area: str = ""
    country_code_mobile: str = "91"
    employer_category: str = ""  # CBDT: CGOV, SGOV, PSU, PE, PESG, PEPS
    verification_capacity: str = "S"  # CBDT: S (Self) or R (Representative)
    verification_place: str = ""
    filing_date: date | None = None
    health_self_family: Decimal | None = Field(default=None, ge=0)
    health_parents: Decimal | None = Field(default=None, ge=0)
    health_self_family_senior: bool = False
    health_parents_senior: bool = False
    education_loan_first_repayment_fy: int | None = None
    donations: list[DonationClaim] = Field(default_factory=list)
    assessment_year: str = "2026-27"
    financial_year: str = "2025-26"

    # Facts by head
    form16s: list[Form16] = Field(default_factory=list)
    salary_breakup: SalaryBreakup | None = None
    house_properties: list[HouseProperty] = Field(default_factory=list)
    capital_gains: list[CapitalGainItem] = Field(default_factory=list)
    presumptive: PresumptiveBusiness | None = None

    savings_interest: Decimal = Decimal("0")
    fd_interest: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")
    family_pension: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    winnings_115bb: Decimal = Decimal("0")
    exempt_income: Decimal = Decimal("0")
    agricultural_income: Decimal = Decimal("0")

    # Deduction claims (raw claims)
    deduction_claims: dict[str, Decimal] = Field(default_factory=dict)
    taxes_paid: TaxesPaid = Field(default_factory=TaxesPaid)
    brought_forward_losses: dict[str, Decimal] = Field(default_factory=dict)

    # Provenance
    evidence: list[SourceEvidence] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator(
        "savings_interest",
        "fd_interest",
        "dividend_income",
        "family_pension",
        "other_income",
        "winnings_115bb",
        "exempt_income",
        "agricultural_income",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal:
        return _to_decimal(v)

    @field_validator(
        "deduction_claims", "brought_forward_losses", mode="before"
    )
    @classmethod
    def _coerce_dict_decimals(cls, v: Any) -> dict[str, Decimal]:
        if not isinstance(v, dict):
            return {}
        return {k: _to_decimal(val) for k, val in v.items()}

    @property
    def masked_pan(self) -> str:
        return mask_pan(self.pan)

    @property
    def tax_year(self) -> str:
        """Backwards-compatible alias for financial_year."""
        return self.financial_year

    def aggregate_form16s(self) -> None:
        """Fold multiple Form 16s into salary totals and taxes paid."""
        total_tds = sum((f.tds_deducted for f in self.form16s), Decimal("0"))
        if total_tds > Decimal("0"):
            self.taxes_paid.tds_salary = total_tds
        total_relief = sum((f.relief_89 for f in self.form16s), Decimal("0"))
        if total_relief > Decimal("0"):
            self.taxes_paid.relief_89 = total_relief


# Alias for compatibility with existing imports
TaxpayerData = IndianTaxpayerData


class HeadwiseIncome(BaseModel):
    regime: Regime
    gross_salary: Decimal = Decimal("0")
    exempt_allowances: Decimal = Decimal("0")
    standard_deduction: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    income_from_salary: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    hp_loss_set_off: Decimal = Decimal("0")
    hp_loss_carried_forward: Decimal = Decimal("0")
    business_income: Decimal = Decimal("0")
    stcg_111a: Decimal = Decimal("0")
    stcg_slab: Decimal = Decimal("0")
    ltcg_112a_gross: Decimal = Decimal("0")
    ltcg_112a_exempt: Decimal = Decimal("0")
    ltcg_112a_taxable: Decimal = Decimal("0")
    ltcg_112: Decimal = Decimal("0")
    capital_gains_total: Decimal = Decimal("0")
    cg_loss_carried_forward: Decimal = Decimal("0")
    winnings_115bb: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    gross_total_income: Decimal = Decimal("0")
    chapter_via: dict[str, Decimal] = Field(default_factory=dict)
    chapter_via_total: Decimal = Decimal("0")
    total_income: Decimal = Decimal("0")
    trace: list[str] = Field(default_factory=list)

    @property
    def salary_income(self) -> Decimal:
        return self.income_from_salary

    @property
    def salary_standard_deduction(self) -> Decimal:
        return self.standard_deduction

    @property
    def salary_professional_tax(self) -> Decimal:
        return self.professional_tax


class RegimeTaxResult(BaseModel):
    regime: Regime
    income: HeadwiseIncome
    tax_on_slab_income: Decimal = Decimal("0")
    slab_components: list[dict[str, Any]] = Field(default_factory=list)
    tax_on_special_income: Decimal = Decimal("0")
    tax_before_rebate: Decimal = Decimal("0")
    rebate_87a: Decimal = Decimal("0")
    marginal_relief_87a: Decimal = Decimal("0")
    tax_after_rebate: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    surcharge_marginal_relief: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")
    total_tax_liability: Decimal = Decimal("0")
    taxes_paid_total: Decimal = Decimal("0")
    interest_234a: Decimal = Decimal("0")
    interest_234b: Decimal = Decimal("0")
    interest_234c: Decimal = Decimal("0")
    fee_234f: Decimal = Decimal("0")
    refund_due: Decimal = Decimal("0")
    tax_payable: Decimal = Decimal("0")
    effective_tax_rate: Decimal = Decimal("0")
    effective_tax_rate_basis: str = "total tax liability / taxable income"
    trace: list[str] = Field(default_factory=list)


class RegimeComparison(BaseModel):
    old: RegimeTaxResult
    new: RegimeTaxResult
    recommended: Regime
    savings: Decimal = Decimal("0")
    savings_pct: Decimal = Decimal("0")
    deltas: list[dict[str, Any]] = Field(default_factory=list)
    deductions_forfeited_if_new: dict[str, Decimal] = Field(default_factory=dict)
    current_old_total_reductions: Decimal = Decimal("0")
    breakeven_deduction_amount: Decimal = Decimal("0")
    unused_80c_headroom: Decimal = Decimal("0")
    switch_allowed_annually: bool = True
    form_10iea_required: bool = False
    reasons: list[str] = Field(default_factory=list)


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    message: str
    weight: float = 1.0


class VerificationResult(BaseModel):
    valid: bool
    confidence_score: float = Field(ge=0, le=1)
    checks: list[VerificationCheck]
    hallucination_flags: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    correctness_ok: bool = True
    completeness_ok: bool = True
    requires_reextraction: bool = False


class AuditEntry(BaseModel):
    agent: str
    action: str
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class FilingDetails(BaseModel):
    """Taxpayer-supplied details the ITR needs but a Form 16 never contains."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    date_of_birth: date | None = None
    employer_category: Literal["CGOV", "SGOV", "PSU", "PE", "PESG", "PEPS", "PEO", "OTH", "NA"] | None = None
    address: str | None = Field(default=None, max_length=50)
    locality_or_area: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=50)
    state_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    pin_code: str | None = Field(default=None, pattern=r"^[1-9]\d{5}$")
    mobile: str | None = Field(default=None, pattern=r"^[6-9]\d{9}$")
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=125)
    bank_ifsc: str | None = None
    bank_name: str | None = Field(default=None, max_length=125)
    bank_account_number: str | None = Field(default=None, pattern=r"^\d{9,18}$")
    father_name: str | None = Field(default=None, max_length=125)
    verification_place: str | None = Field(default=None, max_length=50)

    @field_validator("date_of_birth")
    @classmethod
    def _dob_in_past(cls, v: date | None) -> date | None:
        if v and not date(1900, 1, 1) <= v < date.today():
            raise ValueError("Date of birth must be a past date after 1900")
        return v

    @field_validator("state_code")
    @classmethod
    def _state(cls, v: str | None) -> str | None:
        if v and not (1 <= int(v) <= 37 or v == "99"):
            raise ValueError("Unknown state code")
        return v

    @field_validator("bank_ifsc")
    @classmethod
    def _ifsc(cls, v: str | None) -> str | None:
        if v:
            v = v.upper()
            if not validate_ifsc(v):
                raise ValueError("IFSC must look like HDFC0001234")
        return v

    def provided(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v not in (None, "")}


def age_band_on(dob: date, fy_start_year: int) -> AgeBand:
    """Age band for a financial year: age reached by 31 March of the FY end."""
    fy_end = date(fy_start_year + 1, 3, 31)
    age = fy_end.year - dob.year - ((fy_end.month, fy_end.day) < (dob.month, dob.day))
    if age >= 80:
        return AgeBand.SUPER_SENIOR_80_PLUS
    if age >= 60:
        return AgeBand.SENIOR_60_80
    return AgeBand.BELOW_60


class FilingReceipt(BaseModel):
    submission_id: str
    reference_number: str
    timestamp: datetime
    filing_status: str
    filing_type: str = "json_self_file"
    itr_form: str = "ITR-1"
    regime: str = "new"
    payload_hash: str | None = None
    acknowledgement_id: str | None = None
    instructions: str | None = None
    export_supported: bool = True


class SubmissionResult(BaseModel):
    submission_id: str
    serial_no: int | None = None
    status: WorkflowStatus
    original_filename: str
    extracted_data: IndianTaxpayerData | None = None
    comparison: RegimeComparison | None = None
    verification: VerificationResult | None = None
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    receipt: FilingReceipt | None = None
    report_url: str | None = None
    itr_json_url: str | None = None
    audit_url: str | None = None
    error: str | None = None
    missing_filing_fields: list[str] = Field(default_factory=list)


    @property
    def calculation(self) -> RegimeComparison | None:
        """Backwards-compatible alias for comparison."""
        return self.comparison


# Backwards compatibility aliases
TaxpayerData = IndianTaxpayerData
TaxCalculation = RegimeTaxResult
W2 = Form16


class FilingStatus(str, Enum):
    INDIVIDUAL = "individual"
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_JOINTLY = "married_jointly"
    MARRIED_SEPARATE = "married_separate"
    MARRIED_SEPARATELY = "married_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"
    QUALIFYING_WIDOW = "qualifying_widow"
