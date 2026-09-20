from app.importers.set_list_parser import parse_set_list, tokenize_set_list


def test_tokenize_splits_commas_and_whitespace() -> None:
    assert tokenize_set_list("6024-1, 10281-1\n21309-1") == [
        "6024-1",
        "10281-1",
        "21309-1",
    ]


def test_parse_valid_tokens() -> None:
    valid, errors = parse_set_list("6024-1,10281-1")
    assert valid == ["6024-1", "10281-1"]
    assert errors == []


def test_parse_reports_invalid_tokens() -> None:
    valid, errors = parse_set_list("6024-1,,bad!")
    assert valid == ["6024-1"]
    assert len(errors) == 2
    assert errors[0].message == "empty set number"
    assert errors[1].message == "invalid set number format"
