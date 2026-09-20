"""HTTP client for the Rebrickable API v3."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.rebrickable.config import RebrickableSettings, load_rebrickable_settings
from app.rebrickable.dto import (
    CatalogSetDTO,
    ColorDTO,
    MinifigPartLineDTO,
    SetMinifigLineDTO,
    SetPartLineDTO,
    ThemeDTO,
)
from app.rebrickable.exceptions import RebrickableAPIError
from app.rebrickable.mappers import (
    map_color,
    map_minifig_part_result,
    map_set,
    map_set_minifig_result,
    map_set_part_result,
    map_theme,
)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RebrickableClient:
    """Thin Rebrickable v3 client: auth, pagination, retries. No database I/O."""

    def __init__(
        self,
        settings: RebrickableSettings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or load_rebrickable_settings()
        auth_header = f"key {self._settings.api_key}"
        self._owns_client = http_client is None
        if http_client is None:
            self._http = httpx.Client(
                base_url=self._settings.base_url,
                timeout=self._settings.timeout_seconds,
                headers={"Authorization": auth_header},
            )
        else:
            self._http = http_client
            self._http.headers.setdefault("Authorization", auth_header)
        self._last_request_at: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> RebrickableClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_set(self, set_num: str) -> CatalogSetDTO:
        return map_set(self._get_json(f"lego/sets/{set_num}/"))

    def get_theme(self, theme_id: int) -> ThemeDTO:
        return map_theme(self._get_json(f"lego/themes/{theme_id}/"))

    def iter_set_parts(self, set_num: str) -> Iterator[SetPartLineDTO]:
        for item in self._iter_paginated_results(f"lego/sets/{set_num}/parts/"):
            yield map_set_part_result(item)

    def iter_set_minifigs(self, set_num: str) -> Iterator[SetMinifigLineDTO]:
        for item in self._iter_paginated_results(f"lego/sets/{set_num}/minifigs/"):
            yield map_set_minifig_result(item)

    def iter_minifig_parts(self, minifig_num: str) -> Iterator[MinifigPartLineDTO]:
        for item in self._iter_paginated_results(f"lego/minifigs/{minifig_num}/parts/"):
            yield map_minifig_part_result(item)

    def iter_colors(self) -> Iterator[ColorDTO]:
        for item in self._iter_paginated_results("lego/colors/"):
            yield map_color(item)

    def _get_json(self, path_or_url: str) -> dict[str, Any]:
        response = self._request("GET", path_or_url)
        data = response.json()
        if not isinstance(data, dict):
            raise RebrickableAPIError(
                "expected JSON object response",
                status_code=response.status_code,
                url=str(response.url),
            )
        return data

    def _iter_paginated_results(self, path: str) -> Iterator[dict[str, Any]]:
        page_path: str | None = path
        while page_path:
            payload = self._get_json(page_path)
            results = payload.get("results")
            if not isinstance(results, list):
                raise RebrickableAPIError(
                    f"paginated response missing results list: {page_path}",
                    url=page_path,
                )
            for item in results:
                if isinstance(item, dict):
                    yield item
            next_url = payload.get("next")
            page_path = str(next_url) if next_url else None

    def _throttle(self) -> None:
        interval = self._settings.min_request_interval_seconds
        if interval <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)

    def _request(self, method: str, path_or_url: str) -> httpx.Response:
        last_response: httpx.Response | None = None
        absolute = path_or_url.startswith("http")

        for attempt in range(self._settings.max_retries + 1):
            self._throttle()
            if absolute:
                response = self._http.request(method, path_or_url)
            else:
                response = self._http.request(method, path_or_url)
            self._last_request_at = time.monotonic()

            if response.status_code < 400:
                return response

            last_response = response
            if (
                response.status_code not in RETRYABLE_STATUS
                or attempt >= self._settings.max_retries
            ):
                break

            delay = min(2**attempt, 8)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, int(retry_after))
            time.sleep(delay)

        assert last_response is not None
        detail = last_response.text[:500]
        raise RebrickableAPIError(
            f"Rebrickable API error {last_response.status_code}: {detail}",
            status_code=last_response.status_code,
            url=str(last_response.url),
        )
