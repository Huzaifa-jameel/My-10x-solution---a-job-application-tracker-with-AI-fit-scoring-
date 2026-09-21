"""Database engine and the session dependency routes use."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# The app talks to Supabase through the transaction pooler on port 6543.
#
# Prepared statements are off: pgbouncer in transaction mode can hand a
# different backend to every statement, so a statement prepared on one is not
# there on the next.
#
# Connections are pooled on our side as well, despite pgbouncer being a pool
# itself. Measured against this Supabase region, opening a connection costs
# ~700ms (TCP, TLS and auth) while reusing one costs ~76ms. Without a pool
# every single request pays that 700ms, which the frontend's 2-second polling
# would pay over and over. pgbouncer multiplexes our handful of client
# connections onto its own smaller set of server connections, so this is
# cheap for it.
#
# pool_pre_ping matters more here than in most projects: Supabase pauses free
# projects when idle, and a pooled connection can be dead by the time it is
# handed out.
engine = create_engine(
    settings.sqlalchemy_url,
    connect_args={"prepare_threshold": None},
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def dispose_inherited_connections() -> None:
    """Drop connections inherited from a parent process after a fork.

    RQ forks a child process per job, and the child inherits the parent's open
    sockets. Two processes taking turns on one socket corrupts the connection.
    close=False is deliberate: it abandons the inherited connections without
    closing them, because they still belong to the parent.
    """
    engine.dispose(close=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
