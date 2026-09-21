"""Redis-backed cache for extraction results.

Keyed on the posting AND the profile, not the posting alone. That matters:
half of what the model returns - fit_score, rationale, blockers - is a
judgement about one specific candidate. Caching on content_hash alone would
hand the second user the first user's score, and would keep serving a stale
score after someone edited their CV.

So the key is (content_hash, profile fingerprint). An identical re-ingest by
the same unchanged profile is a hit and costs no model call; anything else
misses and is scored properly.

Every key written here carries a TTL, and every key lives under the "cache:"
prefix so it never collides with the "rq:" keys the queue owns on the same
Redis instance.
"""

import hashlib
import json
import logging
import uuid

from app.config import settings
from app.llm.base import Extraction, ProfileSummary
from app.workers.queue import redis_connection

logger = logging.getLogger(__name__)

CACHE_PREFIX = "cache:"
EXTRACTION_PREFIX = f"{CACHE_PREFIX}extract:"
STATS_PREFIX = f"{CACHE_PREFIX}stats:"

# Hit and miss counters are statistics, not data, but the project rule is a
# TTL on every key. 90 days is long enough to be useful on the usage page.
STATS_TTL_SECONDS = 90 * 24 * 60 * 60


def profile_fingerprint(profile: ProfileSummary) -> str:
    """A stable short hash of everything about the profile that affects a score.

    Sorted, so re-ordering skills in the form does not invalidate the cache.
    The CV text is hashed rather than included, to keep the CV out of Redis.
    """
    material = json.dumps(
        {
            "skills": sorted(s.lower() for s in profile.skills),
            "years": profile.years_experience,
            "roles": sorted(r.lower() for r in profile.target_roles),
            "locations": sorted(loc.lower() for loc in profile.locations),
            "cv": hashlib.sha256(profile.cv_text.encode("utf-8")).hexdigest(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def extraction_key(content_hash: str, profile: ProfileSummary) -> str:
    return f"{EXTRACTION_PREFIX}{content_hash}:{profile_fingerprint(profile)}"


def get(content_hash: str, profile: ProfileSummary) -> Extraction | None:
    """Return a cached extraction, or None.

    A broken cache must never break scoring, so any Redis or decoding problem
    is logged and treated as a miss.
    """
    try:
        raw = redis_connection.get(extraction_key(content_hash, profile))
    except Exception as exc:
        logger.warning("cache read failed (%s), treating as miss", type(exc).__name__)
        return None

    if raw is None:
        return None

    try:
        return Extraction.model_validate_json(raw)
    except Exception:
        # A value written by an older schema. Drop it and re-score.
        logger.info("cached extraction no longer validates, ignoring it")
        return None


def store(content_hash: str, profile: ProfileSummary, extraction: Extraction) -> None:
    try:
        redis_connection.setex(
            extraction_key(content_hash, profile),
            settings.cache_ttl_seconds,
            extraction.model_dump_json(),
        )
    except Exception as exc:
        logger.warning("cache write failed (%s), continuing", type(exc).__name__)


def _bump(user_id: uuid.UUID, kind: str) -> None:
    key = f"{STATS_PREFIX}{user_id}:{kind}"
    try:
        pipe = redis_connection.pipeline()
        pipe.incr(key)
        pipe.expire(key, STATS_TTL_SECONDS)
        pipe.execute()
    except Exception:
        # Statistics are not worth failing a job over.
        pass


def record_hit(user_id: uuid.UUID) -> None:
    _bump(user_id, "hits")


def record_miss(user_id: uuid.UUID) -> None:
    _bump(user_id, "misses")


def stats(user_id: uuid.UUID) -> tuple[int, int]:
    """(hits, misses) for one user."""
    try:
        values = redis_connection.mget(
            f"{STATS_PREFIX}{user_id}:hits", f"{STATS_PREFIX}{user_id}:misses"
        )
    except Exception:
        return 0, 0
    return int(values[0] or 0), int(values[1] or 0)
