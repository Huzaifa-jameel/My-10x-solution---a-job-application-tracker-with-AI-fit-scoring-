"""Job ingest and read-back.

Thin by design: validate, look for a duplicate, store, return. Nothing here
talks to the network or to a model - that work belongs to the worker.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingest.text import clean_text, content_hash
from app.models import Job
from app.schemas.job import JobCreate, JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def ingest_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobRead:
    """Store a pasted posting and hand back the row.

    The row lands as "pending". Once the worker exists (C8) this becomes a
    202 and the scoring happens off the request path.
    """
    cleaned = clean_text(payload.text)
    digest = content_hash(cleaned)

    existing = db.execute(select(Job).where(Job.content_hash == digest)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This posting has already been ingested as job {existing.id}.",
        )

    job = Job(raw_text=cleaned, content_hash=digest, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobRead.model_validate(job)


@router.get("/{job_id}", response_model=JobRead)
def read_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobRead:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobRead.model_validate(job)
