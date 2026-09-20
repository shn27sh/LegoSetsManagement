"""Parse comma-separated LEGO set number tokens for collection import."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.lego_set_number import LegoSetNumberParseError, parse_user_set_number


@dataclass(frozen=True)
class ParseError:
    token_index: int
    raw: str
    message: str


def tokenize_set_list(content: str) -> list[str]:
    """Split file content into set-number tokens (commas and whitespace)."""
    stripped = content.strip()
    if not stripped:
        return []
    tokens: list[str] = []
    for segment in stripped.split(","):
        parts = [part for part in re.split(r"\s+", segment) if part]
        if parts:
            tokens.extend(parts)
        else:
            tokens.append("")
    return tokens


def validate_set_num(token: str) -> str | None:
    trimmed = token.strip()
    if not trimmed:
        return "empty set number"
    try:
        parse_user_set_number(trimmed)
    except LegoSetNumberParseError:
        return "invalid set number format"
    return None


def parse_set_list_entries(content: str) -> tuple[list[tuple[int, str]], list[ParseError]]:
    tokens = tokenize_set_list(content)
    valid: list[tuple[int, str]] = []
    errors: list[ParseError] = []
    for index, raw in enumerate(tokens):
        msg = validate_set_num(raw)
        if msg:
            errors.append(ParseError(token_index=index, raw=raw, message=msg))
        else:
            valid.append((index, raw.strip()))
    return valid, errors


def parse_set_list(content: str) -> tuple[list[str], list[ParseError]]:
    valid_entries, errors = parse_set_list_entries(content)
    return [set_num for _, set_num in valid_entries], errors
