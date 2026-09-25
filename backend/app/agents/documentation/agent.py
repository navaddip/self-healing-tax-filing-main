import json
from datetime import datetime, timezone
from pathlib import Path

from app.itr.schema_loader import MissingFilingData, SchemaValidationError
from app.schemas import AuditEntry, FilingReceipt, SubmissionResult
from app.services.efile import EFileBackend, JsonSelfFileBackend
from app.services.pdf.comparison_report import ProfessionalReportService


class DocumentationAgent:
    name = "Documentation Agent"

    def __init__(
        self,
        reports: ProfessionalReportService,
        efile: EFileBackend | None = None,
    ):
        self.reports = reports
        self.efile = efile or JsonSelfFileBackend()

    def run(
        self,
        result: SubmissionResult,
        output: Path,
        preview: Path | None = None,
    ) -> tuple[FilingReceipt, Path, AuditEntry]:
        if not result.verification or not result.verification.valid:
            raise ValueError("Cannot generate final report before verification")

        # 1. Generate CA-grade Advisory Report PDF
        receipt, path, log = self.reports.run(result, output, preview or output)

        # 2. Generate and write schema-compliant ITR JSON payload
        try:
            self.efile.submit(result, output_dir=output.parent)
        except MissingFilingData as exc:
            receipt.filing_status = "advisory_only"
            receipt.instructions = (
                f"Your {receipt.itr_form} file needs a few personal details that a Form 16 does not "
                "contain. Add them below to create the file."
            )
            log.details["filing_export_blocked"] = str(exc)
        except SchemaValidationError as exc:
            receipt.filing_status = "advisory_only"
            receipt.export_supported = False
            receipt.instructions = (
                f"{receipt.itr_form} file export isn't supported for this return yet. "
                "Use the advisory report to file on the income-tax portal."
            )
            log.details["filing_export_blocked"] = str(exc)
        final_receipt = result.receipt or receipt

        # 3. Write complete audit trail JSON
        audit_file = output.parent / "audit_trail.json"
        audit_data = [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry
            for entry in result.audit_trail
        ]
        audit_file.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")

        return final_receipt, path, log
