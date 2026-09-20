"""Parse LEGO age values from Rebrickable or user input."""

from __future__ import annotations

import re
from typing import Any

_AGE_DIGITS = re.compile(r"(\d+)")


def parse_age_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    match = _AGE_DIGITS.search(text)
    if match is None:
        return None
    return int(match.group(1))
