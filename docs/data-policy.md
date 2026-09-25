# Data handling and retention

This application stores uploaded tax documents, generated reports, audit JSON, workflow checkpoints and submission results. These can contain personal and financial information even when the top-level PAN is masked. Masking is not anonymization.

Filing details the taxpayer types in (date of birth, address, mobile, email, bank account, father's name) are stored unmasked in `submissions.filing_details_json`, because every re-run and the generated ITR JSON need them. Submission results mask the PAN, bank account number and mobile. Treat the database and generated ITR JSON files as sensitive.

## Local demonstration

Use synthetic documents on a trusted machine. API-key authentication is optional only for this local demo. Compose publishes only loopback ports. There is no per-user ownership model; do not expose the demo to unrelated users.

## Retention and deletion

The default retention period is seven days (`RETENTION_DAYS`). From the backend directory, run `python -m app.services.retention` to list eligible terminal submissions. Add `--apply` to remove their source files, generated artifacts, checkpoint rows and database records. Active leases and queued jobs are skipped. Schedule that command through your deployment scheduler; this application does not silently delete existing local files on startup.

Deletion is logical deletion, not forensic erasure. Backups, SQLite free pages, database logs and volume snapshots require their own expiration policy. Encrypted volumes and destruction/rotation of backup keys are operational responsibilities. Never include taxpayer documents in Git or public CI artifacts.

## Encryption and access

`CHECKPOINT_ENCRYPTION_KEY` enables AES authenticated encryption for serialized workflow checkpoints (16, 24 or 32 UTF-8 bytes; use a randomly generated secret and retain it across restarts). It does not encrypt source PDFs, generated reports, checkpoint metadata or database result JSON. Use encrypted disks/volumes and encrypted database/backups for those stores. Supply keys through a secret manager, not checked-in `.env` files. Enable TLS and authenticated per-user authorization before any remote deployment.

## Uploaded content

The ingress checks extensions, MIME and actual content, rejects encrypted PDFs, PDF JavaScript/launch actions and embedded attachments, and bounds file/page/image sizes. These checks are not an antivirus engine. Production processing must also use an isolated scanner/sandbox, resource limits and regularly patched PDF/OCR dependencies. Passwords are not collected or retained; upload an unlocked copy locally when appropriate.
