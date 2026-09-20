import pytest

from app.rebrickable.config import load_rebrickable_settings
from app.rebrickable.exceptions import RebrickableConfigError


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REBRICKABLE_API_KEY", raising=False)
    with pytest.raises(RebrickableConfigError, match="REBRICKABLE_API_KEY"):
        load_rebrickable_settings()


def test_load_settings_reads_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    settings = load_rebrickable_settings()
    assert settings.api_key == "test-key"
    assert settings.base_url.endswith("/")
