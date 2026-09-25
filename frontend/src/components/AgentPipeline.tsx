import type { SubmissionResult, WorkflowStatus } from "../types/tax";

interface AgentPipelineProps {
  status?: WorkflowStatus | string;
  result?: SubmissionResult | null;
}

const STAGE_ORDER: Record<string, number> = {
  parsing: 1,
  computing_income: 2,
  calculating_old: 3,
  calculating_new: 3,
  comparing: 4,
  verifying: 5,
  remediating: 6,
  review_ready: 7,
  approved: 8,
  completed: 8,
};

export function AgentPipeline({ status, result }: AgentPipelineProps) {
  const currentStep = status ? STAGE_ORDER[status] ?? 0 : 0;
  const running = status
    ? [
        "parsing",
        "computing_income",
        "calculating_old",
        "calculating_new",
        "comparing",
        "verifying",
        "remediating",
      ].includes(status)
    : false;
  const done = status === "completed" || status === "approved";
  const halted = status === "manual_review" || status === "failed";

  const remediationEntries =
    result?.audit_trail?.filter(
      (e) =>
        e.agent?.toLowerCase().includes("remediation") ||
        e.action?.toLowerCase().includes("remediat") ||
        e.reason?.toLowerCase().includes("remediat")
    ) ?? [];
  const hasRemediated = remediationEntries.length > 0;

  const isStepDone = (step: number) => done || currentStep > step;
  const isStepCurrent = (step: number) => running && currentStep === step;

  return (
    <section
      className="pipeline-wrap"
      aria-label="8-Agent tax workflow pipeline"
      aria-live="polite"
    >
      <div
        className={`pipeline${running ? " running" : ""}${halted ? " halted" : ""}`}
      >
        {/* Step 1: Reading Agent */}
        <div
          className={`agent-card ${isStepDone(1) ? "active" : ""} ${isStepCurrent(1) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">01</span>
            <span className="agent-tag">Extract</span>
          </div>
          <div className="agent-body">
            <strong>Reading Agent</strong>
            <small>Form 16 (A&B), 26AS, AIS OCR</small>
          </div>
        </div>

        {/* Step 2: Income Computation */}
        <div
          className={`agent-card ${isStepDone(2) ? "active" : ""} ${isStepCurrent(2) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">02</span>
            <span className="agent-tag">Aggregate</span>
          </div>
          <div className="agent-body">
            <strong>Income Computation</strong>
            <small>5 Statutory Heads of Income</small>
          </div>
        </div>

        {/* Step 3: Dual Tax Engines (Parallel Fan-Out) */}
        <div
          className={`agent-card dual-engine-card ${isStepDone(3) ? "active" : ""} ${isStepCurrent(3) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">03</span>
            <span className="parallel-fanout-badge">⚡ Parallel Fan-Out</span>
          </div>
          <div className="agent-body">
            <strong>Dual Tax Engines</strong>
            <div className="engine-subbranches">
              <span className="engine-chip">Old Regime (Slabs + 80C/80D)</span>
              <span className="engine-chip">New Sec 115BAC (Lower Slabs)</span>
            </div>
          </div>
        </div>

        {/* Step 4: Regime Comparison */}
        <div
          className={`agent-card ${isStepDone(4) ? "active" : ""} ${isStepCurrent(4) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">04</span>
            <span className="agent-tag">Optimize</span>
          </div>
          <div className="agent-body">
            <strong>Regime Comparison</strong>
            <small>Optimal Recommendation & Breakeven</small>
          </div>
        </div>

        {/* Step 5: Verification Gates */}
        <div
          className={`agent-card ${isStepDone(5) ? "active" : ""} ${isStepCurrent(5) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">05</span>
            <span className="agent-tag">Audit</span>
          </div>
          <div className="agent-body">
            <strong>Verification Agent</strong>
            <small>11 Statutory Integrity Gates</small>
          </div>
        </div>

        {/* Step 6: Remediation Agent (Self-Healing) */}
        <div
          className={`agent-card remediation-card ${isStepDone(6) ? "active" : ""} ${isStepCurrent(6) ? "current" : ""} ${hasRemediated ? "healed" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">06</span>
            {hasRemediated ? (
              <span className="heal-badge healed">✓ Self-Healed ({remediationEntries.length})</span>
            ) : status === "remediating" ? (
              <span className="heal-badge healing">⚡ Healing...</span>
            ) : (
              <span className="heal-badge standby">Autonomous</span>
            )}
          </div>
          <div className="agent-body">
            <strong>Remediation Agent</strong>
            <small>
              {hasRemediated
                ? "Discrepancies reconciled automatically"
                : "Self-Healing TDS & Statutory Caps"}
            </small>
          </div>
        </div>

        {/* Step 7: Documentation / Advisory Report */}
        <div
          className={`agent-card ${isStepDone(7) ? "active" : ""} ${isStepCurrent(7) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">07</span>
            <span className="agent-tag">CA Report</span>
          </div>
          <div className="agent-body">
            <strong>Advisory Agent</strong>
            <small>8-Page CA-Grade Advisory PDF</small>
          </div>
        </div>

        {/* Step 8: E-Filing Boundary */}
        <div
          className={`agent-card ${isStepDone(8) ? "active" : ""} ${isStepCurrent(8) ? "current" : ""}`}
        >
          <div className="agent-card-top">
            <span className="agent-number">08</span>
            <span className="agent-tag">E-Filing</span>
          </div>
          <div className="agent-body">
            <strong>E-Filing Boundary</strong>
            <small>Official CBDT JSON & Receipt</small>
          </div>
        </div>
      </div>

      {running && (
        <div className="pipeline-status" role="status">
          <div className="pipeline-bar" aria-hidden="true" />
          <small>
            {status === "remediating"
              ? "Self-healing engine triggered — reconciling discrepancies against Form 26AS ledger…"
              : "Agents executing — parsing docs, computing 5 heads, running dual engines in parallel, and auditing…"}
          </small>
        </div>
      )}
    </section>
  );
}
