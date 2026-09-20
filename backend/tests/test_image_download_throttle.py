"""CDN image download throttling (Phase 4)."""

from __future__ import annotations

import httpx
import pytest

from app.services.image_download import HttpxImageDownloader


def test_image_downloader_reuses_client_and_throttles(monkeypatch) -> None:
    sleeps: list[float] = []
    monotonic_values = iter([0.0, 0.1, 0.1])

    def fake_monotonic() -> float:
        return next(monotonic_values)

    monkeypatch.setattr(
        "app.services.image_download.time.monotonic",
        fake_monotonic,
    )
    monkeypatch.setattr(
        "app.services.image_download.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=b"jpeg-bytes",
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = HttpxImageDownloader(
        min_interval_seconds=0.5,
        http_client=http,
    )
    try:
        downloader.download("https://cdn.example/one.jpg")
        downloader.download("https://cdn.example/two.jpg")
    finally:
        downloader.close()

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(0.4, abs=0.01)


def test_image_downloader_context_manager_closes_owned_client() -> None:
    with HttpxImageDownloader.from_settings() as downloader:
        assert downloader._owns_client is True
    assert downloader._http.is_closed
