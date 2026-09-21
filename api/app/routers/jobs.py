"""Job ingest, listing, read-back, rescore and delete.

Thin by design: validate, authorise, store, return. Nothing here talks to the
network or to a model - that work belongs to the worker.

Every query is filtered by owner in this file, explicitly, rather than relying
on Postgres row-level security. An ownership check you can read in the route
is an ownership check a reviewer can verify.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.ingest.text import clean_text, content_hash
from app.models import JOB_STATUSES, Job
from app.models.user import User
from app.schemas.job import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, JobCreate, JobPage, JobRead
from app.workers.queue import queue
from app.workers.tasks import score_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

SortField = Literal["score", "created", "company"]


def _owned_job(db: Session, job_id: uuid.UUID, user: User) -> Job:
    """Fetch a job or raise 404.

    A job owned by somebody else answers 404, not 403. A 403 would confirm the
    id exists, which is exactly the thing a stranger should not learn.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def ingest_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Accept a pasted posting for scoring.

    Returns 202, not 201: the row exists, but the interesting part has not
    happened yet. The client polls GET /jobs/{id} until status leaves
    "pending". Nothing on this path touches the network or a model.
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

    # Enqueued only after the commit succeeds: a worker that picked the job up
    # first would look for a row that is not there yet.
    queue.enqueue(score_job, str(job.id))

    return JobRead.model_validate(job)


@router.get("", response_model=JobPage)
def list_jobs(
    min_score: int | None = Query(default=None, ge=0, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    company: str | None = Query(default=None, max_length=120),
    sort: SortField = Query(default="score"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobPage:
    """List this user's jobs, filtered and paginated.

    There is no way to ask for everything: limit is capped, so the endpoint
    cannot be made to return an unbounded list.
    """
    if status_filter is not None and status_filter not in JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {', '.join(JOB_STATUSES)}",
        )

    filters = [Job.user_id == current_user.id]
    if min_score is not None:
        filters.append(Job.fit_score >= min_score)
    if status_filter is not None:
        filters.append(Job.status == status_filter)
    if company:
        filters.append(Job.company.ilike(f"%{company}%"))

    total = db.execute(select(func.count(Job.id)).where(*filters)).scalar_one()

    # nulls_last matters: unscored jobs have no score, and burying them under
    # a wall of NULLs at the top of the dashboard would be useless.
    order = {
        "score": Job.fit_score.desc().nulls_last(),
        "created": Job.created_at.desc(),
        "company": Job.company.asc().nulls_last(),
    }[sort]

    rows = (
        db.execute(
            select(Job).where(*filters).order_by(order, Job.created_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )

    return JobPage(
        items=[JobRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobRead)
def read_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    return JobRead.model_validate(_owned_job(db, job_id, current_user))


@router.post("/{job_id}/rescore", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def rescore_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Score this posting again, ignoring the cache.

    Bypassing the cache is the whole point: a rescore exists to get a fresh
    answer, usually after editing the profile or after an extraction failed.
    Serving it from the cache would make the button do nothing.
    """
    job = _owned_job(db, job_id, current_user)

    job.status = "pending"
    job.scored_at = None
    db.commit()
    db.refresh(job)

    queue.enqueue(score_job, str(job.id), use_cache=False)
    return JobRead.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    job = _owned_job(db, job_id, current_user)
    db.delete(job)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
