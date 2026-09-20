"""Checkpoint commits during long import/sync operations."""

from __future__ import annotations

from sqlalchemy.orm import Session


def commit_import_progress(session: Session) -> None:
    """Persist work for one import unit so other DB connections can read progress."""
    session.commit()
