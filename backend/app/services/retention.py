"""Delete expired, terminal submissions: python -m app.services.retention.
Dry-run by default; pass --apply to remove files, checkpoints and database rows.
"""
import argparse
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from langgraph.checkpoint.sqlite import SqliteSaver
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.submission import SubmissionRecord, WorkflowJob

def remove_submission_files(root, submission_id):
    from uuid import UUID
    if str(UUID(submission_id)) != submission_id:
        raise ValueError("Invalid submission ID")
    root = root.resolve()
    for kind in ("uploads", "previews", "generated"):
        target = (root / kind / submission_id).resolve()
        if not target.is_relative_to(root / kind):
            raise ValueError("Unsafe retention path")
        if target.exists():
            shutil.rmtree(target)
    checkpoint = root / "checkpoints.db"
    if checkpoint.exists():
        with sqlite3.connect(checkpoint) as connection:
            SqliteSaver(connection).delete_thread(submission_id)

def purge(apply=False):
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
    with SessionLocal() as db:
        records = list(db.scalars(select(SubmissionRecord).where(SubmissionRecord.created_at < cutoff)))
        for record in records:
            job = db.get(WorkflowJob, record.id)
            # A cancelled process can still be unwinding; wait for its lease.
            import time
            if job and (job.status in ("queued", "running") or job.lease_until > time.time()):
                continue
            print(record.id)
            if apply:
                remove_submission_files(settings.storage_root, record.id)
                if job:
                    db.delete(job)
                db.delete(record)
        if apply:
            db.commit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    purge(parser.parse_args().apply)
