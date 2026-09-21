"""Job ingest and read-back.

Thin by design: validate, authorise, store, return. Nothing here talks to the
network or to a model - that work belongs to the worker.

Every query is filtered by owner in this file, explicitly, rather than relying
on Postgres row-level security. An ownership check you can read in the route
is an ownership check a reviewer can verify.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.ingest.text import clean_text, content_hash
from app.models import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def ingest_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Store a pasted posting and hand back the row.

    The row lands as "pending". Once the worker exists (C8) this becomes a
    202 and the scoring happens off the request path.
    """
    cleaned = clean_text(payload.text)
    digest = content_hash(cleaned)

    existing = db.execute(
        select(Job).where(Job.user_id == current_user.id, Job.content_hash == digest)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This posting has already been ingested as job {existing.id}.",
        )

    job = Job(
        user_id=current_user.id,
        raw_text=cleaned,
        content_hash=digest,
        status="pending",
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        # Two simultaneous ingests of the same posting: the check above lost the
        # race, and uq_jobs_user_content caught it. The constraint is the real
        # guard; the SELECT just produces a nicer message in the common case.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This posting has already been ingested.",
        ) from None
    db.refresh(job)
    return JobRead.model_validate(job)


@router.get("/{job_id}", response_model=JobRead)
def read_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Read one job.

    A job owned by somebody else answers 404, not 403. A 403 would confirm the
    id exists, which is exactly the thing a stranger should not learn.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobRead.model_validate(job)
