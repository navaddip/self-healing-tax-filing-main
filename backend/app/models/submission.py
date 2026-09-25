from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, Integer, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SubmissionRecord(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Human-friendly 1..n number; the UUID stays the unguessable key used in URLs.
    serial_no: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    upload_path: Mapped[str] = mapped_column(Text)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Taxpayer-entered details (DOB, address, bank...) merged into each run
    filing_details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    token: Mapped[str | None] = mapped_column(String(36), nullable=True)
