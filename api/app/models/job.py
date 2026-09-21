"""The jobs table: one ingested posting and whatever we have learned about it.

A row starts life as raw text with status "pending" and is filled in by the
worker. Every column the model extracts is nullable, because a row exists
before it has been scored - and may never be scored if extraction fails.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Kept as plain tuples rather than a Postgres ENUM type: altering a PG enum in a
# migration is painful, and a CHECK constraint is just as strict while staying
# readable in the schema.
JOB_STATUSES = (
    "pending",
    "fetching",
    "scoring",
    "scored",
    "extraction_failed",
    "fetch_failed",
)
SENIORITIES = ("junior", "mid", "senior", "lead", "unknown")
REMOTE_MODES = ("onsite", "hybrid", "remote", "unknown")


def _one_of(column: str, allowed: tuple[str, ...], *, nullable: bool) -> CheckConstraint:
    """A CHECK constraint restricting a column to a known set of strings."""
    values = ", ".join(f"'{v}'" for v in allowed)
    clause = f"{column} IN ({values})"
    if nullable:
        clause = f"{column} IS NULL OR {clause}"
    return CheckConstraint(clause, name=f"ck_jobs_{column}")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- what was ingested ---
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sha256 of the cleaned text: identifies a re-ingest of the same posting and
    # keys the extraction cache.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- what the model extracted ---
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    required_skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    min_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- what the model concluded ---
    fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    blockers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # --- lifecycle ---
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        _one_of("status", JOB_STATUSES, nullable=False),
        _one_of("seniority", SENIORITIES, nullable=True),
        _one_of("remote", REMOTE_MODES, nullable=True),
        CheckConstraint(
            "fit_score IS NULL OR (fit_score >= 0 AND fit_score <= 100)",
            name="ck_jobs_fit_score_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} status={self.status} score={self.fit_score}>"
