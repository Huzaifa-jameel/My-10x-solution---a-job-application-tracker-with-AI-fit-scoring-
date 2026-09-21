"""The profiles table: what the user is measured against.

Exactly one profile per user - the whole point is "score this posting against
me", and there is only one "me". The unique constraint on user_id is what
makes PUT /profile an upsert rather than a way to accumulate duplicates.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    cv_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    years_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    locations: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "years_experience >= 0 AND years_experience <= 70",
            name="ck_profiles_years_experience",
        ),
    )

    def __repr__(self) -> str:
        # Never includes cv_text: repr() ends up in logs, and a CV is personal.
        return f"<Profile user={self.user_id} skills={len(self.skills or [])}>"
