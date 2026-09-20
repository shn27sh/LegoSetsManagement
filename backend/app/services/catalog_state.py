"""Derive catalog sync state for API responses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CatalogMinifig, CatalogSet, ElementImage, Part
from app.services.image_blob import (
    catalog_minifig_has_image,
    catalog_set_has_image,
    element_has_image,
    part_has_image,
)
from app.services.image_urls import (
    catalog_minifig_image_url,
    catalog_set_image_url,
    element_image_url,
    part_image_url,
)


def catalog_sync_state(catalog_set: CatalogSet) -> str:
    if catalog_set.source == "csv_import" and catalog_set.name is None:
        return "pending"
    return "ok"


def resolve_catalog_image_url(catalog_set: CatalogSet) -> str | None:
    if catalog_set_has_image(catalog_set):
        return catalog_set_image_url(catalog_set.id)
    return None


def resolve_part_image_url(part: Part) -> str | None:
    if part_has_image(part):
        return part_image_url(part.id)
    return None


def resolve_catalog_minifig_image_url(catalog_minifig: CatalogMinifig) -> str | None:
    if catalog_minifig_has_image(catalog_minifig):
        return catalog_minifig_image_url(catalog_minifig.id)
    return None


def load_element_image_urls(
    session: Session,
    element_ids: Iterable[str],
) -> dict[str, str]:
    unique_ids = {element_id for element_id in element_ids if element_id}
    if not unique_ids:
        return {}
    rows = session.scalars(
        select(ElementImage).where(
            ElementImage.element_id.in_(unique_ids),
            ElementImage.image_blob.isnot(None),
            ElementImage.image_content_type.isnot(None),
        )
    ).all()
    return {
        row.element_id: element_image_url(row.element_id)
        for row in rows
        if element_has_image(row)
    }


def resolve_line_image_url(
    *,
    element_ids: Sequence[str],
    part: Part,
    element_url_by_id: Mapping[str, str],
) -> str | None:
    for element_id in element_ids:
        url = element_url_by_id.get(element_id)
        if url:
            return url
    return resolve_part_image_url(part)


def missing_image_url_for_part(
    part: Part,
    *,
    quantity_missing: int,
    element_ids: Sequence[str] = (),
    element_url_by_id: Mapping[str, str] | None = None,
) -> str | None:
    if quantity_missing <= 0:
        return None
    if element_url_by_id is not None:
        return resolve_line_image_url(
            element_ids=element_ids,
            part=part,
            element_url_by_id=element_url_by_id,
        )
    return resolve_part_image_url(part)
