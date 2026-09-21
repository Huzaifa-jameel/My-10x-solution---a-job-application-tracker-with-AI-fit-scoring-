"""SQLAlchemy models.

Every model must be imported here so that Base.metadata is complete when
Alembic autogenerates a migration.
"""

from app.models.application import APPLICATION_STATES, Application
from app.models.base import Base
from app.models.job import JOB_STATUSES, REMOTE_MODES, SCORED_BY, SENIORITIES, Job
from app.models.llm_call import LLMCall
from app.models.profile import Profile
from app.models.user import User

__all__ = [
    "Application",
    "APPLICATION_STATES",
    "Base",
    "Job",
    "LLMCall",
    "Profile",
    "User",
    "JOB_STATUSES",
    "SENIORITIES",
    "REMOTE_MODES",
    "SCORED_BY",
]
