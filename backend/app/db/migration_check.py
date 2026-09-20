"""Verify the database schema matches Alembic head before serving traffic."""

from __future__ import annotations

import os

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.db.session import get_database_url
from app.runtime_paths import make_alembic_config


class DatabaseMigrationError(RuntimeError):
    """Raised when the database is missing or not at Alembic head."""


def get_alembic_head_revision() -> str:
    script = ScriptDirectory.from_config(make_alembic_config())
    head = script.get_current_head()
    if head is None:
        raise DatabaseMigrationError("No Alembic head revision found")
    return head


def get_database_revision(database_url: str) -> str | None:
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {},
    )
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    finally:
        engine.dispose()


def ensure_database_at_head(database_url: str | None = None) -> None:
    """Fail fast when the database is not migrated to head."""
    if os.environ.get("SKIP_DB_MIGRATION_CHECK", "").lower() in ("1", "true", "yes"):
        return

    url = database_url or get_database_url()
    head = get_alembic_head_revision()
    current = get_database_revision(url)

    if current is None:
        raise DatabaseMigrationError(
            "Database has no Alembic revision (missing or empty). "
            "From backend/: alembic upgrade head"
        )
    if current != head:
        raise DatabaseMigrationError(
            f"Database revision {current!r} is not at head {head!r}. "
            "From backend/: alembic upgrade head"
        )
