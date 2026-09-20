"""Write comma-separated failed Rebrickable set keys for retry CSV import."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)
_write_lock = Lock()
_active_keys: list[str] | None = None


def failed_sets_csv_path() -> Path:
    return Path(os.environ.get("FAILED_SETS_CSV_PATH", "./data/failedSets.csv"))


def begin_failed_sets_run() -> None:
    """Clear the retry file and start collecting catalog-level failures for this run."""
    global _active_keys
    path = failed_sets_csv_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            _active_keys = []
            path.write_text("", encoding="utf-8")
    except OSError:
        logger.exception("Failed to initialize failed sets CSV path=%s", path)
        with _write_lock:
            _active_keys = []


def record_failed_set(rb_key: str) -> None:
    """Record a Rebrickable catalog fetch failure (``6024-1`` style key)."""
    key = rb_key.strip()
    if not key:
        return
    with _write_lock:
        if _active_keys is not None:
            _active_keys.append(key)


def finalize_failed_sets_run() -> None:
    """Dedupe collected keys and rewrite the retry file (empty when no failures)."""
    global _active_keys
    with _write_lock:
        keys = list(_active_keys or [])
        _active_keys = None

    seen: set[str] = set()
    unique: list[str] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)

    path = failed_sets_csv_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(unique), encoding="utf-8")
    except OSError:
        logger.exception("Failed to write failed sets CSV path=%s", path)


@contextmanager
def failed_sets_import_run() -> Iterator[Callable[[str], None]]:
    """Scope for one CSV import or Rebrickable sync that may write ``failedSets.csv``."""
    begin_failed_sets_run()
    try:
        yield record_failed_set
    finally:
        finalize_failed_sets_run()
