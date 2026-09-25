import { FormEvent, useEffect, useState } from "react";
import { getSubmission, submitDocument } from "./api/submissions";
import { AgentPipeline } from "./components/AgentPipeline";
import { ResultPanel } from "./components/ResultPanel";
import type { SubmissionResult } from "./types/tax";

const TERMINAL = new Set(["completed", "manual_review", "failed"]);

async function pollUntilDone(
  submissionId: string,
  onUpdate: (r: SubmissionResult) => void,
  attempts = 60,
): Promise<SubmissionResult> {
  let latest: SubmissionResult | undefined;
  for (let i = 0; i < attempts; i += 1) {
    latest = await getSubmission(submissionId);
    onUpdate(latest);
    if (TERMINAL.has(latest.status)) return latest;
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error(
    "Processing is taking longer than expected. Reload this page later to see the result.",
  );
}

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<SubmissionResult>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      document.documentElement.style.setProperty('--mouse-x', `${e.clientX}px`);
      document.documentElement.style.setProperty('--mouse-y', `${e.clientY}px`);
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    const submissionId = new URLSearchParams(window.location.search).get(
      "submission",
    );
    if (!submissionId) return;
    setBusy(true);
    pollUntilDone(submissionId, setResult)
      .then(setResult)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Load failed"),
      )
      .finally(() => setBusy(false));
  }, []);

  function followRerun(saved: SubmissionResult) {
    setResult(saved);
    setError("");
    setBusy(true);
    pollUntilDone(saved.submission_id, setResult)
      .then(setResult)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Load failed"),
      )
      .finally(() => setBusy(false));
  }

  function resetRun() {
    setFiles([]);
    setResult(undefined);
    setError("");
    setDragging(false);
    window.history.replaceState({}, "", window.location.pathname);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!files.length) return;
    setBusy(true);
    setError("");
    setResult(undefined);
    try {
      const queued = await submitDocument(files);
      setResult(queued);
      window.history.replaceState({}, "", `?submission=${queued.submission_id}`);
      setResult(await pollUntilDone(queued.submission_id, setResult));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <nav>
        <div className="brand">
          <span>IN</span>
          <strong>TaxFlow India · AY 2026-27</strong>
        </div>
        <div className="nav-right">
          {(result || busy) && (
            <button
              type="button"
              className="start-over"
              onClick={resetRun}
              disabled={busy}
            >
              {busy ? "Running…" : "Start over"}
            </button>
          )}
          <div className="local-badge">AY 2026-27 · Section 115BAC · Auditable</div>
        </div>
      </nav>

      <header className="hero">
        <div className="eyebrow">Self-Healing Indian Income Tax Advisory</div>
        <h1>Indian Tax Documents In.<br />Optimal Regime & ITR Out.</h1>
      </header>

      <AgentPipeline status={busy ? "computing_income" : result?.status} result={result} />

      <section className="workspace">
        <form className="upload-card" onSubmit={handleSubmit}>
          <div className="upload-icon">↑</div>
          <h2>Start a Filing & Advisory Run</h2>
          <p>Upload Form 16 (Part A & B), Form 26AS, AIS, Broker P&L CSV, or Rent Receipts.</p>
          <label
            className={`file-field${dragging ? " dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              const dropped = Array.from(event.dataTransfer.files ?? []);
              if (dropped.length) setFiles(dropped);
            }}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.csv"
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
            <span>
              {dragging
                ? "Drop to upload"
                : files.length === 0
                  ? "Drop files here, or choose Form 16 / 26AS / AIS / CSV"
                  : files.length === 1
                    ? files[0].name
                    : `${files.length} files selected`}
            </span>
          </label>
          {files.length > 1 && (
            <ul className="file-list">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`}>{f.name}</li>
              ))}
            </ul>
          )}
          <button
            className={busy ? "working" : ""}
            disabled={!files.length || busy}
            aria-busy={busy}
          >
            {busy ? "Agents are working…" : "Process securely"}
          </button>
          <small>PDF · PNG · JPG · multiple documents merged into one return</small>
          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}
        </form>


      </section>

      {result && <ResultPanel result={result} onResubmit={followRerun} />}

      <footer>
        <span>FastAPI · LangGraph · SQLite · ChromaDB · React</span>
        <span>Deterministic Indian Tax Engine (FY 2025-26 · AY 2026-27) · Grounded Evidence</span>
      </footer>

    </main>
  );
}
