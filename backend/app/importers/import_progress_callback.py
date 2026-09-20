"""Cooperative cancel checks for long import loops."""

from __future__ import annotations

import threading

from app.importers.import_job_exceptions import ImportJobCancelled


def check_import_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ImportJobCancelled()
