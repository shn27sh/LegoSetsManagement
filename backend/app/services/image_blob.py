"""Store and serve JPEG/PNG images in SQLite BLOB columns."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.image_settings import get_max_image_bytes, normalize_content_type
from app.db.models import CatalogMinifig, CatalogSet, ElementImage, Part, utc_now


class ImageBlobError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class StoredImage:
    content: bytes
    content_type: str


def validate_image_upload(content: bytes, content_type: str) -> str:
    normalized = normalize_content_type(content_type)
    if normalized is None:
        raise ImageBlobError("File must be JPEG or PNG")
    if len(content) > get_max_image_bytes():
        raise ImageBlobError("Image file too large", status_code=413)
    return normalized


def part_has_image(part: Part) -> bool:
    return part.image_blob is not None and part.image_content_type is not None


def catalog_set_has_image(catalog_set: CatalogSet) -> bool:
    return (
        catalog_set.image_blob is not None
        and catalog_set.image_content_type is not None
    )


def catalog_minifig_has_image(catalog_minifig: CatalogMinifig) -> bool:
    return (
        catalog_minifig.image_blob is not None
        and catalog_minifig.image_content_type is not None
    )


def element_has_image(element_image: ElementImage) -> bool:
    return (
        element_image.image_blob is not None
        and element_image.image_content_type is not None
    )


def get_part_image(session: Session, part_id: int) -> StoredImage | None:
    part = session.get(Part, part_id)
    if part is None or not part_has_image(part):
        return None
    assert part.image_blob is not None
    assert part.image_content_type is not None
    return StoredImage(content=part.image_blob, content_type=part.image_content_type)


def set_part_image(
    session: Session,
    part_id: int,
    *,
    content: bytes,
    content_type: str,
) -> Part:
    part = session.get(Part, part_id)
    if part is None:
        raise ImageBlobError("Part not found", status_code=404)
    normalized = validate_image_upload(content, content_type)
    part.image_blob = content
    part.image_content_type = normalized
    part.image_byte_size = len(content)
    part.part_image_user_removed = False
    session.flush()
    return part


def clear_part_image(session: Session, part_id: int) -> Part:
    part = session.get(Part, part_id)
    if part is None:
        raise ImageBlobError("Part not found", status_code=404)
    part.image_blob = None
    part.image_content_type = None
    part.image_byte_size = None
    part.part_image_user_removed = True
    session.flush()
    return part


def get_catalog_set_image(session: Session, catalog_set_id: int) -> StoredImage | None:
    catalog_set = session.get(CatalogSet, catalog_set_id)
    if catalog_set is None or not catalog_set_has_image(catalog_set):
        return None
    assert catalog_set.image_blob is not None
    assert catalog_set.image_content_type is not None
    return StoredImage(
        content=catalog_set.image_blob,
        content_type=catalog_set.image_content_type,
    )


def set_catalog_set_image(
    session: Session,
    catalog_set_id: int,
    *,
    content: bytes,
    content_type: str,
) -> CatalogSet:
    catalog_set = session.get(CatalogSet, catalog_set_id)
    if catalog_set is None:
        raise ImageBlobError("Catalog set not found", status_code=404)
    normalized = validate_image_upload(content, content_type)
    catalog_set.image_blob = content
    catalog_set.image_content_type = normalized
    catalog_set.image_byte_size = len(content)
    session.flush()
    return catalog_set


def clear_catalog_set_image(session: Session, catalog_set_id: int) -> CatalogSet:
    catalog_set = session.get(CatalogSet, catalog_set_id)
    if catalog_set is None:
        raise ImageBlobError("Catalog set not found", status_code=404)
    catalog_set.image_blob = None
    catalog_set.image_content_type = None
    catalog_set.image_byte_size = None
    session.flush()
    return catalog_set


def get_catalog_minifig_image(
    session: Session, catalog_minifig_id: int
) -> StoredImage | None:
    catalog_minifig = session.get(CatalogMinifig, catalog_minifig_id)
    if catalog_minifig is None or not catalog_minifig_has_image(catalog_minifig):
        return None
    assert catalog_minifig.image_blob is not None
    assert catalog_minifig.image_content_type is not None
    return StoredImage(
        content=catalog_minifig.image_blob,
        content_type=catalog_minifig.image_content_type,
    )


def set_catalog_minifig_image(
    session: Session,
    catalog_minifig_id: int,
    *,
    content: bytes,
    content_type: str,
) -> CatalogMinifig:
    catalog_minifig = session.get(CatalogMinifig, catalog_minifig_id)
    if catalog_minifig is None:
        raise ImageBlobError("Catalog minifig not found", status_code=404)
    normalized = validate_image_upload(content, content_type)
    catalog_minifig.image_blob = content
    catalog_minifig.image_content_type = normalized
    catalog_minifig.image_byte_size = len(content)
    session.flush()
    return catalog_minifig


def clear_catalog_minifig_image(
    session: Session, catalog_minifig_id: int
) -> CatalogMinifig:
    catalog_minifig = session.get(CatalogMinifig, catalog_minifig_id)
    if catalog_minifig is None:
        raise ImageBlobError("Catalog minifig not found", status_code=404)
    catalog_minifig.image_blob = None
    catalog_minifig.image_content_type = None
    catalog_minifig.image_byte_size = None
    session.flush()
    return catalog_minifig


def get_element_image(session: Session, element_id: str) -> StoredImage | None:
    row = session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if row is None or not element_has_image(row):
        return None
    assert row.image_blob is not None
    assert row.image_content_type is not None
    return StoredImage(content=row.image_blob, content_type=row.image_content_type)


def set_element_image(
    session: Session,
    element_id: str,
    *,
    content: bytes,
    content_type: str,
    source: str = "rebrickable",
) -> ElementImage:
    normalized = validate_image_upload(content, content_type)
    row = session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if row is None:
        row = ElementImage(
            element_id=element_id,
            source=source,
            fetched_at=utc_now(),
        )
        session.add(row)
    row.image_blob = content
    row.image_content_type = normalized
    row.image_byte_size = len(content)
    row.source = source
    row.fetched_at = utc_now()
    session.flush()
    return row


def clear_element_image(session: Session, element_id: str) -> ElementImage:
    row = session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if row is None:
        raise ImageBlobError("Element image not found", status_code=404)
    row.image_blob = None
    row.image_content_type = None
    row.image_byte_size = None
    session.flush()
    return row
