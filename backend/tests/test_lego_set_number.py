"""Tests for LEGO set number parsing and Rebrickable formatting."""

import pytest

from app.domain.lego_set_number import (
    LegoSetId,
    LegoSetNumberParseError,
    display_set_number,
    from_rebrickable_set_num,
    parse_user_set_number,
    to_rebrickable_set_num,
)


def test_parse_plain_digits_defaults_variant() -> None:
    assert parse_user_set_number("65001") == LegoSetId(65001, 1)


def test_parse_with_variant() -> None:
    assert parse_user_set_number("65001-2") == LegoSetId(65001, 2)


def test_parse_rejects_invalid() -> None:
    with pytest.raises(LegoSetNumberParseError):
        parse_user_set_number("")
    with pytest.raises(LegoSetNumberParseError):
        parse_user_set_number("abc")
    with pytest.raises(LegoSetNumberParseError):
        parse_user_set_number("65a-1")


def test_rebrickable_round_trip() -> None:
    ls = parse_user_set_number("6024")
    assert to_rebrickable_set_num(ls) == "6024-1"


def test_from_rebrickable() -> None:
    assert from_rebrickable_set_num("6024-1") == LegoSetId(6024, 1)


def test_display_omits_variant() -> None:
    assert display_set_number(LegoSetId(21309, 1)) == 21309
