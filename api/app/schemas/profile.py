"""Request and response shapes for the CV profile."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_CV_CHARS = 40_000
MAX_LIST_ITEMS = 50


class ProfileUpsert(BaseModel):
    """The whole profile, replaced in one call.

    A PUT replaces rather than patches: the profile is small, the frontend
    edits it as one form, and a partial update would raise the question of how
    to clear a list.
    """

    cv_text: str = Field(default="", max_length=MAX_CV_CHARS)
    skills: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    years_experience: int = Field(default=0, ge=0, le=70)
    target_roles: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    locations: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cv_text: str
    skills: list[str]
    years_experience: int
    target_roles: list[str]
    locations: list[str]
    updated_at: datetime
