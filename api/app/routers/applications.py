"""Application tracking: create one for a job, then move it through states."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Job
from app.models.application import ALLOWED_TRANSITIONS, Application, can_transition
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate

router = APIRouter(tags=["applications"])


def _owned_application(db: Session, application_id: uuid.UUID, user: User) -> Application:
    """Fetch an application, or 404.

    The ownership check reaches through the job, because an application has no
    user of its own. Someone else's application answers 404, never 403.
    """
    application = db.execute(
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id, Job.user_id == user.id)
    ).scalar_one_or_none()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found."
        )
    return application


@router.post(
    "/jobs/{job_id}/application",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    job_id: uuid.UUID,
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Start tracking an application for a job."""
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    existing = db.execute(
        select(Application).where(Application.job_id == job_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This job is already tracked as application {existing.id}.",
        )

    now = datetime.now(UTC)
    application = Application(
        job_id=job_id,
        state=payload.state,
        notes=payload.notes,
        last_touch_at=now,
        applied_at=now if payload.state == "applied" else None,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return ApplicationRead.model_validate(application)


@router.get("/applications/{application_id}", response_model=ApplicationRead)
def read_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    return ApplicationRead.model_validate(_owned_application(db, application_id, current_user))


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationRead:
    """Move an application to a new state, or edit its notes.

    An illegal move is a 409 with the legal moves listed, not a silent no-op:
    the client asked for something the state machine forbids, and saying which
    moves are allowed is more useful than saying no.
    """
    application = _owned_application(db, application_id, current_user)
    changed = False

    if payload.state is not None and payload.state != application.state:
        if not can_transition(application.state, payload.state):
            allowed = sorted(ALLOWED_TRANSITIONS.get(application.state, frozenset()))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot move from {application.state} to {payload.state}. "
                    + (f"Allowed from here: {', '.join(allowed)}." if allowed else
                       f"{application.state} is a terminal state.")
                ),
            )
        application.state = payload.state
        # Stamped once, the first time it is actually applied for. Re-entering
        # "applied" after being ghosted must not rewrite the original date.
        if payload.state == "applied" and application.applied_at is None:
            application.applied_at = datetime.now(UTC)
        changed = True

    if payload.notes is not None:
        application.notes = payload.notes
        changed = True

    if changed:
        application.last_touch_at = datetime.now(UTC)
        db.commit()
        db.refresh(application)

    return ApplicationRead.model_validate(application)
