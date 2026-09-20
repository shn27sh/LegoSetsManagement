"""Download remote image URLs into existing SQLite BLOB image columns."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.image_download_settings import (
    ImageDownloadSettings,
    load_image_download_settings,
)
from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    ElementImage,
    MinifigPartInventoryLine,
    Part,
    SetPartInventoryLine,
)
from app.services.image_blob import (
    ImageBlobError,
    catalog_minifig_has_image,
    catalog_set_has_image,
    element_has_image,
    part_has_image,
    set_catalog_minifig_image,
    set_catalog_set_image,
    set_element_image,
    set_part_image,
)

logger = logging.getLogger(__name__)


class ImageDownloadError(Exception):
    """Raised when a remote image could not be fetched or stored."""


@dataclass(frozen=True)
class DownloadedImage:
    content: bytes
    content_type: str


class ImageDownloader(Protocol):
    def download(self, url: str) -> DownloadedImage: ...


class HttpxImageDownloader:
    """HTTP(S) image fetcher with optional rate limiting and connection reuse."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        min_interval_seconds: float = 0.3,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._min_interval_seconds = max(0.0, min_interval_seconds)
        self._owns_client = http_client is None
        if http_client is None:
            self._http = httpx.Client(
                timeout=timeout_seconds,
                follow_redirects=True,
            )
        else:
            self._http = http_client
        self._last_request_at: float | None = None

    @classmethod
    def from_settings(
        cls,
        settings: ImageDownloadSettings | None = None,
    ) -> HttpxImageDownloader:
        loaded = settings or load_image_download_settings()
        return cls(
            timeout_seconds=loaded.timeout_seconds,
            min_interval_seconds=loaded.min_interval_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> HttpxImageDownloader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._min_interval_seconds <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)

    def download(self, url: str) -> DownloadedImage:
        if not url.startswith(("http://", "https://")):
            raise ImageDownloadError("Image URL must be HTTP(S)")
        self._throttle()
        try:
            response = self._http.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImageDownloadError(str(exc)) from exc
        finally:
            self._last_request_at = time.monotonic()
        return DownloadedImage(
            content=response.content,
            content_type=response.headers.get("content-type", ""),
        )


@contextmanager
def image_downloader_for_sync(
    downloader: ImageDownloader | None,
    *,
    images_enabled: bool,
) -> Iterator[ImageDownloader | None]:
    """Provide a shared downloader for sync image phases; close when owned."""
    if not images_enabled:
        yield None
        return
    if downloader is not None:
        yield downloader
        return
    with HttpxImageDownloader.from_settings() as owned:
        yield owned


def download_catalog_set_image(
    session: Session,
    catalog_set: CatalogSet,
    downloader: ImageDownloader,
    *,
    replace_existing: bool = False,
) -> bool:
    if not catalog_set.image_url or (
        catalog_set_has_image(catalog_set) and not replace_existing
    ):
        return False
    image = downloader.download(catalog_set.image_url)
    try:
        set_catalog_set_image(
            session,
            catalog_set.id,
            content=image.content,
            content_type=image.content_type,
        )
    except ImageBlobError as exc:
        raise ImageDownloadError(str(exc)) from exc
    return True


def download_catalog_minifig_image(
    session: Session,
    catalog_minifig: CatalogMinifig,
    downloader: ImageDownloader,
    *,
    replace_existing: bool = False,
) -> bool:
    if not catalog_minifig.image_url or (
        catalog_minifig_has_image(catalog_minifig) and not replace_existing
    ):
        return False
    image = downloader.download(catalog_minifig.image_url)
    try:
        set_catalog_minifig_image(
            session,
            catalog_minifig.id,
            content=image.content,
            content_type=image.content_type,
        )
    except ImageBlobError as exc:
        raise ImageDownloadError(str(exc)) from exc
    return True


def download_part_image(
    session: Session,
    part: Part,
    downloader: ImageDownloader,
    *,
    replace_existing: bool = False,
) -> bool:
    if not part.image_url or (part_has_image(part) and not replace_existing):
        return False
    image = downloader.download(part.image_url)
    try:
        set_part_image(
            session,
            part.id,
            content=image.content,
            content_type=image.content_type,
        )
    except ImageBlobError as exc:
        raise ImageDownloadError(str(exc)) from exc
    return True


def download_element_image(
    session: Session,
    element_id: str,
    source_url: str,
    downloader: ImageDownloader,
    *,
    replace_existing: bool = False,
) -> bool:
    if not source_url:
        return False
    existing = session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if existing is not None and element_has_image(existing) and not replace_existing:
        return False
    image = downloader.download(source_url)
    try:
        set_element_image(
            session,
            element_id,
            content=image.content,
            content_type=image.content_type,
        )
    except ImageBlobError as exc:
        raise ImageDownloadError(str(exc)) from exc
    return True
