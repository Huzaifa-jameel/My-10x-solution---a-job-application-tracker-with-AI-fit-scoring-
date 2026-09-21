"""Work that happens off the request path.

Everything here runs in the worker process, which means a fresh database
session per task - the request-scoped session from app.db.get_db does not
exist out here.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, dispose_inherited_connections
from app.config import settings
from app.llm.base import LLMOutcome, ProfileSummary, estimate_cost_usd
from app.llm.groq_provider import GroqProvider
from app.models import Job
from app.models.llm_call import LLMCall
from app.models.profile import Profile

logger = logging.getLogger(__name__)


def _profile_summary(db: Session, user_id: uuid.UUID) -> ProfileSummary:
    """Flatten the user's profile for the prompt.

    A user with no profile still gets a score - the model just has nothing to
    match against, which the rationale will say.
    """
    profile = db.execute(select(Profile).where(Profile.user_id == user_id)).scalar_one_or_none()
    if profile is None:
        return ProfileSummary()
    return ProfileSummary(
        skills=list(profile.skills or []),
        years_experience=profile.years_experience,
        target_roles=list(profile.target_roles or []),
        locations=list(profile.locations or []),
        cv_text=profile.cv_text or "",
    )


def _log_call(db: Session, job: Job, outcome: LLMOutcome) -> None:
    """Write one cost-log row for one request.

    Called for every attempt, including failures. A failed call still costs
    latency and still counts against a rate limit, so leaving it out would
    make the log a record of successes rather than a record of spend.
    """
    db.add(
        LLMCall(
            user_id=job.user_id,
            job_id=job.id,
            provider=outcome.provider,
            model=outcome.model,
            prompt_tokens=outcome.prompt_tokens,
            completion_tokens=outcome.completion_tokens,
            max_input_tokens=settings.llm_max_input_tokens,
            est_cost_usd=estimate_cost_usd(outcome.prompt_tokens, outcome.completion_tokens),
            latency_ms=outcome.latency_ms,
            success=outcome.ok,
            error_kind=outcome.error_kind,
            attempt=outcome.attempts,
            raw_response=outcome.raw_response,
        )
    )


def _apply(job: Job, outcome: LLMOutcome) -> None:
    """Copy a validated extraction onto the row."""
    extraction = outcome.extraction
    assert extraction is not None  # guarded by outcome.ok at the call site

    job.title = extraction.title or None
    job.company = extraction.company or None
    job.seniority = extraction.seniority
    job.required_skills = extraction.required_skills
    job.min_years = extraction.min_years
    job.location = extraction.location or None
    job.remote = extraction.remote
    job.fit_score = extraction.fit_score
    job.rationale = extraction.rationale
    job.blockers = extraction.blockers
    job.status = "scored"
    job.scored_at = datetime.now(UTC)


def score_job(job_id: str) -> None:
    """Extract requirements from one posting and score it against the profile."""
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

        profile = _profile_summary(db, job.user_id)
        provider = GroqProvider()
        attempts = provider.extract_and_score(job.raw_text, profile)

        for attempt in attempts:
            _log_call(db, job, attempt)

        outcome = attempts[-1]
        if outcome.ok:
            _apply(job, outcome)
            logger.info(
                "job_id=%s scored score=%s model=%s tokens=%s+%s latency=%sms",
                job_id,
                job.fit_score,
                outcome.model,
                outcome.prompt_tokens,
                outcome.completion_tokens,
                outcome.latency_ms,
            )
        else:
            # A failed extraction is a state the row carries, not an exception
            # that kills the worker. The raw reply is on the cost-log row for
            # whoever has to work out why.
            job.status = "extraction_failed"
            logger.warning(
                "job_id=%s extraction failed kind=%s attempts=%s latency=%sms",
                job_id,
                outcome.error_kind,
                len(attempts),
                outcome.latency_ms,
            )

        db.commit()
