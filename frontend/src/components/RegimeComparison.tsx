import { useEffect, useState } from "react";
import type { RegimeComparison } from "../types/tax";
import { formatINR } from "../utils/inr";
import { getSensitivity } from "../api/submissions";

interface Props {
  comparison: RegimeComparison;
  submissionId?: string;
  assessmentYear?: string;
  financialYear?: string;
}

export function RegimeComparisonView({ comparison, submissionId, assessmentYear, financialYear }: Props) {
  const { old: oldRes, new: newRes, recommended, savings, deltas, breakeven_deduction_amount, deductions_forfeited_if_new, reasons } = comparison;
  const isNew = recommended === "new";
  const numSavings = typeof savings === "number" ? savings : parseFloat(String(savings));

  const [extraDeduction, setExtraDeduction] = useState(0);
  const baseOldTax = Math.round(parseFloat(String(oldRes.total_tax_liability)));
  const newTaxNum = Math.round(parseFloat(String(newRes.total_tax_liability)));
  const [simulatedOldTax, setSimulatedOldTax] = useState<number>(baseOldTax);
  const [_calculating, setCalculating] = useState(false);

  useEffect(() => {
    if (!submissionId || extraDeduction === 0) {
      setSimulatedOldTax(baseOldTax);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setCalculating(true);
        const results = await getSensitivity(submissionId, [extraDeduction]);
        if (results && results.length > 0) {
          setSimulatedOldTax(Math.round(results[0].old_tax));
        }
      } catch (err) {
        const marginalRate = parseFloat(String(oldRes.income.gross_total_income)) > 1000000 ? 0.312 : 0.208;
        setSimulatedOldTax(Math.max(0, Math.round(baseOldTax - extraDeduction * marginalRate)));
      } finally {
        setCalculating(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [submissionId, extraDeduction, baseOldTax, oldRes.income.gross_total_income]);

  const simulatedSavings = simulatedOldTax - newTaxNum;

  return (
    <div className="regime-comparison-container">
      {/* Recommendation Banner */}
      <div className={`recommendation-banner ${isNew ? "banner-new" : "banner-old"}`}>
        <div className="banner-left">
          <span className="badge-recommendation">Recommended Filing Choice</span>
          <h2>
            {isNew ? "New Tax Regime" : "Old Tax Regime"}
            <span className="banner-h2-sub">
              {isNew ? " · Section 115BAC" : " · With deductions"}
            </span>
          </h2>
          <p className="banner-savings">
            {numSavings > 0 ? (
              <>
                Filing under this regime saves you{" "}
                <strong>{formatINR(numSavings)}</strong> versus the alternative.
              </>
            ) : (
              "Both regimes result in identical tax liability. Defaulting to New Regime u/s 115BAC."
            )}
          </p>
          <div className="banner-tags">
            {(assessmentYear || financialYear) && (
              <span className="tag-pill">
                AY {assessmentYear}
                {financialYear ? ` · FY ${financialYear}` : ""}
              </span>
            )}
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
            <span className="pill-sub">
              vs {isNew ? "Old" : "New"} Regime
            </span>
          </div>
        </div>
      </div>

      {/* Side-by-Side Cards */}
      <div className="regime-cards-grid">
        <RegimeCard
          title="Old Tax Regime"
          subtitle="Chapter VI-A, HRA, home loan interest allowed"
          isRecommended={recommended === "old"}
          data={oldRes}
          rebateLabel="Tax after Rebate u/s 87A"
        />
        <RegimeCard
          title="New Tax Regime"
          subtitle="Section 115BAC · concessional slabs · ₹75,000 standard deduction"
          isRecommended={recommended === "new"}
          data={newRes}
          rebateLabel="Tax after Rebate u/s 87A"
        />
      </div>

      {/* Breakeven + Sensitivity */}
      <div className="breakeven-card">
        <div className="breakeven-header">
          <div>
            <h4>Deduction Breakeven &amp; Sensitivity</h4>
            <p>
              The Old Regime becomes optimal once total deductions exceed{" "}
              <strong>{formatINR(breakeven_deduction_amount)}</strong>. Move the slider to see how
              extra 80C / 80D / HRA claims change the picture.
            </p>
          </div>
          <div className="breakeven-target">
            <span>Breakeven</span>
            <strong>{formatINR(breakeven_deduction_amount)}</strong>
          </div>
        </div>

        <div className="slider-box">
          <label htmlFor="deduction-slider" className="slider-label">
            <span>Additional deductions to simulate</span>
            <strong>+ {formatINR(extraDeduction)}</strong>
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
          <div className="slider-scale">
            <span>₹ 0</span>
            <span>₹ 3 L</span>
            <span>₹ 6 L</span>
          </div>
          <div className="slider-results">
            <div className="slider-result-cell">
              <span>Simulated Old Regime Tax</span>
              <strong>{formatINR(simulatedOldTax)}</strong>
            </div>
            <div className="slider-result-cell">
              <span>New Regime Tax</span>
              <strong>{formatINR(newTaxNum)}</strong>
            </div>
            <div className="slider-result-cell slider-result-advantage">
              <span>Result</span>
              <strong className={simulatedSavings >= 0 ? "text-refund" : "text-payable"}>
                {simulatedSavings >= 0
                  ? `New wins by ${formatINR(simulatedSavings)}`
                  : `Old wins by ${formatINR(Math.abs(simulatedSavings))}`}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Forfeited under New */}
      {deductions_forfeited_if_new && Object.keys(deductions_forfeited_if_new).length > 0 && (
        <div className="forfeited-section">
          <div className="forfeited-head">
            <h4>Deductions Forfeited under New Regime</h4>
            <p>These claims are unavailable if you elect Section 115BAC.</p>
          </div>
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

      {/* Line-by-Line */}
      <div className="delta-table-wrap">
        <div className="delta-table-head">
          <h4>Line-by-Line Comparison</h4>
          <p>How each computational step differs between the two regimes.</p>
        </div>
        <div className="table-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Particulars</th>
                <th className="th-num">Old Regime</th>
                <th className="th-num">New Regime</th>
                <th className="th-num">Difference (New − Old)</th>
              </tr>
            </thead>
            <tbody>
              {deltas.map((d) => {
                const diff = Number(d.delta);
                const isFavorable = diff < 0;
                return (
                  <tr key={d.line}>
                    <td>{d.line}</td>
                    <td className="td-num">{formatINR(d.old_value)}</td>
                    <td className="td-num">{formatINR(d.new_value)}</td>
                    <td className={`td-num td-diff ${diff === 0 ? "" : isFavorable ? "text-refund" : "text-payable"}`}>
                      {diff === 0
                        ? "—"
                        : `${isFavorable ? "▼" : "▲"} ${formatINR(Math.abs(diff))}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Rationale */}
      {reasons && reasons.length > 0 && (
        <div className="reasons-box">
          <h4>Advisory Rationale</h4>
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

function RegimeCard({
  title,
  subtitle,
  isRecommended,
  data,
  rebateLabel,
}: {
  title: string;
  subtitle: string;
  isRecommended: boolean;
  data: RegimeComparison["old"];
  rebateLabel: string;
}) {
  const isRefund = Number(data.refund_due) > 0;
  const surcharge = Number(data.surcharge);

  return (
    <div className={`regime-card ${isRecommended ? "card-recommended" : ""}`}>
      <div className="card-header">
        <div>
          <h4>{title}</h4>
          <small>{subtitle}</small>
        </div>
        {isRecommended && <span className="chip-winner">Optimal</span>}
      </div>
      <dl className="card-metrics">
        <div className="metric-row">
          <dt>Gross Total Income</dt>
          <dd>{formatINR(data.income.gross_total_income)}</dd>
        </div>
        <div className="metric-row">
          <dt>Chapter VI-A deductions</dt>
          <dd className="text-deduction">− {formatINR(data.income.chapter_via_total)}</dd>
        </div>
        <div className="metric-row metric-row-emphasis">
          <dt>Taxable Income</dt>
          <dd>{formatINR(data.income.total_income)}</dd>
        </div>
        <div className="metric-divider" />
        <div className="metric-row">
          <dt>{rebateLabel}</dt>
          <dd>{formatINR(data.tax_after_rebate)}</dd>
        </div>
        {surcharge > 0 && (
          <div className="metric-row">
            <dt>Surcharge</dt>
            <dd>{formatINR(surcharge)}</dd>
          </div>
        )}
        <div className="metric-row">
          <dt>Health &amp; Education Cess (4%)</dt>
          <dd>{formatINR(data.cess)}</dd>
        </div>
        <div className="metric-row total-liability">
          <dt>Total Tax Liability</dt>
          <dd>{formatINR(data.total_tax_liability)}</dd>
        </div>
        <div className="metric-row">
          <dt>Taxes paid &amp; relief (TDS / Advance / Sec 89)</dt>
          <dd>{formatINR(data.taxes_paid_total)}</dd>
        </div>
        <div className="metric-row final-settlement">
          <dt>{isRefund ? "Refund due to you" : "Tax payable"}</dt>
          <dd className={isRefund ? "text-refund" : "text-payable"}>
            {isRefund ? formatINR(data.refund_due) : formatINR(data.tax_payable)}
          </dd>
        </div>
      </dl>
    </div>
  );
}
