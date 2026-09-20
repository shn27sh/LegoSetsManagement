"""FastAPI dependencies for database sessions."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_session_factory

_session_factory = None


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = get_session_factory()
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
