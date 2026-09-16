import { useState } from "react";
import type { RegimeComparison } from "../types/tax";
import { formatINR } from "../utils/inr";

interface Props {
  comparison: RegimeComparison;
}

export function RegimeComparisonView({ comparison }: Props) {
  const { old: oldRes, new: newRes, recommended, savings, deltas, breakeven_deduction_amount, deductions_forfeited_if_new, reasons } = comparison;
  const isNew = recommended === "new";
  const numSavings = typeof savings === "number" ? savings : parseFloat(String(savings));

  // Interactive sensitivity slider
  const [extraDeduction, setExtraDeduction] = useState(0);

  // Approximate sensitivity tax adjustment (marginal rate 31.2% or 20.8%)
  const marginalRate = parseFloat(String(oldRes.income.gross_total_income)) > 1000000 ? 0.312 : 0.208;
  const simulatedOldTax = Math.max(0, Math.round(parseFloat(String(oldRes.total_tax_liability)) - extraDeduction * marginalRate));
  const newTaxNum = Math.round(parseFloat(String(newRes.total_tax_liability)));
  const simulatedSavings = newTaxNum - simulatedOldTax;

  return (
    <div className="regime-comparison-container">
      {/* 1. Recommendation Banner */}
      <div className={`recommendation-banner ${isNew ? "banner-new" : "banner-old"}`}>
        <div className="banner-left">
          <span className="badge-recommendation">RECOMMENDED FILING CHOICE</span>
          <h2>
            {isNew ? "New Tax Regime (Section 115BAC)" : "Old Tax Regime (With Deductions)"}
          </h2>
          <p className="banner-savings">
            {numSavings > 0 ? (
              <>
                You save <strong>{formatINR(numSavings)}</strong> by choosing the{" "}
                <span className="highlight-regime">{isNew ? "New" : "Old"} Regime</span>.
              </>
            ) : (
              "Both regimes result in identical tax liability. Defaulting to New Regime u/s 115BAC."
            )}
          </p>
          <div className="banner-tags">
            <span className="tag-pill">AY 2026-27 (FY 2025-26)</span>
            <span className="tag-pill">
              {comparison.switch_allowed_annually
                ? "Annual switch permitted (Salaried)"
                : "One-time switch (Business income)"}
            </span>
            {comparison.form_10iea_required && (
              <span className="tag-pill tag-warning">Form 10-IEA Required</span>
            )}
          </div>
        </div>
        <div className="banner-right">
          <div className="savings-pill">
            <span className="pill-label">Net Advantage</span>
            <span className="pill-val">{formatINR(numSavings)}</span>
          </div>
        </div>
      </div>

      {/* 2. Side-by-Side Regime Cards */}
      <div className="regime-cards-grid">
        {/* Old Regime Card */}
        <div className={`regime-card ${recommended === "old" ? "card-recommended" : ""}`}>
          <div className="card-header">
            <div>
              <h3>Old Tax Regime</h3>
              <small>Retains Chapter VI-A, HRA & SOP Interest</small>
            </div>
            {recommended === "old" && <span className="chip-winner">Optimal</span>}
          </div>
          <div className="card-metrics">
            <div className="metric-row">
              <span>Gross Total Income:</span>
              <strong>{formatINR(oldRes.income.gross_total_income)}</strong>
            </div>
            <div className="metric-row">
              <span>Deductions & Exemptions:</span>
              <strong className="text-deduction">
                - {formatINR(Number(oldRes.income.chapter_via_total) + Number(oldRes.income.standard_deduction))}
              </strong>
            </div>
            <div className="metric-row">
              <span>Taxable Total Income:</span>
              <strong>{formatINR(oldRes.income.total_income)}</strong>
            </div>
            <div className="metric-divider" />
            <div className="metric-row">
              <span>Tax before Cess:</span>
              <span>{formatINR(oldRes.tax_after_rebate)}</span>
            </div>
            <div className="metric-row">
              <span>Health & Education Cess (4%):</span>
              <span>{formatINR(oldRes.cess)}</span>
            </div>
            <div className="metric-row total-liability">
              <span>Total Tax Liability:</span>
              <strong className="text-liability">{formatINR(oldRes.total_tax_liability)}</strong>
            </div>
            <div className="metric-row">
              <span>Taxes Paid (TDS / Advance):</span>
              <span>{formatINR(oldRes.taxes_paid_total)}</span>
            </div>
            <div className="metric-row final-settlement">
              <span>{Number(oldRes.refund_due) > 0 ? "Refund Due:" : "Tax Payable:"}</span>
              <strong className={Number(oldRes.refund_due) > 0 ? "text-refund" : "text-payable"}>
                {Number(oldRes.refund_due) > 0 ? formatINR(oldRes.refund_due) : formatINR(oldRes.tax_payable)}
              </strong>
            </div>
          </div>
        </div>

        {/* New Regime Card */}
        <div className={`regime-card ${recommended === "new" ? "card-recommended" : ""}`}>
          <div className="card-header">
            <div>
              <h3>New Regime (Sec 115BAC)</h3>
              <small>Lower Slabs + ₹75,000 Standard Deduction</small>
            </div>
            {recommended === "new" && <span className="chip-winner">Optimal</span>}
          </div>
          <div className="card-metrics">
            <div className="metric-row">
              <span>Gross Total Income:</span>
              <strong>{formatINR(newRes.income.gross_total_income)}</strong>
            </div>
            <div className="metric-row">
              <span>Deductions & Exemptions:</span>
              <strong className="text-deduction">
                - {formatINR(Number(newRes.income.chapter_via_total) + Number(newRes.income.standard_deduction))}
              </strong>
            </div>
            <div className="metric-row">
              <span>Taxable Total Income:</span>
              <strong>{formatINR(newRes.income.total_income)}</strong>
            </div>
            <div className="metric-divider" />
            <div className="metric-row">
              <span>Tax after Rebate (87A):</span>
              <span>{formatINR(newRes.tax_after_rebate)}</span>
            </div>
            <div className="metric-row">
              <span>Health & Education Cess (4%):</span>
              <span>{formatINR(newRes.cess)}</span>
            </div>
            <div className="metric-row total-liability">
              <span>Total Tax Liability:</span>
              <strong className="text-liability">{formatINR(newRes.total_tax_liability)}</strong>
            </div>
            <div className="metric-row">
              <span>Taxes Paid (TDS / Advance):</span>
              <span>{formatINR(newRes.taxes_paid_total)}</span>
            </div>
            <div className="metric-row final-settlement">
              <span>{Number(newRes.refund_due) > 0 ? "Refund Due:" : "Tax Payable:"}</span>
              <strong className={Number(newRes.refund_due) > 0 ? "text-refund" : "text-payable"}>
                {Number(newRes.refund_due) > 0 ? formatINR(newRes.refund_due) : formatINR(newRes.tax_payable)}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Interactive Breakeven & Sensitivity Analysis */}
      <div className="breakeven-card">
        <div className="breakeven-header">
          <div>
            <h3>Deduction Breakeven & Sensitivity Analysis</h3>
            <p>
              Under current laws, the Old Regime becomes optimal once your total deductions exceed{" "}
              <strong>{formatINR(breakeven_deduction_amount)}</strong>.
            </p>
          </div>
          <div className="breakeven-target">
            <span>Breakeven Threshold</span>
            <strong>{formatINR(breakeven_deduction_amount)}</strong>
          </div>
        </div>

        <div className="slider-box">
          <label htmlFor="deduction-slider">
            What if you invested more? Simulate additional deductions:{" "}
            <strong>+{formatINR(extraDeduction)}</strong>
          </label>
          <input
            id="deduction-slider"
            type="range"
            min="0"
            max="600000"
            step="10000"
            value={extraDeduction}
            onChange={(e) => setExtraDeduction(Number(e.target.value))}
            className="slider-input"
          />
          <div className="slider-results">
            <div>
              <span>Simulated Old Regime Tax:</span>
              <strong>{formatINR(simulatedOldTax)}</strong>
            </div>
            <div>
              <span>New Regime Tax:</span>
              <strong>{formatINR(newTaxNum)}</strong>
            </div>
            <div>
              <span>Advantage:</span>
              <strong className={simulatedSavings >= 0 ? "text-refund" : "text-payable"}>
                {simulatedSavings >= 0
                  ? `New Regime by ${formatINR(simulatedSavings)}`
                  : `Old Regime by ${formatINR(Math.abs(simulatedSavings))}`}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Forfeited Deductions in New Regime */}
      {deductions_forfeited_if_new && Object.keys(deductions_forfeited_if_new).length > 0 && (
        <div className="forfeited-section">
          <h3>Deductions & Exemptions Forfeited under New Regime</h3>
          <p>The New Regime bars these claims in exchange for concessional slab rates:</p>
          <div className="forfeited-grid">
            {Object.entries(deductions_forfeited_if_new).map(([desc, amt]) => (
              <div key={desc} className="forfeited-item">
                <span className="forfeited-title">{desc}</span>
                <strong className="forfeited-amount">{formatINR(amt)}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. Line-by-Line Comparison Table */}
      <div className="delta-table-wrap">
        <h3>Line-by-Line Comparison (AY 2026-27)</h3>
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Particulars</th>
              <th className="th-num">Old Regime</th>
              <th className="th-num">New Regime</th>
              <th className="th-num">Difference</th>
            </tr>
          </thead>
          <tbody>
            {deltas.map((d) => {
              const diff = d.delta;
              const isFavorable = diff < 0; // lower under new
              return (
                <tr key={d.line}>
                  <td>{d.line}</td>
                  <td className="td-num">{formatINR(d.old_value)}</td>
                  <td className="td-num">{formatINR(d.new_value)}</td>
                  <td className={`td-num font-bold ${diff === 0 ? "" : isFavorable ? "text-refund" : "text-payable"}`}>
                    {diff === 0 ? "—" : `${isFavorable ? "↓ " : "↑ "}${formatINR(Math.abs(diff))}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 6. Statutory Reasoning */}
      {reasons && reasons.length > 0 && (
        <div className="reasons-box">
          <h4>Advisory Rationale & Legal Grounding</h4>
          <ul>
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
