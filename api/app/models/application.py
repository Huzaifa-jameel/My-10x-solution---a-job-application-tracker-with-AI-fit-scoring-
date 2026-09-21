"""The applications table and the state machine that governs it.

One application per job. The allowed-transition map is the point of this
module: an application can move forward, and it can be abandoned, but it
cannot travel back in time. "rejected -> saved" is not a typo to be tolerated,
it is a 409.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

APPLICATION_STATES = ("saved", "applied", "interviewing", "offer", "rejected", "ghosted")

# Read as: from this state, you may move to any of these.
#
#   saved         you have not applied yet, so you can still drop it
#   applied       waiting to hear back - this is where ghosting happens
#   interviewing  in process; can still end in an offer or a rejection
#   offer         terminal in the happy direction, though it can still be
#                 rejected afterwards
#   rejected      terminal
#   ghosted       terminal, but a company that resurfaces can be un-ghosted,
#                 which is the one backwards edge that happens in real life
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "saved": frozenset({"applied", "rejected", "ghosted"}),
    "applied": frozenset({"interviewing", "rejected", "ghosted", "offer"}),
    "interviewing": frozenset({"offer", "rejected", "ghosted"}),
    "offer": frozenset({"rejected"}),
    "rejected": frozenset(),
    "ghosted": frozenset({"applied", "interviewing"}),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # One application per job: tracking the same posting twice is a bug, not a
    # feature. Deleting the job removes its application with it.
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    state: Mapped[str] = mapped_column(String(16), nullable=False, default="saved", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set the first time the state becomes "applied", and never moved again.
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bumped on every change. This is what "stale application" is measured
    # from in the weekly digest.
    last_touch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "state IN (" + ", ".join(f"'{s}'" for s in APPLICATION_STATES) + ")",
            name="ck_applications_state",
        ),
    )

    def __repr__(self) -> str:
        return f"<Application {self.id} job={self.job_id} state={self.state}>"
