"""Request and response shapes for registration and login."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.security import BCRYPT_MAX_PASSWORD_BYTES

MIN_PASSWORD_CHARS = 8


class UserCredentials(BaseModel):
    """Registration and login take the same two fields."""

    email: EmailStr
    password: str = Field(..., min_length=MIN_PASSWORD_CHARS)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        """Reject passwords bcrypt would silently truncate.

        min_length/max_length count characters, but bcrypt's limit is 72
        *bytes*, so a shorter string of multi-byte characters can still exceed
        it. Rejecting is better than accepting a password whose tail is
        ignored.
        """
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
            )
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
