from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, HTTPException
from app.core.config import get_settings
from app.services.documents.validation import validate_document


class StorageService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        for name in ("uploads", "previews", "generated", "chroma"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    async def save_upload(self, submission_id: str, upload: UploadFile) -> Path:
        suffix = Path(upload.filename or "document").suffix.lower()
        target_dir = self.root / "uploads" / submission_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{uuid4().hex}{suffix}"
        try:
            total = 0
            with target.open("wb") as stream:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > get_settings().max_upload_bytes:
                        raise HTTPException(413, "Document exceeds upload size limit")
                    stream.write(chunk)
            validate_document(target, upload.content_type)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return target

    def report_path(self, submission_id: str) -> Path:
        target = self.root / "generated" / submission_id
        target.mkdir(parents=True, exist_ok=True)
        return target / "tax_filing_report.pdf"

    def itr_json_path(self, submission_id: str) -> Path:
        target = self.root / "generated" / submission_id
        target.mkdir(parents=True, exist_ok=True)
        return target / "itr_return.json"

    def audit_path(self, submission_id: str) -> Path:
        target = self.root / "generated" / submission_id
        target.mkdir(parents=True, exist_ok=True)
        return target / "audit_trail.json"
