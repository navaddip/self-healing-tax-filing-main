import { useState } from "react";
import type { SubmissionResult } from "../types/tax";
import { FilingDetailsForm, labelFor } from "./FilingDetailsForm";
import { RegimeComparisonView } from "./RegimeComparison";

const ACTION_SUMMARY: Record<string, string> = {
  extract_page: "Read document page using OCR and structured text extraction.",
  form16_extract: "Extracted salary 17(1), exemptions u/s 10, standard deduction, and Chapter VI-A deductions.",
  form26as_extract: "Extracted TDS on salary, other TDS, and advance tax / SAT challans.",
  ais_extract: "Parsed Annual Information Statement financial streams and interest entries.",
  broker_pnl_extract: "Parsed capital gains trading P&L and recomputed holding periods.",
  compute_income: "Determined gross total income and net deductions across all five statutory heads.",
  tax_old: "Computed tax liability under the Old Regime with full slab and rebate benefits.",
  tax_new: "Computed tax liability under Section 115BAC (New Regime) with concessional slabs.",
  compare: "Selected optimal regime, determined savings, line-by-line deltas, and breakeven threshold.",
  verify: "Recomputed returns in fresh engines and validated 11 statutory and audit gates.",
  remediate: "Healed discrepancies (TDS reconciliation, 80C caps, or date corrections).",
  document: "Generated 8-page CA-grade advisory report and filing export readiness check.",
};

const STATUS_LABEL: Record<string, string> = {
  completed: "Return Ready",
  manual_review: "Needs Review",
  failed: "Failed",
  computing_income: "In Progress",
  processing: "In Progress",
};

