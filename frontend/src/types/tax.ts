export type WorkflowStatus =
  | "uploaded"
  | "parsing"
  | "computing_income"
  | "calculating_old"
  | "calculating_new"
  | "comparing"
  | "verifying"
  | "remediating"
  | "review_ready"
  | "approved"
  | "completed"
  | "manual_review"
  | "failed";

export type Regime = "old" | "new";

export interface HeadwiseIncome {
  regime: Regime;
  gross_salary: number | string;
  exempt_allowances: number | string;
  standard_deduction: number | string;
  professional_tax: number | string;
  income_from_salary: number | string;
  house_property_income: number | string;
  business_income: number | string;
  stcg_111a?: number | string;
  stcg_slab?: number | string;
  ltcg_112a_gross?: number | string;
  ltcg_112a_exempt?: number | string;
  ltcg_112a_taxable?: number | string;
  ltcg_112?: number | string;
  capital_gains_total: number | string;
  other_sources_income: number | string;
  gross_total_income: number | string;
  chapter_via: Record<string, number | string>;
  chapter_via_total: number | string;
  total_income: number | string;
}

export interface RegimeTaxResult {
  regime: Regime;
  income: HeadwiseIncome;
  tax_on_slab_income: number | string;
  tax_on_special_income: number | string;
  tax_before_rebate: number | string;
  rebate_87a: number | string;
  marginal_relief_87a: number | string;
  tax_after_rebate: number | string;
  surcharge: number | string;
  cess: number | string;
  total_tax_liability: number | string;
  taxes_paid_total: number | string;
  interest_234a: number | string;
  interest_234b: number | string;
  interest_234c: number | string;
  fee_234f: number | string;
  refund_due: number | string;
  tax_payable: number | string;
  effective_tax_rate: number | string;
}

export interface ComparisonDelta {
  line: string;
  old_value: number | string;
  new_value: number | string;
  delta: number | string;
}

export interface RegimeComparison {
  old: RegimeTaxResult;
  new: RegimeTaxResult;
  recommended: Regime;
  savings: number | string;
  savings_pct: number | string;
  deltas: ComparisonDelta[];
  deductions_forfeited_if_new: Record<string, number | string>;
  breakeven_deduction_amount: number | string;
  unused_80c_headroom: number | string;
  switch_allowed_annually: boolean;
  form_10iea_required: boolean;
  reasons: string[];
}

export interface VerificationCheck {
  name: string;
  passed: boolean;
  message: string;
  weight?: number;
}

export interface VerificationResult {
  valid: boolean;
  confidence_score: number;
  checks: VerificationCheck[];
  hallucination_flags?: string[];
  errors?: string[];
  correctness_ok?: boolean;
  completeness_ok?: boolean;
  requires_reextraction?: boolean;
}

export interface AuditEntry {
  agent: string;
  action: string;
  reason: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

export interface FilingReceipt {
  submission_id: string;
  reference_number: string;
  timestamp: string;
  filing_status: string;
  filing_type?: string;
  itr_form?: string;
  regime?: string;
  payload_hash?: string;
  acknowledgement_id?: string;
  instructions?: string;
  export_supported?: boolean;
}

export interface IndianTaxpayerData {
  name?: string;
  pan?: string;
  masked_pan?: string;
  date_of_birth?: string;
  residential_status?: string;
  age_band?: string;
  financial_year?: string;
  assessment_year?: string;
  bank_account_last4?: string;
  bank_ifsc?: string;
  form16s?: Array<{
    employer_name: string;
    gross_salary_17_1: number | string;
    tds_deducted: number | string;
  }>;
  savings_interest?: number | string;
  deduction_claims?: Record<string, number | string>;
}

export interface SensitivityPoint {
  delta: number;
  old_tax: number;
  new_tax: number;
  winner: "old" | "new";
}

export interface SubmissionResult {
  serial_no?: number | null;
  submission_id: string;
  status: WorkflowStatus;
  original_filename: string;
  extracted_data?: IndianTaxpayerData;
  comparison?: RegimeComparison;
  verification?: VerificationResult;
  audit_trail: AuditEntry[];
  receipt?: FilingReceipt;
  report_url?: string;
  itr_json_url?: string;
  audit_url?: string;
  error?: string;
  missing_filing_fields?: string[];
}
