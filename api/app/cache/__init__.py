"""Redis-backed caching (concept 6). All keys live under the "cache:" prefix."""

from app.cache.extraction import (
    CACHE_PREFIX,
    get,
    record_hit,
    record_miss,
    stats,
    store,
)

__all__ = ["CACHE_PREFIX", "get", "store", "record_hit", "record_miss", "stats"]
