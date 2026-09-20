"""LEGO catalog set identifier: numeric base + variant suffix for Rebrickable APIs.

Displayed to users without the `-variant` suffix. Stored in DB as integers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FULL = re.compile(r"^(\d+)(?:-(\d+))?$")


@dataclass(frozen=True)
class LegoSetId:
    """Rebrickable-style identity: `number` + `variant` (e.g. 65001 + 1 → `65001-1`)."""

    number: int
    variant: int = 1


class LegoSetNumberParseError(ValueError):
    """User-facing invalid set number input."""


def parse_user_set_number(raw: str) -> LegoSetId:
    """Parse CSV / form input such as `65001`, `65001-1`, `65001-02`.

    If the `-variant` part is omitted, variant defaults to **1** (Rebrickable convention).
    """
    s = raw.strip()
    if not s:
        raise LegoSetNumberParseError("empty set number")
    m = _FULL.match(s)
    if not m:
        raise LegoSetNumberParseError("invalid set number format")
    number = int(m.group(1))
    variant = int(m.group(2)) if m.group(2) is not None else 1
    if number < 1 or variant < 1:
        raise LegoSetNumberParseError("set number must be positive")
    if number > 999_999_999 or variant > 999:
        raise LegoSetNumberParseError("set number out of range")
    return LegoSetId(number=number, variant=variant)


def from_rebrickable_set_num(rb: str) -> LegoSetId:
    """Parse Rebrickable API `set_num` field (always includes `-variant`)."""
    s = rb.strip()
    m = _FULL.match(s)
    if not m or m.group(2) is None:
        # Rebrickable always returns forms like 6024-1; fallback for tests.
        m2 = re.match(r"^(\d+)-(\d+)$", s)
        if not m2:
            raise ValueError(f"unexpected Rebrickable set_num: {rb!r}")
        return LegoSetId(int(m2.group(1)), int(m2.group(2)))
    return LegoSetId(number=int(m.group(1)), variant=int(m.group(2)))


def to_rebrickable_set_num(ls: LegoSetId) -> str:
    """Format for HTTP calls to Rebrickable (`GET lego/sets/{set_num}/`)."""
    return f"{ls.number}-{ls.variant}"


def display_set_number(ls: LegoSetId) -> int:
    """Single integer shown in the UI (omit `-variant`)."""
    return ls.number


def migrate_legacy_set_num_text(legacy: str) -> LegoSetId:
    """Convert existing DB `catalog_sets.set_num` TEXT during migration."""
    s = legacy.strip()
    m = _FULL.match(s)
    if m:
        return parse_user_set_number(s)
    # Rare legacy text such as "stub-1" — preserve distinguishability in dev DB
    if m2 := re.match(r"^(\d+)-(\d+)$", s):
        return LegoSetId(int(m2.group(1)), int(m2.group(2)))
    raise ValueError(f"cannot migrate legacy set_num: {legacy!r}")
