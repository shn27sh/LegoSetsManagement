"""Configuration for CDN image downloads during Rebrickable sync."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageDownloadSettings:
    timeout_seconds: float
    min_interval_seconds: float


def load_image_download_settings() -> ImageDownloadSettings:
    timeout = float(os.environ.get("IMAGE_DOWNLOAD_TIMEOUT_SECONDS", "20"))
    interval = float(os.environ.get("IMAGE_DOWNLOAD_MIN_INTERVAL_SECONDS", "0.3"))
    return ImageDownloadSettings(
        timeout_seconds=timeout,
        min_interval_seconds=max(0.0, interval),
    )
