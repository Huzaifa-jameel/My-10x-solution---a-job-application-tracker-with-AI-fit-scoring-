"""Database engine and the session dependency routes use."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

# The app talks to Supabase through the transaction pooler on port 6543, which
# has two consequences worth spelling out:
#
#   - pgbouncer in transaction mode can hand a different backend to every
#     statement, so psycopg must not keep server-side prepared statements
#     around. prepare_threshold=None turns them off.
#   - pgbouncer is already a connection pool. Pooling again inside SQLAlchemy
#     would just hold connections the pooler wants back, so NullPool.
#
# Alembic deliberately uses a different URL - see settings.alembic_url.
engine = create_engine(
    settings.sqlalchemy_url,
    poolclass=NullPool,
    connect_args={"prepare_threshold": None},
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
