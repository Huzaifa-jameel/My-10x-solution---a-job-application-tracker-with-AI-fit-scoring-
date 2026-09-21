"""SQLAlchemy models.

Every model must be imported here so that Base.metadata is complete when
Alembic autogenerates a migration.
"""

from app.models.base import Base
from app.models.job import JOB_STATUSES, REMOTE_MODES, SENIORITIES, Job
from app.models.user import User

__all__ = ["Base", "Job", "User", "JOB_STATUSES", "SENIORITIES", "REMOTE_MODES"]
