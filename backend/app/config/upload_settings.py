"""Deprecated: use app.config.image_settings for BLOB image limits."""

from app.config.image_settings import (
    ALLOWED_IMAGE_CONTENT_TYPES,
    DEFAULT_MAX_IMAGE_BYTES,
    get_max_image_bytes,
)

# Backward-compatible alias for older imports.
get_max_missing_image_bytes = get_max_image_bytes
DEFAULT_UPLOAD_ROOT = "./data/uploads"