export function ResultPanel({
  result,
  onResubmit,
}: {
  result: SubmissionResult;
  onResubmit?: (result: SubmissionResult) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const missing = result.missing_filing_fields ?? [];
  const refundOnly = missing.length > 0 && missing.every((key) => key.startsWith("bank_"));
  const v = result.verification;
  const cmp = result.comparison;
  const data = result.extracted_data;
  const checks = v?.checks ?? [];
  const verificationPassed = Boolean(v?.valid);
  const reportEligible = Boolean(verificationPassed && result.report_url);
  const submissionCompleted = result.status === "completed";
  const statusLabel = STATUS_LABEL[result.status] ?? result.status.replace(/_/g, " ");
  const passedChecks = checks.filter((c) => c.passed).length;

  return (
    <section className="results">
      {/* Report Cover */}
      <header className="report-cover">
        <div className="report-cover-meta">
          <span className={`status status-${result.status}`}>{statusLabel}</span>
          <p className="report-doctype">Income Tax Filing Report</p>
          <h2>Tax Assessment &amp; Regime Advisory</h2>
          <p className="report-tagline">
            Independent dual-regime computation, statutory verification, and filing-ready ITR package.
          </p>
          <dl className="report-facts">
            {result.serial_no != null && (
              <div>
                <dt>Submission No.</dt>
                <dd>#{result.serial_no}</dd>
              </div>
            )}
            <div>
              <dt>PAN</dt>
              <dd>{data?.masked_pan || data?.pan || "—"}</dd>
            </div>
            <div>
              <dt>Assessment Year</dt>
              <dd>{data?.assessment_year || "—"}</dd>
            </div>
            <div>
              <dt>Financial Year</dt>
              <dd>{data?.financial_year || "—"}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd><code>{result.submission_id}</code></dd>
            </div>
          </dl>
        </div>
        {v && (
          <aside className="confidence-card">
            <span className="confidence-label">Verification Confidence</span>
            <div className="confidence-num">
              {Math.round(v.confidence_score * 100)}
              <span>%</span>
            </div>
            <div className="verdict-chips">
              <span className={v.correctness_ok ? "chip ok" : "chip bad"}>
                {v.correctness_ok ? "✓" : "✗"} Correctness
              </span>
              <span className={v.completeness_ok ? "chip ok" : "chip bad"}>
                {v.completeness_ok ? "✓" : "✗"} Completeness
              </span>
            </div>
            {checks.length > 0 && (
              <p className="confidence-note">
                {passedChecks} of {checks.length} statutory gates cleared
              </p>
            )}
          </aside>
        )}
      </header>

      {result.error && (
        <div className="alert" role="alert">
          <strong>Processing failed.</strong>
          <p>{result.error}</p>
        </div>
      )}

      {/* Section: Regime Comparison */}
      {cmp && (
        <ReportSection
          number="01"
          title="Regime Recommendation"
          subtitle="Which regime saves you more under current law, and by how much."
        >
          <RegimeComparisonView
            comparison={cmp}
            submissionId={result.submission_id}
            assessmentYear={data?.assessment_year}
            financialYear={data?.financial_year}
          />
        </ReportSection>
      )}

      {/* Section: Filing Package */}
      {(result.receipt || submissionCompleted) && (
        <ReportSection
          number="02"
          title="Filing Package"
          subtitle="Downloadable deliverables: the advisory PDF, the ITR JSON, and the full audit log."
        >
          <div className="filing-package">
            <div className="package-summary">

              {result.receipt && (
                <dl className="package-facts">

                  <div>
                    <dt>Channel</dt>
                    <dd>{result.receipt.filing_type || "json_self_file"}</dd>
                  </div>
                  <div>
                    <dt>Form</dt>
                    <dd>{result.receipt.itr_form || "ITR-1"}</dd>
                  </div>
                </dl>
              )}
            </div>

            {result.receipt?.filing_status === "ready_to_self_file" && result.receipt.instructions && (
              <pre className="receipt-instructions">{result.receipt.instructions}</pre>
            )}

            <div className="download-actions">
              {reportEligible && result.report_url && (
                <a
                  href={result.report_url}
                  download={`tax-filing-report-${result.submission_id}.pdf`}
                  className="btn-download"
                >
                  <span aria-hidden="true">📄</span>
                  <span>
                    <strong>Tax Filing Report</strong>
                    <small>Verified PDF · 8 pages</small>
                  </span>
                </a>
              )}
              {!reportEligible && submissionCompleted && (
                <button
                  type="button"
                  className="btn-download btn-disabled"
                  disabled
                  title={
                    verificationPassed
                      ? "The verified PDF is still being prepared."
                      : "PDF download requires successful verification with the configured confidence threshold."
                  }
                >
                  <span aria-hidden="true">📄</span>
                  <span>
                    <strong>
                      {verificationPassed
                        ? "Preparing Tax Filing PDF…"
                        : "Awaiting Verification"}
                    </strong>
                    <small>Not yet available</small>
                  </span>
                </button>
              )}
              {result.itr_json_url && (
                <a
                  href={result.itr_json_url}
                  download={`ITR_Return_AY${data?.assessment_year}.json`}
                  className="btn-download btn-secondary"
                >
                  <span aria-hidden="true">📥</span>
                  <span>
                    <strong>ITR JSON</strong>
                    <small>Import into the ITR utility</small>
                  </span>
                </a>
              )}
              {result.audit_trail && result.audit_trail.length > 0 && (
                <a
                  href={result.audit_url || `/api/v1/submissions/${result.submission_id}/audit`}
                  download={`audit-trail-${result.submission_id}.json`}
                  className="btn-download btn-secondary"
                >
                  <span aria-hidden="true">📋</span>
                  <span>
                    <strong>Audit Log</strong>
                  </span>
                </a>
              )}
            </div>

            {v && submissionCompleted && !reportEligible && (
              <p className="report-threshold-note">
                {verificationPassed
                  ? "The verified PDF is being prepared. This download activates automatically once the report is signed."
                  : "The tax filing PDF unlocks after verification clears the configured confidence threshold."}
              </p>
            )}
          </div>
        </ReportSection>
      )}

      {missing.length > 0 && (
        <section className="filing-details-card" aria-labelledby="filing-details-title">
          <h3 id="filing-details-title">
            {refundOnly
              ? "Add your bank account to receive the refund"
              : `Your ${result.receipt?.itr_form ?? "ITR"} file needs a few more details`}
          </h3>
          <p>
            A Form 16 doesn't contain these, so we couldn't fill them in. Your tax calculation and
            advisory report are not affected.
          </p>
          <ul className="missing-list">
            {missing.map((key) => (
              <li key={key}>{labelFor(key)}</li>
            ))}
          </ul>
          {showForm ? (
            <FilingDetailsForm
              submissionId={result.submission_id}
              missing={missing}
              onSaved={(saved) => {
                setShowForm(false);
                onResubmit?.(saved);
              }}
            />
          ) : (
            <button type="button" className="fill-details-btn" onClick={() => setShowForm(true)}>
              Fill details
            </button>
          )}
        </section>
      )}

      {missing.length === 0 && result.receipt?.filing_status === "advisory_only" && result.receipt.instructions && (
        <div className="alert" role="status">
          <strong>Advisory report ready.</strong>
          <p>{result.receipt.instructions}</p>
        </div>
      )}

      {/* Section: Statutory Gates */}
      {checks.length > 0 && (
        <ReportSection
          number="03"
          title="Statutory & Computational Integrity"
          subtitle={`${passedChecks} of ${checks.length} independent gates cleared before the report was released.`}
        >
          <div className="checks-grid">
            {checks.map((chk, idx) => (
              <div key={idx} className={`check-card ${chk.passed ? "check-pass" : "check-fail"}`}>
                <div className="check-title">
                  <span className="check-mark">{chk.passed ? "✓" : "✗"}</span>
                  <strong>{chk.name}</strong>
                </div>
                <p className="check-msg">{chk.message}</p>
              </div>
            ))}
          </div>
        </ReportSection>
      )}

      {/* Section: Agent Trail */}
      {result.audit_trail && result.audit_trail.length > 0 && (
        <ReportSection
          number="04"
          title="Agent Decision Trail"
          subtitle="A chronological log of each agent that touched this return, in the order it ran."
        >
          <ol className="timeline">
            {result.audit_trail.map((entry, idx) => (
              <li key={idx} className="timeline-item">
                <div className="timeline-marker">
                  <span className="timeline-index">{String(idx + 1).padStart(2, "0")}</span>
                </div>
                <div className="timeline-content">
                  <div className="timeline-top">
                    <strong>{entry.agent}</strong>
                    <span className="action-tag">{entry.action}</span>
                    <time>{new Date(entry.timestamp).toLocaleTimeString()}</time>
                  </div>
                  <p>{ACTION_SUMMARY[entry.action] || entry.reason}</p>
                </div>
              </li>
            ))}
          </ol>
        </ReportSection>
      )}
    </section>
  );
}

function ReportSection({
  number,
  title,
  subtitle,
  children,
}: {
  number: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="report-section">
      <header className="report-section-head">
        <span className="section-number">Section {number}</span>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </header>
      <div className="report-section-body">{children}</div>
    </section>
  );
}
