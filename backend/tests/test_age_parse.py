from app.utils.age import parse_age_value


def test_parse_age_from_plus_suffix() -> None:
    assert parse_age_value("6+") == 6
    assert parse_age_value("16+") == 16


def test_parse_age_integer() -> None:
    assert parse_age_value(8) == 8
