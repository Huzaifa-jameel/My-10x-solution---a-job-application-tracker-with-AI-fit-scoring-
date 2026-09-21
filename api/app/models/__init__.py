"""SQLAlchemy models.

Every model must be imported here so that Base.metadata is complete when
Alembic autogenerates a migration.
"""

from app.models.base import Base
from app.models.job import JOB_STATUSES, REMOTE_MODES, SENIORITIES, Job

__all__ = ["Base", "Job", "JOB_STATUSES", "SENIORITIES", "REMOTE_MODES"]
