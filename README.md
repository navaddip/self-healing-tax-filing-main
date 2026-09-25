# Self-Healing Tax Advisory — India

A local-first hackathon application for FY 2025–26 / AY 2026–27. Upload salary and supporting documents, compare old/new regimes using deterministic arithmetic, inspect verification checks, and download an eight-page advisory report with source documents when verification succeeds.

**This release is an advisory demo, not a certified filing product.** Official ITR-1, ITR-2 and ITR-4 schemas are installed and enforced. The existing draft builders do not yet implement every official schedule, so export fails closed. The UI reports missing fields or schema failures instead of offering a fabricated return. No live e-filing occurs.

## Run the hackathon demo

Requirements: Python 3.11+, Node 22+, and Tesseract for scanned documents. Use a new virtual environment; a copied `.venv` from another computer is not portable.

```powershell
cd backend
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In a second terminal with the same environment and backend working directory:

```powershell
python -m app.services.jobs
```

In a third terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The worker is required: API uploads are durably queued rather than processed inside the web server. For an existing database created before migrations, back it up, verify that its `submissions` table matches migration 0001, then run `alembic stamp 0001` followed by `alembic upgrade head`. Do not stamp a fresh database.

Alternatively, `docker compose up --build` starts PostgreSQL, migrations, backend, worker and frontend. Open http://localhost:8080. Ports bind to localhost and default credentials are for local demonstration only.

## Implemented safeguards

- Real CBDT Draft 4 schemas, source provenance and SHA-256 verification; validation runs before any filing file or successful receipt is emitted.
- Missing DOB, full account number, address, identity or supporting payment details produce explicit errors. PAN is excluded from export filenames.
- 80TTA/80TTB are limited to declared qualifying interest. Chapter VI-A components reconcile with their total after the GTI cap.
- Separate 80D family/parents limits, 80E eight-year inputs, and categorized 80G percentage/qualifying-limit calculations. Unsupported eligibility facts require review.
- Ordinary advance-tax interest includes 234B/234C, dated instalments, tolerance bands and resident senior exemption. Special-income timing relief and dated self-assessment payments still require manual review.
- Rule-pack assessment years, standard non-audit due dates, schema selection and report headers; FY 2026–27 remains provisional and is unavailable for verified upload runs.
- CSV ingestion, 20 MiB per document, ten documents per request, content/MIME checks, bounded PDF/image sizes, and explicit rejection of locked PDFs and active PDF content.
- A database queue with exclusive leases, heartbeat renewal, three attempts, stale-job recovery and cancellation between graph nodes. SQLite workflow checkpoints survive worker restarts.
- All PDFs/images are appended to the report; CSV sources are embedded attachments.
- One configurable verification threshold (default 0.97) governs both workflow and report downloads.

## AI and audit scope

Layout parsing and OCR provide financial facts. Ollama can classify remediation failures. `ENABLE_VISION=true` enables optional diagnostic extraction for unrecognized documents; hints are logged by field name and never substituted for verified financial facts. Chroma retrieval is not implemented and is not required by the active workflow. The audit export is ordinary JSON, not an immutable ledger or independent professional sign-off.

## Tests

```powershell
python -m pytest backend/tests --cov=backend/app --cov-fail-under=75
python -m ruff check backend/app backend/tests --select E9,F63,F7,F82
npm --prefix frontend test
npm --prefix frontend run build
```

CI runs backend tests and coverage, critical Python lint checks, migrations, frontend tests and TypeScript production builds. The tests include upload rejection, queue recovery, checkpoint persistence and source packaging. Private PDFs and local virtual environments are excluded from Git; do not commit real PANs or account details as fixtures.

## Deployment boundary

See [release status](docs/release-status.md) and [data policy](docs/data-policy.md). Production still requires complete official ITR schedule mappings and portal business-rule validation, expanded statutory review, isolated malware scanning, authenticated per-user access, deployment-specific encryption/key management and operational load testing. JSON schema validity alone does not establish legal correctness or portal acceptance.
