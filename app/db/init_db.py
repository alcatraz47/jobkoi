"""Database schema initialization helpers."""

from __future__ import annotations

from app.db.base import Base
from app.db.session import get_engine

# Import models for SQLAlchemy metadata registration side-effects.
from app.db import models as _models  # noqa: F401


def init_database() -> None:
    """Create all configured SQLAlchemy tables if they do not exist.

    Returns:
        None.
    """

    Base.metadata.create_all(bind=get_engine())


if __name__ == "__main__":
    init_database()
