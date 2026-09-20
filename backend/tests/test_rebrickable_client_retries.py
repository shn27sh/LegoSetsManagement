import httpx
import pytest

from app.rebrickable.client import RebrickableClient
from app.rebrickable.config import RebrickableSettings
from app.rebrickable.exceptions import RebrickableAPIError
from tests.rebrickable_helpers import load_fixture

BASE = "https://rebrickable.com/api/v3/"


def test_retries_on_429_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, json={"detail": "throttled"})
        return httpx.Response(200, json=load_fixture("set_6024.json"))

    settings = RebrickableSettings(
        api_key="test-key",
        base_url=BASE,
        timeout_seconds=5.0,
        max_retries=2,
        min_request_interval_seconds=0.0,
    )
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE)

    with RebrickableClient(settings, http_client=http) as client:
        dto = client.get_set("6024-1")

    assert dto.set_num == "6024-1"
    assert attempts["count"] == 2


def test_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rebrickable.client.time.sleep", lambda _: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    settings = RebrickableSettings(
        api_key="test-key",
        base_url=BASE,
        timeout_seconds=5.0,
        max_retries=1,
        min_request_interval_seconds=0.0,
    )
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE)

    with RebrickableClient(settings, http_client=http) as client:
        with pytest.raises(RebrickableAPIError) as exc_info:
            client.get_set("6024-1")

    assert exc_info.value.status_code == 503
