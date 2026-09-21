"""The user's CV profile: read it, replace it."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileRead, ProfileUpsert

router = APIRouter(prefix="/profile", tags=["profile"])


def _normalise(values: list[str]) -> list[str]:
    """Trim, drop blanks, and de-duplicate case-insensitively, keeping order.

    Skills arrive from a text box, so "Python", "python " and "Python" all turn
    up. Keeping the first spelling preserves what the user typed.
    """
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


@router.get("", response_model=ProfileRead)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileRead:
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile yet. PUT /profile to create one.",
        )
    return ProfileRead.model_validate(profile)


@router.put("", response_model=ProfileRead)
def upsert_profile(
    payload: ProfileUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileRead:
    """Create the profile, or replace it if it already exists."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    ).scalar_one_or_none()

    if profile is None:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    profile.cv_text = payload.cv_text
    profile.skills = _normalise(payload.skills)
    profile.years_experience = payload.years_experience
    profile.target_roles = _normalise(payload.target_roles)
    profile.locations = _normalise(payload.locations)

    db.commit()
    db.refresh(profile)
    return ProfileRead.model_validate(profile)
