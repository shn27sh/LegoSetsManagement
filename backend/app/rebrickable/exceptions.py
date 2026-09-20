"""Rebrickable client errors."""

from __future__ import annotations


class RebrickableConfigError(RuntimeError):
    """Missing or invalid configuration (e.g. API key)."""


class RebrickableAPIError(RuntimeError):
    """HTTP or API-level failure from Rebrickable."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
