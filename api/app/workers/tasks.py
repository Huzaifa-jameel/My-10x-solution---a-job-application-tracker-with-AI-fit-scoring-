"""Work that happens off the request path.

Everything here runs in the worker process, which means a fresh database
session per task - the request-scoped session from app.db.get_db does not
exist out here.
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from app.db import SessionLocal, dispose_inherited_connections
from app.models import Job

logger = logging.getLogger(__name__)


def score_job(job_id: str) -> None:
    """Score one ingested posting.

    Placeholder implementation: it moves the row through the same states the
    real pipeline will use, so the async round-trip can be proven end to end
    before a model is involved. C9 replaces the sleep with Groq extraction.
    """
    # RQ runs this in a forked child, which inherited the parent's pool.
    dispose_inherited_connections()

    job_uuid = uuid.UUID(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_uuid)
        if job is None:
            # Ingested then deleted before the worker got to it. Not an error.
            logger.warning("job_id=%s not found, nothing to score", job_id)
            return

        logger.info("job_id=%s user_id=%s scoring started", job_id, job.user_id)
        job.status = "scoring"
        db.commit()

        # Stands in for the model call, so the pending -> scored transition is
        # actually observable in the UI rather than finishing instantly.
        time.sleep(3)

        job.status = "scored"
        job.scored_at = datetime.now(UTC)
        db.commit()
        logger.info("job_id=%s scoring finished status=%s", job_id, job.status)
