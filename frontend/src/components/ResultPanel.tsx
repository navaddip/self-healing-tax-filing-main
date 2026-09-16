import type { SubmissionResult } from "../types/tax";
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
  document: "Generated 8-page CA-grade advisory report and official CBDT ITR JSON payload.",
};

export function ResultPanel({ result }: { result: SubmissionResult }) {
  const v = result.verification;
  const cmp = result.comparison;
  const data = result.extracted_data;
  const checks = v?.checks ?? [];

  return (
    <section className="results">
      {/* 1. Header & Verification Status */}
      <div className="result-heading">
        <div>
          <span className={`status status-${result.status}`}>
            {result.status.replace("_", " ")}
          </span>
          <h2>Tax Filing Intelligence</h2>
          <p className="sub-id">
            PAN: <strong>{data?.masked_pan || data?.pan || "—"}</strong> &nbsp;·&nbsp;
            AY: <strong>2026-27 (FY 2025-26)</strong> &nbsp;·&nbsp;
            Ref: <code>{result.submission_id}</code>
          </p>
        </div>
        {v && (
          <div className="confidence-card">
            <div className="confidence-num">
              {Math.round(v.confidence_score * 100)}
              <span>%</span>
            </div>
            <span className="confidence-label">Confidence</span>
            <div className="verdict-chips">
              <span className={v.correctness_ok ? "chip ok" : "chip bad"}>
                Correctness {v.correctness_ok ? "✓" : "✗"}
              </span>
              <span className={v.completeness_ok ? "chip ok" : "chip bad"}>
                Completeness {v.completeness_ok ? "✓" : "✗"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 2. Regime Comparison View */}
      {cmp && <RegimeComparisonView comparison={cmp} />}

      {/* 3. Action & E-Filing Receipt Box */}
      {result.receipt && (
        <div className="receipt-box">
          <div className="receipt-header">
            <h3>e-Filing Transmission & Receipt</h3>
            <span className="chip ok">Ready to File</span>
          </div>
          <p className="receipt-meta">
            Reference No: <strong>{result.receipt.reference_number}</strong> &nbsp;·&nbsp;
            Channel: <strong>{result.receipt.filing_type || "json_self_file"}</strong> &nbsp;·&nbsp;
            Form: <strong>{result.receipt.itr_form || "ITR-1"}</strong>
          </p>
          {result.receipt.instructions && (
            <pre className="receipt-instructions">{result.receipt.instructions}</pre>
          )}
          <div className="download-actions">
            {result.report_url && (
              <a
                href={result.report_url}
                target="_blank"
                rel="noreferrer"
                className="btn-download"
              >
                📄 View 8-Page CA Advisory Report (PDF)
              </a>
            )}
            <button
              type="button"
              className="btn-download btn-secondary"
              onClick={() => {
                const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(result, null, 2));
                const dlAnchorElem = document.createElement("a");
                dlAnchorElem.setAttribute("href", dataStr);
                dlAnchorElem.setAttribute("download", `${data?.pan || "ITR"}_Return_AY2026-27.json`);
                dlAnchorElem.click();
              }}
            >
              📥 Download ITR JSON
            </button>
          </div>
        </div>
      )}

      {/* 4. Verification Checklist */}
      {checks.length > 0 && (
        <div className="checks-section">
          <h3>Statutory & Computational Integrity Gates</h3>
          <div className="checks-grid">
            {checks.map((chk, idx) => (
              <div key={idx} className={`check-card ${chk.passed ? "check-pass" : "check-fail"}`}>
                <div className="check-title">
                  <span>{chk.passed ? "✓" : "✗"}</span>
                  <strong>{chk.name}</strong>
                </div>
                <p className="check-msg">{chk.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. Agent Decision Audit Trail */}
      {result.audit_trail && result.audit_trail.length > 0 && (
        <div className="audit-section">
          <h3>Agent Decision Log & Audit Trail</h3>
          <div className="timeline">
            {result.audit_trail.map((entry, idx) => (
              <div key={idx} className="timeline-item">
                <div className="timeline-dot" />
                <div className="timeline-content">
                  <div className="timeline-top">
                    <strong>{entry.agent}</strong>
                    <span className="action-tag">{entry.action}</span>
                    <small>{new Date(entry.timestamp).toLocaleTimeString()}</small>
                  </div>
                  <p>{ACTION_SUMMARY[entry.action] || entry.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
