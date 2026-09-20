"""Local append-only failure log for import and sync troubleshooting."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)
_write_lock = Lock()


def failure_log_path() -> Path:
    return Path(os.environ.get("IMPORT_FAILURE_LOG_PATH", "./data/import_failures.log"))


def record_import_failure(
    *,
    operation: str,
    message: str,
    set_num: int | str | None = None,
    rb_key: str | None = None,
    token_index: int | None = None,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist a troubleshooting record without interrupting the import flow."""
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "message": message,
    }
    if set_num is not None:
        payload["set_num"] = set_num
    if rb_key is not None:
        payload["rb_key"] = rb_key
    if token_index is not None:
        payload["token_index"] = token_index
    if error_type is not None:
        payload["error_type"] = error_type
    if extra:
        payload["extra"] = extra

    path = failure_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        with _write_lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
    except OSError:
        logger.exception("Failed to write import failure log path=%s", path)
