"""Missing-part tracking; photos stored on element or part rows."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    MinifigPartInventoryLine,
    MissingItem,
    OwnedSet,
    OwnedSetInventoryLine,
    Part,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
)
from app.schemas.missing import MissingImageResponse, MissingUpsertRequest, MissingUpsertResponse
from app.services.catalog_state import (
    load_element_image_urls,
    resolve_line_image_url,
)
from app.services.image_blob import (
    ImageBlobError,
    clear_element_image,
    clear_part_image,
    get_element_image,
    get_part_image,
    set_element_image,
    set_part_image,
)
from app.services.part_color_catalog_service import element_ids_for_part_color
from app.services.instance_inventory import (
    InstanceInventoryError,
    resolve_or_create_instance_line_for_catalog_ref,
)


class MissingItemError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _part_for_instance_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
) -> Part | None:
    if instance_line.set_part_inventory_line_id is not None:
        line = session.get(SetPartInventoryLine, instance_line.set_part_inventory_line_id)
        if line is None:
            return None
        return session.get(Part, line.part_id)
    assert instance_line.minifig_part_inventory_line_id is not None
    line = session.get(
        MinifigPartInventoryLine, instance_line.minifig_part_inventory_line_id
    )
    if line is None:
        return None
    return session.get(Part, line.part_id)


def _catalog_line_for_instance_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
) -> SetPartInventoryLine | MinifigPartInventoryLine | None:
    if instance_line.set_part_inventory_line_id is not None:
        return session.get(SetPartInventoryLine, instance_line.set_part_inventory_line_id)
    if instance_line.minifig_part_inventory_line_id is None:
        return None
    return session.get(
        MinifigPartInventoryLine, instance_line.minifig_part_inventory_line_id
    )


def _element_ids_for_catalog_line(
    session: Session,
    line: SetPartInventoryLine | MinifigPartInventoryLine,
) -> list[str]:
    return element_ids_for_part_color(session, line.part_id, line.color_id)


def _primary_element_id_for_instance_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
) -> str | None:
    catalog_line = _catalog_line_for_instance_line(session, instance_line)
    if catalog_line is None:
        return None
    element_ids = _element_ids_for_catalog_line(session, catalog_line)
    return element_ids[0] if element_ids else None


def _image_urls_for_instance_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
    part: Part,
) -> tuple[str | None, str | None]:
    catalog_line = _catalog_line_for_instance_line(session, instance_line)
    element_ids = (
        _element_ids_for_catalog_line(session, catalog_line)
        if catalog_line is not None
        else []
    )
    element_url_by_id = load_element_image_urls(session, element_ids)
    resolved = resolve_line_image_url(
        element_ids=element_ids,
        part=part,
        element_url_by_id=element_url_by_id,
    )
    return resolved, resolved


def upsert_missing(
    session: Session,
    owned_set_id: int,
    body: MissingUpsertRequest,
) -> MissingUpsertResponse:
    owned_set = session.get(OwnedSet, owned_set_id)
    if owned_set is None:
        raise MissingItemError("Set copy not found", status_code=404)

    _validate_catalog_line_for_owned_set(session, owned_set, body)

    try:
        instance_line = resolve_or_create_instance_line_for_catalog_ref(
            session,
            owned_set,
            set_part_inventory_line_id=body.set_part_inventory_line_id,
            minifig_part_inventory_line_id=body.minifig_part_inventory_line_id,
        )
    except InstanceInventoryError as exc:
        raise MissingItemError(str(exc), status_code=exc.status_code) from exc

    if body.quantity_missing > instance_line.quantity:
        raise MissingItemError(
            f"quantity_missing cannot exceed inventory quantity ({instance_line.quantity})"
        )

    if body.quantity_missing == 0:
        cleared_id = 0
        if instance_line.missing_item is not None:
            cleared_id = instance_line.missing_item.id
            session.delete(instance_line.missing_item)
        instance_line.quantity_missing = 0
        session.flush()
        return MissingUpsertResponse(
            owned_set_id=owned_set_id,
            missing_item_id=cleared_id,
            updated_lines=1,
        )

    instance_line.quantity_missing = body.quantity_missing
    missing = instance_line.missing_item
    if missing is None:
        missing = MissingItem(
            owned_set_id=owned_set_id,
            owned_set_inventory_line_id=instance_line.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(missing)
    else:
        missing.updated_at = utc_now()

    session.flush()
    return MissingUpsertResponse(
        owned_set_id=owned_set_id,
        missing_item_id=missing.id,
        updated_lines=1,
    )


def upload_missing_image(
    session: Session,
    owned_set_id: int,
    missing_item_id: int,
    *,
    content: bytes,
    content_type: str,
) -> MissingImageResponse:
    missing = _get_missing_for_owned_set(session, owned_set_id, missing_item_id)
    instance_line = missing.owned_set_inventory_line

    if instance_line.quantity_missing <= 0:
        raise MissingItemError("Cannot attach image when missing quantity is 0")

    part = _part_for_instance_line(session, instance_line)
    if part is None:
        raise MissingItemError("Part not found for inventory line", status_code=404)

    primary_element_id = _primary_element_id_for_instance_line(session, instance_line)
    if primary_element_id is not None:
        set_element_image(
            session,
            primary_element_id,
            content=content,
            content_type=content_type,
            source="user",
        )
    else:
        set_part_image(session, part.id, content=content, content_type=content_type)
    missing.updated_at = utc_now()
    session.flush()

    missing_url, part_url = _image_urls_for_instance_line(session, instance_line, part)
    return MissingImageResponse(
        missing_item_id=missing.id,
        missing_image_url=missing_url,
        part_image_url=part_url,
    )


def delete_missing_image(
    session: Session,
    owned_set_id: int,
    missing_item_id: int,
) -> MissingImageResponse:
    missing = _get_missing_for_owned_set(session, owned_set_id, missing_item_id)
    instance_line = missing.owned_set_inventory_line
    part = _part_for_instance_line(session, instance_line)
    if part is not None:
        primary_element_id = _primary_element_id_for_instance_line(session, instance_line)
        if primary_element_id is not None:
            try:
                clear_element_image(session, primary_element_id)
            except ImageBlobError:
                pass
        else:
            clear_part_image(session, part.id)
    missing.updated_at = utc_now()
    session.flush()
    return MissingImageResponse(
        missing_item_id=missing.id,
        missing_image_url=None,
        part_image_url=None,
    )


def resolve_missing_image_for_serving(
    session: Session,
    missing_item_id: int,
) -> tuple[bytes, str] | None:
    missing = session.get(MissingItem, missing_item_id)
    if missing is None:
        return None
    instance_line = missing.owned_set_inventory_line
    if instance_line.quantity_missing <= 0:
        return None
    part = _part_for_instance_line(session, instance_line)
    if part is None:
        return None
    primary_element_id = _primary_element_id_for_instance_line(session, instance_line)
    if primary_element_id is not None:
        stored = get_element_image(session, primary_element_id)
        if stored is not None:
            return stored.content, stored.content_type
    stored = get_part_image(session, part.id)
    if stored is None:
        return None
    return stored.content, stored.content_type


def _get_missing_for_owned_set(
    session: Session,
    owned_set_id: int,
    missing_item_id: int,
) -> MissingItem:
    missing = session.scalar(
        select(MissingItem)
        .where(
            MissingItem.id == missing_item_id,
            MissingItem.owned_set_id == owned_set_id,
        )
        .options(selectinload(MissingItem.owned_set_inventory_line))
    )
    if missing is None:
        raise MissingItemError("Missing item not found", status_code=404)
    return missing


def _validate_catalog_line_for_owned_set(
    session: Session,
    owned_set: OwnedSet,
    body: MissingUpsertRequest,
) -> None:
    if body.set_part_inventory_line_id is not None:
        line = session.get(SetPartInventoryLine, body.set_part_inventory_line_id)
        if line is None or line.catalog_set_id != owned_set.catalog_set_id:
            raise MissingItemError("Inventory line does not belong to this set copy")
        return

    line = session.get(MinifigPartInventoryLine, body.minifig_part_inventory_line_id)
    if line is None:
        raise MissingItemError("Inventory line does not belong to this set copy")

    in_set = session.scalar(
        select(SetMinifigInventoryLine.id).where(
            SetMinifigInventoryLine.catalog_set_id == owned_set.catalog_set_id,
            SetMinifigInventoryLine.catalog_minifig_id == line.catalog_minifig_id,
        )
    )
    if in_set is None:
        raise MissingItemError("Inventory line does not belong to this set copy")
