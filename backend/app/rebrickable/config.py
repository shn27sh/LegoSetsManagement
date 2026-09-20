"""Rebrickable client configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.rebrickable.exceptions import RebrickableConfigError

DEFAULT_BASE_URL = "https://rebrickable.com/api/v3/"
ENV_API_KEY = "REBRICKABLE_API_KEY"
ENV_BASE_URL = "REBRICKABLE_BASE_URL"


@dataclass(frozen=True)
class RebrickableSettings:
    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int
    min_request_interval_seconds: float


def load_rebrickable_settings() -> RebrickableSettings:
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        raise RebrickableConfigError(
            f"{ENV_API_KEY} is not set; add it to backend/.env (see .env.example)"
        )

    base_url = os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL).strip()
    if not base_url.endswith("/"):
        base_url = f"{base_url}/"

    timeout = float(os.environ.get("REBRICKABLE_TIMEOUT_SECONDS", "30"))
    max_retries = int(os.environ.get("REBRICKABLE_MAX_RETRIES", "3"))
    min_interval = float(
        os.environ.get("REBRICKABLE_MIN_REQUEST_INTERVAL_SECONDS", "1.0")
    )

    return RebrickableSettings(
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout,
        max_retries=max_retries,
        min_request_interval_seconds=max(0.0, min_interval),
    )
