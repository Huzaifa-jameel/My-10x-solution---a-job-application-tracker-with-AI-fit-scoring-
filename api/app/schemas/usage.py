"""The shape of GET /usage: what the model work has cost so far."""

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """Totals across every model call this user has caused.

    Makes two otherwise invisible concepts legible: the cost log (concept 7)
    and, once caching lands, the cache hit rate (concept 6).
    """

    total_calls: int
    successful_calls: int
    failed_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    est_cost_usd: float
    avg_latency_ms: int
    jobs_scored: int
    calls_per_scored_job: float

    # Concept 6, made countable. A hit means a posting was scored without any
    # model call at all.
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float


class UsageCall(BaseModel):
    """One row of the cost log, newest first."""

    created_at: str
    provider: str
    model: str
    success: bool
    error_kind: str | None
    prompt_tokens: int
    completion_tokens: int
    est_cost_usd: float
    latency_ms: int
    attempt: int


class UsageResponse(BaseModel):
    summary: UsageSummary
    recent_calls: list[UsageCall]
