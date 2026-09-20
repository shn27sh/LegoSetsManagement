"""Upsert catalog set-part lines and attach rows to physical set copies (``owned_sets``)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Color, OwnedSet, OwnedSetInventoryLine, Part, SetPartInventoryLine
from app.schemas.instance_inventory import (
    InstanceInventoryLineResponse,
    UpdateSetPartLineRequest,
)
from app.schemas.manual_add import ManualAddPartInput
from app.services.instance_inventory import get_instance_line_for_owned_set

MANUAL_SOURCE = "user"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _upsert_user_color(
    session: Session,
    *,
    external_id: int,
    color_name: str | None,
    fetched_at: datetime,
) -> Color:
    color = session.scalar(select(Color).where(Color.external_id == external_id))
    name = (color_name or "").strip() or f"Color {external_id}"
    if color is None:
        color = Color(
            external_id=external_id,
            name=name,
            rgb=None,
            source=MANUAL_SOURCE,
            fetched_at=fetched_at,
        )
        session.add(color)
    else:
        if color_name and color_name.strip():
            color.name = color_name.strip()
        color.fetched_at = fetched_at
    session.flush()
    return color


def _upsert_user_part(
    session: Session,
    *,
    part_num: str,
    part_name: str | None,
    fetched_at: datetime,
) -> Part:
    trimmed = part_num.strip()
    if not trimmed:
        raise InventoryPartsError("Part number is required")
    part = session.scalar(select(Part).where(Part.part_num == trimmed))
    if part is None:
        part = Part(
            part_num=trimmed,
            name=part_name.strip() if part_name and part_name.strip() else None,
            image_url=None,
            source=MANUAL_SOURCE,
            source_ref=trimmed,
            fetched_at=fetched_at,
        )
        session.add(part)
    else:
        if part_name and part_name.strip():
            part.name = part_name.strip()
        part.fetched_at = fetched_at
    session.flush()
    return part


class InventoryPartsError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def upsert_set_part_catalog_line(
    session: Session,
    catalog_set_id: int,
    line: ManualAddPartInput,
    *,
    fetched_at: datetime | None = None,
) -> SetPartInventoryLine:
    when = fetched_at or utc_now()
    part = _upsert_user_part(
        session,
        part_num=line.part_num,
        part_name=line.part_name,
        fetched_at=when,
    )
    color = _upsert_user_color(
        session,
        external_id=line.color_id,
        color_name=line.color_name,
        fetched_at=when,
    )
    existing = session.scalar(
        select(SetPartInventoryLine).where(
            SetPartInventoryLine.catalog_set_id == catalog_set_id,
            SetPartInventoryLine.part_id == part.id,
            SetPartInventoryLine.color_id == color.id,
        )
    )
    if existing is None:
        existing = SetPartInventoryLine(
            catalog_set_id=catalog_set_id,
            part_id=part.id,
            color_id=color.id,
            quantity=line.quantity,
            image_url=None,
            source=MANUAL_SOURCE,
            source_ref=None,
            fetched_at=when,
        )
        session.add(existing)
    else:
        existing.quantity = max(existing.quantity, line.quantity)
        existing.fetched_at = when
    session.flush()
    return existing


def add_set_part_to_owned_set(
    session: Session,
    owned_set_id: int,
    line: ManualAddPartInput,
) -> OwnedSetInventoryLine:
    owned_set = session.get(OwnedSet, owned_set_id)
    if owned_set is None:
        raise InventoryPartsError("Set copy not found", status_code=404)

    catalog_line = upsert_set_part_catalog_line(
        session,
        owned_set.catalog_set_id,
        line,
    )

    existing_instance = session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == owned_set_id,
            OwnedSetInventoryLine.set_part_inventory_line_id == catalog_line.id,
        )
    )
    if existing_instance is not None:
        raise InventoryPartsError(
            "This part is already in the inventory for this instance",
            status_code=409,
        )

    instance_line = OwnedSetInventoryLine(
        owned_set_id=owned_set_id,
        set_part_inventory_line_id=catalog_line.id,
        minifig_part_inventory_line_id=None,
        quantity=line.quantity,
        quantity_missing=0,
    )
    session.add(instance_line)
    session.flush()
    return instance_line


def instance_line_response(
    session: Session, instance_line: OwnedSetInventoryLine
) -> InstanceInventoryLineResponse:
    catalog_line_id = instance_line.set_part_inventory_line_id
    if catalog_line_id is None:
        raise InventoryPartsError("Not a set-part inventory line", status_code=400)
    catalog_line = session.get(SetPartInventoryLine, catalog_line_id)
    if catalog_line is None:
        raise InventoryPartsError("Catalog inventory line not found", status_code=404)
    return InstanceInventoryLineResponse(
        instance_line_id=instance_line.id,
        part_id=catalog_line.part_id,
        catalog_line_id=catalog_line.id,
        quantity=instance_line.quantity,
        quantity_missing=instance_line.quantity_missing,
    )


def _delete_set_part_catalog_line_if_orphan(
    session: Session, catalog_line_id: int
) -> None:
    ref_count = session.scalar(
        select(func.count())
        .select_from(OwnedSetInventoryLine)
        .where(OwnedSetInventoryLine.set_part_inventory_line_id == catalog_line_id)
    )
    if ref_count:
        return
    catalog_line = session.get(SetPartInventoryLine, catalog_line_id)
    if catalog_line is not None:
        session.delete(catalog_line)
        session.flush()


def _repoint_instance_to_catalog_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
    catalog_line: SetPartInventoryLine,
    *,
    quantity: int,
) -> None:
    if instance_line.set_part_inventory_line_id == catalog_line.id:
        instance_line.quantity = quantity
        return

    other = session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == instance_line.owned_set_id,
            OwnedSetInventoryLine.set_part_inventory_line_id == catalog_line.id,
            OwnedSetInventoryLine.id != instance_line.id,
        )
    )
    if other is not None:
        raise InventoryPartsError(
            "This part is already in the inventory for this instance",
            status_code=409,
        )

    old_catalog_line_id = instance_line.set_part_inventory_line_id
    instance_line.set_part_inventory_line_id = catalog_line.id
    instance_line.quantity = quantity
    session.flush()

    if old_catalog_line_id is not None:
        _delete_set_part_catalog_line_if_orphan(session, old_catalog_line_id)


def update_set_part_on_owned_set(
    session: Session,
    owned_set_id: int,
    instance_line_id: int,
    body: UpdateSetPartLineRequest,
) -> OwnedSetInventoryLine:
    instance_line = get_instance_line_for_owned_set(
        session, owned_set_id, instance_line_id
    )
    if instance_line is None or instance_line.set_part_inventory_line_id is None:
        raise InventoryPartsError("Inventory line not found", status_code=404)

    catalog_line = session.get(
        SetPartInventoryLine, instance_line.set_part_inventory_line_id
    )
    if catalog_line is None:
        raise InventoryPartsError("Catalog inventory line not found", status_code=404)

    part = session.get(Part, catalog_line.part_id)
    if part is None:
        raise InventoryPartsError("Part not found", status_code=404)

    when = utc_now()
    if body.part_name is not None:
        trimmed = body.part_name.strip()
        part.name = trimmed if trimmed else None
        part.fetched_at = when

    new_quantity = body.quantity if body.quantity is not None else instance_line.quantity
    if new_quantity <= 0:
        raise InventoryPartsError("quantity must be greater than 0")
    if instance_line.quantity_missing > new_quantity:
        raise InventoryPartsError(
            f"quantity_missing must be between 0 and {new_quantity}"
        )

    if body.color_id is not None or body.color_name is not None:
        current_color = session.get(Color, catalog_line.color_id)
        if current_color is None:
            raise InventoryPartsError("Color not found", status_code=404)
        color_external_id = (
            body.color_id if body.color_id is not None else current_color.external_id
        )
        color = _upsert_user_color(
            session,
            external_id=color_external_id,
            color_name=body.color_name,
            fetched_at=when,
        )
        if color.id != catalog_line.color_id:
            target = session.scalar(
                select(SetPartInventoryLine).where(
                    SetPartInventoryLine.catalog_set_id == catalog_line.catalog_set_id,
                    SetPartInventoryLine.part_id == catalog_line.part_id,
                    SetPartInventoryLine.color_id == color.id,
                )
            )
            if target is None:
                target = SetPartInventoryLine(
                    catalog_set_id=catalog_line.catalog_set_id,
                    part_id=catalog_line.part_id,
                    color_id=color.id,
                    quantity=new_quantity,
                    image_url=None,
                    source=MANUAL_SOURCE,
                    source_ref=None,
                    fetched_at=when,
                )
                session.add(target)
                session.flush()
            _repoint_instance_to_catalog_line(
                session, instance_line, target, quantity=new_quantity
            )
        else:
            instance_line.quantity = new_quantity
    else:
        instance_line.quantity = new_quantity

    session.flush()
    return instance_line


def delete_set_part_from_owned_set(
    session: Session,
    owned_set_id: int,
    instance_line_id: int,
) -> None:
    instance_line = get_instance_line_for_owned_set(
        session, owned_set_id, instance_line_id
    )
    if instance_line is None or instance_line.set_part_inventory_line_id is None:
        raise InventoryPartsError("Inventory line not found", status_code=404)

    catalog_line_id = instance_line.set_part_inventory_line_id
    session.delete(instance_line)
    session.flush()
    _delete_set_part_catalog_line_if_orphan(session, catalog_line_id)
