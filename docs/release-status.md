# Hackathon release status

Implemented: missing-field filing gates; all three official AY 2026–27 schemas and checksum manifest; fail-closed export; ordinary deduction/interest corrections; rule-pack date propagation; upload validation; durable queue/checkpoints/retries/cancellation; complete source packaging; migrations; Docker services; CI; frontend tests; retention tooling and checkpoint encryption option.

## Remaining production work

1. Replace the simplified ITR draft mappings with complete official schedules for each supported taxpayer category, including registered software metadata, itemized TDS/TCS, dated challans and portal business validations. Current payloads are correctly blocked by the official validator.
2. Independently verify the FY 2026–27 pack, special-income advance-tax relief, dated self-assessment payments, complex capital gains/loss carry-forwards, eligibility exceptions and notified due-date extensions. The current release does not certify all Indian tax scenarios.
3. Add per-user authentication/authorization, isolated malware scanning, managed encryption for files/database/backups, key rotation and automated retention scheduling.
4. Exercise Docker images and multi-worker crash/recovery under deployment load; shared SQLite checkpoints are intended for a local demo. Use PostgreSQL checkpoints and stronger side-effect fencing for multi-host operation.
5. Expand ingestion tests with consented, sanitized real-world documents and add broader backend static type checking. Current CI includes critical Python lint and frontend TypeScript checking.

Existing user changes, deleted legacy code and presentation assets are preserved. Generated root PDFs, audit files, temporary directories and local virtual environments are ignored, not deleted.
