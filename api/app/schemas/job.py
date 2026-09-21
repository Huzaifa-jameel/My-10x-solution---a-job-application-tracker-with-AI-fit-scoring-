"""Request and response shapes for job ingest and read-back.

Kept separate from the SQLAlchemy model on purpose: an ORM object is never
returned to a client directly.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# A posting shorter than this is almost certainly a mis-paste, and a 422 saying
# so is more useful than a row nobody can score.
MIN_POSTING_CHARS = 50
MAX_POSTING_CHARS = 60_000


class JobCreate(BaseModel):
    """Ingest a posting by pasted text."""

    text: str = Field(
        ...,
        min_length=MIN_POSTING_CHARS,
        max_length=MAX_POSTING_CHARS,
        description="The full text of the job posting, pasted.",
    )


class JobRead(BaseModel):
    """A job as the API reports it.

    Every extracted field is optional because a row exists from the moment it
    is ingested, long before anything has looked at it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url: str | None
    content_hash: str

    title: str | None
    company: str | None
    seniority: str | None
    required_skills: list[str] | None
    min_years: int | None
    location: str | None
    remote: str | None

    fit_score: int | None
    rationale: list[str] | None
    blockers: list[str] | None

    status: str
    created_at: datetime
    scored_at: datetime | None
