"""Engine / session factory and the FastAPI session dependency."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(url: str, *, echo: bool = False) -> Engine:
    engine = create_engine(url, echo=echo, pool_pre_ping=True, future=True)

    @event.listens_for(engine, "connect")
    def _set_session_defaults(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        # All timestamps are stored as timestamptz and rendered in UTC.
        with dbapi_conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")
        dbapi_conn.commit()

    return engine


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return build_engine(settings.database_url, echo=settings.sql_echo)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    """One session per request. Services commit explicitly; anything uncommitted rolls back."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
