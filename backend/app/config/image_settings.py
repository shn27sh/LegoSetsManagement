"""Image upload limits and allowed MIME types (SQLite BLOB storage)."""

from __future__ import annotations

import os

DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024

ALLOWED_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
}


def get_max_image_bytes() -> int:
    return int(os.environ.get("IMAGE_MAX_BYTES", DEFAULT_MAX_IMAGE_BYTES))


def normalize_content_type(content_type: str) -> str | None:
    base = content_type.split(";")[0].strip().lower()
    return ALLOWED_IMAGE_CONTENT_TYPES.get(base)
