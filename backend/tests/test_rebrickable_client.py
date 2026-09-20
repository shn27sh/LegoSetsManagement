import httpx
import pytest

from app.rebrickable.client import RebrickableClient
from app.rebrickable.config import RebrickableSettings
from app.rebrickable.exceptions import RebrickableAPIError
from tests.rebrickable_helpers import load_fixture

BASE = "https://rebrickable.com/api/v3/"


def _settings() -> RebrickableSettings:
    return RebrickableSettings(
        api_key="test-key",
        base_url=BASE,
        timeout_seconds=5.0,
        max_retries=0,
        min_request_interval_seconds=0.0,
    )


def _mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/lego/sets/6024-1/"):
            return httpx.Response(200, json=load_fixture("set_6024.json"))
        if "/lego/sets/6024-1/parts/" in url:
            if "page=2" in url:
                return httpx.Response(200, json=load_fixture("parts_page2.json"))
            return httpx.Response(200, json=load_fixture("parts_page1.json"))
        if url.endswith("/lego/sets/6024-1/minifigs/"):
            return httpx.Response(200, json=load_fixture("minifigs.json"))
        if url.endswith("/lego/minifigs/cop01/parts/"):
            return httpx.Response(200, json=load_fixture("minifig_parts.json"))
        if url.endswith("/lego/themes/67/"):
            return httpx.Response(200, json=load_fixture("theme_67.json"))
        if url.endswith("/lego/colors/"):
            return httpx.Response(200, json=load_fixture("colors_page1.json"))
        if "/lego/sets/missing-1/" in url:
            return httpx.Response(404, json={"detail": "Not found"})
        return httpx.Response(404, json={"detail": f"unmocked {url}"})

    return httpx.MockTransport(handler)


def _client() -> RebrickableClient:
    http = httpx.Client(
        transport=_mock_transport(),
        base_url=BASE,
        headers={"Authorization": "key test-key"},
    )
    return RebrickableClient(_settings(), http_client=http)


def test_get_set() -> None:
    with _client() as client:
        dto = client.get_set("6024-1")
    assert dto.set_num == "6024-1"
    assert dto.name == "Police Car"


def test_iter_set_parts_follows_pagination() -> None:
    with _client() as client:
        lines = list(client.iter_set_parts("6024-1"))
    assert len(lines) == 2
    assert lines[0].part.part_num == "3024"
    assert lines[1].part.part_num == "3005"
    assert lines[1].is_spare is True


def test_iter_set_minifigs_and_minifig_parts() -> None:
    with _client() as client:
        minifigs = list(client.iter_set_minifigs("6024-1"))
        parts = list(client.iter_minifig_parts("cop01"))
    assert minifigs[0].minifig_num == "cop01"
    assert parts[0].part.part_num == "973c27h01pr0126"


def test_get_theme_and_iter_colors() -> None:
    with _client() as client:
        theme = client.get_theme(67)
        colors = list(client.iter_colors())
    assert theme.name == "Town"
    assert colors[0].name == "Black"


def test_get_set_not_found_raises() -> None:
    with _client() as client:
        with pytest.raises(RebrickableAPIError) as exc_info:
            client.get_set("missing-1")
    assert exc_info.value.status_code == 404


def test_authorization_header_on_requests() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, json=load_fixture("set_6024.json"))

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE)
    with RebrickableClient(_settings(), http_client=http) as client:
        client.get_set("6024-1")
    assert seen == ["key test-key"]
