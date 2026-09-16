const agents = [
  ["01", "Reading", "Form 16 / 26AS / AIS"],
  ["02", "Income Computation", "5 Heads of Income"],
  ["03", "Dual Tax Engines", "Old & New Parallel"],
  ["04", "Regime Comparison", "Optimal Selection"],
  ["05", "Verification", "11 Integrity Gates"],
  ["06", "Remediation", "Self-Healing TDS"],
  ["07", "Advisory Report", "8-Page CA Report"],
  ["08", "E-Filing Boundary", "ITR JSON & Receipt"],
];

const RUNNING = new Set([
  "parsing",
  "computing_income",
  "calculating_old",
  "calculating_new",
  "comparing",
  "verifying",
  "remediating",
]);

export function AgentPipeline({ status }: { status?: string }) {
  const running = !!status && RUNNING.has(status);
  const done = status === "completed" || status === "approved";
  const halted = status === "manual_review" || status === "failed";

  return (
    <section
      className="pipeline-wrap"
      aria-label="Agent workflow"
      aria-live="polite"
    >
      <div
        className={`pipeline${running ? " running" : ""}${halted ? " halted" : ""}`}
      >
        {agents.map(([number, title, subtitle]) => (
          <div className={`agent-card ${done ? "active" : ""}`} key={title}>
            <span className="agent-number">{number}</span>
            <div>
              <strong>{title}</strong>
              <small>{subtitle}</small>
            </div>
          </div>
        ))}
      </div>
      {running && (
        <div className="pipeline-status" role="status">
          <div className="pipeline-bar" aria-hidden="true" />
          <small>Agents processing — parsing, computing heads, running dual engines, and verifying…</small>
        </div>
      )}
    </section>
  );
}
