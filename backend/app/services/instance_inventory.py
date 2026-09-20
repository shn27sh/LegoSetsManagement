"""Per-copy inventory (quantities and missing counts) for each ``owned_sets`` row."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MinifigPartInventoryLine,
    MissingItem,
    OwnedSet,
    OwnedSetInventoryLine,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
)


class InstanceInventoryError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def clone_instance_inventory(session: Session, owned_set_id: int) -> None:
    """Create per-copy inventory rows from the catalog template for one set copy (`owned_sets`)."""
    owned_set = session.get(OwnedSet, owned_set_id)
    if owned_set is None:
        return

    existing_set_part_ids = set(
        session.scalars(
            select(OwnedSetInventoryLine.set_part_inventory_line_id).where(
                OwnedSetInventoryLine.owned_set_id == owned_set_id,
                OwnedSetInventoryLine.set_part_inventory_line_id.is_not(None),
            )
        ).all()
    )
    existing_minifig_part_ids = set(
        session.scalars(
            select(OwnedSetInventoryLine.minifig_part_inventory_line_id).where(
                OwnedSetInventoryLine.owned_set_id == owned_set_id,
                OwnedSetInventoryLine.minifig_part_inventory_line_id.is_not(None),
            )
        ).all()
    )

    catalog_set_id = owned_set.catalog_set_id
    for line in session.scalars(
        select(SetPartInventoryLine).where(
            SetPartInventoryLine.catalog_set_id == catalog_set_id
        )
    ).all():
        if line.id in existing_set_part_ids:
            continue
        session.add(
            OwnedSetInventoryLine(
                owned_set_id=owned_set_id,
                set_part_inventory_line_id=line.id,
                minifig_part_inventory_line_id=None,
                quantity=line.quantity,
                quantity_missing=0,
            )
        )

    minifig_ids = session.scalars(
        select(SetMinifigInventoryLine.catalog_minifig_id).where(
            SetMinifigInventoryLine.catalog_set_id == catalog_set_id
        )
    ).all()
    for minifig_id in minifig_ids:
        for line in session.scalars(
            select(MinifigPartInventoryLine).where(
                MinifigPartInventoryLine.catalog_minifig_id == minifig_id
            )
        ).all():
            if line.id in existing_minifig_part_ids:
                continue
            session.add(
                OwnedSetInventoryLine(
                    owned_set_id=owned_set_id,
                    set_part_inventory_line_id=None,
                    minifig_part_inventory_line_id=line.id,
                    quantity=line.quantity,
                    quantity_missing=0,
                )
            )

    session.flush()


def ensure_instance_inventory(session: Session, owned_set_id: int) -> None:
    """Add instance lines for any new catalog lines without touching existing rows."""
    clone_instance_inventory(session, owned_set_id)


def ensure_instance_inventory_for_catalog(session: Session, catalog_set_id: int) -> None:
    owned_set_ids = session.scalars(
        select(OwnedSet.id).where(OwnedSet.catalog_set_id == catalog_set_id)
    ).all()
    for owned_set_id in owned_set_ids:
        ensure_instance_inventory(session, owned_set_id)


def refresh_instance_quantities_for_catalog(session: Session, catalog_set_id: int) -> None:
    """Copy catalog quantity changes to set copies without touching missing counts."""
    set_part_rows = session.execute(
        select(OwnedSetInventoryLine, SetPartInventoryLine.quantity)
        .join(
            SetPartInventoryLine,
            OwnedSetInventoryLine.set_part_inventory_line_id == SetPartInventoryLine.id,
        )
        .join(OwnedSet, OwnedSet.id == OwnedSetInventoryLine.owned_set_id)
        .where(OwnedSet.catalog_set_id == catalog_set_id)
    ).all()
    for instance_line, quantity in set_part_rows:
        instance_line.quantity = quantity

    minifig_part_rows = session.execute(
        select(
            OwnedSetInventoryLine,
            MinifigPartInventoryLine.quantity * SetMinifigInventoryLine.quantity,
        )
        .join(
            MinifigPartInventoryLine,
            OwnedSetInventoryLine.minifig_part_inventory_line_id
            == MinifigPartInventoryLine.id,
        )
        .join(OwnedSet, OwnedSet.id == OwnedSetInventoryLine.owned_set_id)
        .join(
            SetMinifigInventoryLine,
            SetMinifigInventoryLine.catalog_set_id == OwnedSet.catalog_set_id,
        )
        .where(
            OwnedSet.catalog_set_id == catalog_set_id,
            SetMinifigInventoryLine.catalog_minifig_id
            == MinifigPartInventoryLine.catalog_minifig_id,
        )
    ).all()
    for instance_line, quantity in minifig_part_rows:
        instance_line.quantity = quantity

    session.flush()


def clear_instance_inventory(session: Session, owned_set_id: int) -> None:
    session.execute(
        delete(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == owned_set_id
        )
    )
    session.flush()


def count_lines_with_missing(session: Session, owned_set_ids: list[int]) -> dict[int, int]:
    if not owned_set_ids:
        return {}
    rows = session.execute(
        select(OwnedSetInventoryLine.owned_set_id, func.count())
        .where(
            OwnedSetInventoryLine.owned_set_id.in_(owned_set_ids),
            OwnedSetInventoryLine.quantity_missing > 0,
        )
        .group_by(OwnedSetInventoryLine.owned_set_id)
    ).all()
    return {owned_set_id: int(count) for owned_set_id, count in rows}


def get_instance_line_for_owned_set(
    session: Session,
    owned_set_id: int,
    instance_line_id: int,
) -> OwnedSetInventoryLine | None:
    return session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.id == instance_line_id,
            OwnedSetInventoryLine.owned_set_id == owned_set_id,
        )
    )


def find_instance_line_for_catalog_ref(
    session: Session,
    owned_set_id: int,
    *,
    set_part_inventory_line_id: int | None = None,
    minifig_part_inventory_line_id: int | None = None,
) -> OwnedSetInventoryLine | None:
    if set_part_inventory_line_id is not None:
        line = session.scalar(
            select(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.owned_set_id == owned_set_id,
                OwnedSetInventoryLine.set_part_inventory_line_id
                == set_part_inventory_line_id,
            )
        )
        if line is not None:
            return line

    if minifig_part_inventory_line_id is not None:
        return session.scalar(
            select(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.owned_set_id == owned_set_id,
                OwnedSetInventoryLine.minifig_part_inventory_line_id
                == minifig_part_inventory_line_id,
            )
        )

    return None


def resolve_or_create_instance_line_for_catalog_ref(
    session: Session,
    owned_set: OwnedSet,
    *,
    set_part_inventory_line_id: int | None = None,
    minifig_part_inventory_line_id: int | None = None,
) -> OwnedSetInventoryLine:
    line = find_instance_line_for_catalog_ref(
        session,
        owned_set.id,
        set_part_inventory_line_id=set_part_inventory_line_id,
        minifig_part_inventory_line_id=minifig_part_inventory_line_id,
    )
    if line is not None:
        return line

    ensure_instance_inventory(session, owned_set.id)
    line = find_instance_line_for_catalog_ref(
        session,
        owned_set.id,
        set_part_inventory_line_id=set_part_inventory_line_id,
        minifig_part_inventory_line_id=minifig_part_inventory_line_id,
    )
    if line is None:
        raise InstanceInventoryError("Inventory line does not belong to this set copy")
    return line


def update_instance_inventory_line(
    session: Session,
    owned_set_id: int,
    instance_line_id: int,
    *,
    quantity: int | None = None,
    quantity_missing: int | None = None,
) -> OwnedSetInventoryLine:
    line = get_instance_line_for_owned_set(session, owned_set_id, instance_line_id)
    if line is None:
        raise InstanceInventoryError("Inventory line not found", status_code=404)

    new_quantity = quantity if quantity is not None else line.quantity
    new_missing = quantity_missing if quantity_missing is not None else line.quantity_missing

    if new_quantity <= 0:
        raise InstanceInventoryError("quantity must be greater than 0")
    if new_missing < 0 or new_missing > new_quantity:
        raise InstanceInventoryError(
            f"quantity_missing must be between 0 and {new_quantity}"
        )

    line.quantity = new_quantity
    line.quantity_missing = new_missing

    if new_missing == 0:
        missing = session.scalar(
            select(MissingItem).where(
                MissingItem.owned_set_inventory_line_id == line.id
            )
        )
        if missing is not None:
            session.delete(missing)

    session.flush()
    return line
