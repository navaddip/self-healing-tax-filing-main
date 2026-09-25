"""Database-backed queue with leased claims, retries, recovery and cancellation.
Run one or more dedicated workers: python -m app.services.jobs.
Only paths and IDs are queued; taxpayer facts stay out of the queue payload.
"""
import json
import logging
import threading
import time
from uuid import uuid4
from sqlalchemy import or_, and_, select, update
from app.db.session import SessionLocal
from app.models.submission import WorkflowJob, SubmissionRecord
from app.repositories.submissions import SubmissionRepository

log = logging.getLogger(__name__)
LEASE_SECONDS = 300
MAX_ATTEMPTS = 3

def enqueue(db, submission_id, payload):
    db.add(WorkflowJob(id=submission_id, payload=json.dumps(payload), status="queued", attempts=0, lease_until=0))
    db.commit()

def claim(db):
    now = time.time()
    eligible = or_(and_(WorkflowJob.status == "queued", WorkflowJob.lease_until <= now),
                   and_(WorkflowJob.status == "running", WorkflowJob.lease_until < now))
    # Expired final attempts become visible failures rather than stranded jobs.
    for job in db.scalars(select(WorkflowJob).where(eligible, WorkflowJob.attempts >= MAX_ATTEMPTS)):
        job.status = "failed"
        record = db.get(SubmissionRecord, job.id)
        if record:
            SubmissionRepository(db).save_result(record, {"status": "failed", "error": "Processing exhausted retries; upload again"})
    db.commit()
    candidate = db.scalar(select(WorkflowJob.id).where(eligible, WorkflowJob.attempts < MAX_ATTEMPTS).limit(1))
    if not candidate:
        return None
    token = str(uuid4())
    changed = db.execute(update(WorkflowJob).where(WorkflowJob.id == candidate, eligible).values(
        status="running", token=token, lease_until=now + LEASE_SECONDS, attempts=WorkflowJob.attempts + 1))
    db.commit()
    if not changed.rowcount:
        return None
    db.expire_all()
    job = db.get(WorkflowJob, candidate)
    return job.id, token, json.loads(job.payload)

def process_one():
    with SessionLocal() as db:
        item = claim(db)
    if item is None:
        return False
    job_id, token, payload = item
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(30):
            with SessionLocal() as db:
                db.execute(update(WorkflowJob).where(WorkflowJob.id == job_id, WorkflowJob.token == token,
                    WorkflowJob.status == "running").values(lease_until=time.time() + LEASE_SECONDS))
                db.commit()
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        from app.api.dependencies.services import get_workflow
        state = get_workflow().run(payload)
    except Exception:
        log.exception("Workflow execution failed for %s", job_id)
        state = {"status": "failed", "error": "Processing failed"}
    finally:
        stop.set()
        thread.join(timeout=2)
    with SessionLocal() as db:
        job = db.get(WorkflowJob, job_id)
        if job.token != token or job.status == "cancelled":
            return True
        record = db.get(SubmissionRecord, job_id)
        if state.get("status") == "failed" and job.attempts < MAX_ATTEMPTS:
            job.status = "queued"
            job.lease_until = time.time() + 2 ** job.attempts
        else:
            job.status = "failed" if state.get("status") == "failed" else "completed"
            if record:
                SubmissionRepository(db).save_result(record, state)
        db.commit()
    return True

def main():
    logging.basicConfig(level=logging.INFO)
    from app.db.session import init_db
    init_db()
    while True:
        try:
            if not process_one():
                time.sleep(2)
        except Exception:
            log.exception("Queue polling failed")
            time.sleep(5)

if __name__ == "__main__":
    main()
