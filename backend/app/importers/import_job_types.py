"""Shared types for import job progress reporting."""

from __future__ import annotations

from collections.abc import Callable

ProgressCallback = Callable[[int, int, str], None]
