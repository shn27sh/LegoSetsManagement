"""SQLite connection pragmas for local-first concurrency during long imports."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine


def configure_sqlite_engine(engine: Engine) -> None:
    """Enable WAL and a busy timeout on SQLite engines."""
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
