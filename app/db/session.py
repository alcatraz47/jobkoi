"""SQLAlchemy engine and session providers."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy engine.

    Returns:
        Configured SQLAlchemy engine.
    """

    settings: Settings = get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.sqlalchemy_echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache the SQLAlchemy session factory.

    Returns:
        Sessionmaker configured for synchronous sessions.
    """

    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, class_=Session)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session for request-scoped usage.

    Yields:
        Active SQLAlchemy session.
    """

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose the SQLAlchemy engine and clear provider caches."""

    engine = get_engine()
    engine.dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
