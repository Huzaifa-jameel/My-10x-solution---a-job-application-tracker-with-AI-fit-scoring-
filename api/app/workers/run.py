"""Worker entrypoint: python -m app.workers.run

A tiny wrapper around `rq worker` so that the Redis URL comes from app.config
like every other setting, instead of being repeated in docker-compose.yml.
"""

import logging

from rq import Queue, Worker

from app.workers.queue import QUEUE_NAME, redis_connection


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    queue = Queue(QUEUE_NAME, connection=redis_connection)
    Worker([queue], connection=redis_connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()
