"""GET /usage - the cost log, summarised.

Caching and cost logging are otherwise invisible. This endpoint, and the page
built on it, are what make them checkable in ten seconds.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Job
from app.models.llm_call import LLMCall
from app.models.user import User
from app.schemas.usage import UsageCall, UsageResponse, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])

RECENT_CALLS_LIMIT = 50


@router.get("", response_model=UsageResponse)
def read_usage(
    limit: int = Query(default=20, ge=1, le=RECENT_CALLS_LIMIT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageResponse:
    mine = LLMCall.user_id == current_user.id

    totals = db.execute(
        select(
            func.count(LLMCall.id),
            func.count(LLMCall.id).filter(LLMCall.success.is_(True)),
            func.coalesce(func.sum(LLMCall.prompt_tokens), 0),
            func.coalesce(func.sum(LLMCall.completion_tokens), 0),
            func.coalesce(func.sum(LLMCall.est_cost_usd), 0),
            func.coalesce(func.avg(LLMCall.latency_ms), 0),
        ).where(mine)
    ).one()

    total_calls, successful, prompt_tokens, completion_tokens, cost, avg_latency = totals

    jobs_scored = db.execute(
        select(func.count(Job.id)).where(Job.user_id == current_user.id, Job.status == "scored")
    ).scalar_one()

    summary = UsageSummary(
        total_calls=total_calls,
        successful_calls=successful,
        failed_calls=total_calls - successful,
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        total_tokens=int(prompt_tokens) + int(completion_tokens),
        est_cost_usd=float(cost),
        avg_latency_ms=int(avg_latency),
        jobs_scored=jobs_scored,
        # Above 1.0 means repair retries are firing; well below 1.0 means the
        # cache is doing its job.
        calls_per_scored_job=round(total_calls / jobs_scored, 2) if jobs_scored else 0.0,
    )

    rows = (
        db.execute(
            select(LLMCall).where(mine).order_by(LLMCall.created_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )

    return UsageResponse(
        summary=summary,
        recent_calls=[
            UsageCall(
                created_at=row.created_at.isoformat(),
                provider=row.provider,
                model=row.model,
                success=row.success,
                error_kind=row.error_kind,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                est_cost_usd=float(row.est_cost_usd),
                latency_ms=row.latency_ms,
                attempt=row.attempt,
            )
            for row in rows
        ],
    )
