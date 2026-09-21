"""Request and response shapes for application tracking."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ApplicationState = Literal["saved", "applied", "interviewing", "offer", "rejected", "ghosted"]

MAX_NOTES_CHARS = 4000


class ApplicationCreate(BaseModel):
    state: ApplicationState = "saved"
    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)


class ApplicationUpdate(BaseModel):
    """Both fields optional: this is a PATCH, not a replacement."""

    state: ApplicationState | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    state: str
    notes: str | None
    applied_at: datetime | None
    last_touch_at: datetime
    created_at: datetime
