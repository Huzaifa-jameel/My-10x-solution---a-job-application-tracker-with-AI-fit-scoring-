"""The RQ queue the API enqueues onto and the worker consumes from.

Redis serves two jobs in this project - queue and cache - on one instance,
separated by key prefix. RQ owns the "rq:" keys; the cache owns "cache:".
"""

import redis
from rq import Queue

from app.config import settings

QUEUE_NAME = "jobfit"

# decode_responses stays False: RQ stores pickled payloads and must get bytes.
redis_connection = redis.Redis.from_url(settings.redis_url)

queue = Queue(
    QUEUE_NAME,
    connection=redis_connection,
    # A scoring job that has not finished in five minutes is stuck, not slow.
    default_timeout=300,
)
