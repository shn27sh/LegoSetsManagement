"""Minimal model factories for tests."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.lego_set_number import LegoSetId, to_rebrickable_set_num
from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    Color,
    MissingItem,
    MinifigPartInventoryLine,
    OwnedSet,
    OwnedSetInventoryLine,
    Part,
    PartAlias,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
    Theme,
)
from app.services.part_color_catalog_service import set_element_ids_for_part_color
from app.services.instance_inventory import clone_instance_inventory

# Minimal 1x1 PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def add_theme(session: Session, *, external_id: int = 1, name: str = "Town") -> Theme:
    theme = Theme(
        external_id=external_id,
        name=name,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(theme)
    session.flush()
    return theme


def add_catalog_set(
    session: Session,
    *,
    set_number: int = 6024,
    set_variant: int = 1,
    theme: Theme | None = None,
) -> CatalogSet:
    rb = to_rebrickable_set_num(LegoSetId(set_number, set_variant))
    catalog_set = CatalogSet(
        set_number=set_number,
        set_variant=set_variant,
        name="Police Car",
        year=1980,
        theme_id=theme.id if theme else None,
        source="rebrickable",
        source_ref=rb,
        fetched_at=utc_now(),
    )
    session.add(catalog_set)
    session.flush()
    return catalog_set


def add_owned_set(
    session: Session,
    catalog_set: CatalogSet,
    *,
    investigated: bool = False,
    label: str | None = None,
    with_inventory: bool = True,
) -> OwnedSet:
    owned_set = OwnedSet(
        catalog_set_id=catalog_set.id,
        investigated=investigated,
        label=label,
        created_at=utc_now(),
    )
    session.add(owned_set)
    session.flush()
    if with_inventory:
        clone_instance_inventory(session, owned_set.id)
    return owned_set


def add_part(session: Session, *, part_num: str = "3024") -> Part:
    part = Part(
        part_num=part_num,
        name="Plate 1 x 1",
        source="rebrickable",
        source_ref=part_num,
        fetched_at=utc_now(),
    )
    session.add(part)
    session.flush()
    return part


def add_color(session: Session, *, external_id: int = 0, name: str = "Black") -> Color:
    color = Color(
        external_id=external_id,
        name=name,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(color)
    session.flush()
    return color


def add_set_part_inventory_line(
    session: Session,
    *,
    catalog_set: CatalogSet,
    part: Part,
    color: Color,
    quantity: int = 4,
) -> SetPartInventoryLine:
    line = SetPartInventoryLine(
        catalog_set_id=catalog_set.id,
        part_id=part.id,
        color_id=color.id,
        quantity=quantity,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(line)
    session.flush()
    return line


def add_element_id_for_set_part_line(
    session: Session,
    *,
    line: SetPartInventoryLine,
    element_id: str = "302400",
) -> None:
    set_element_ids_for_part_color(
        session,
        line.part_id,
        line.color_id,
        (element_id,),
        merge=True,
    )
    session.flush()


def add_catalog_stub(
    session: Session,
    *,
    set_number: int = 9999,
    set_variant: int = 1,
) -> CatalogSet:
    rb = to_rebrickable_set_num(LegoSetId(set_number, set_variant))
    catalog_set = CatalogSet(
        set_number=set_number,
        set_variant=set_variant,
        name=None,
        year=None,
        theme_id=None,
        num_parts=None,
        image_url=None,
        source="csv_import",
        source_ref=rb,
        fetched_at=utc_now(),
    )
    session.add(catalog_set)
    session.flush()
    return catalog_set


def add_instance_line_for_set_part(
    session: Session,
    *,
    owned_set: OwnedSet,
    catalog_line: SetPartInventoryLine,
    quantity: int | None = None,
    quantity_missing: int = 0,
) -> OwnedSetInventoryLine:
    instance = _get_instance_line_for_set_part(session, owned_set.id, catalog_line.id)
    if instance is None:
        clone_instance_inventory(session, owned_set.id)
        instance = _get_instance_line_for_set_part(session, owned_set.id, catalog_line.id)
    assert instance is not None
    instance.quantity = quantity if quantity is not None else catalog_line.quantity
    instance.quantity_missing = quantity_missing
    session.flush()
    return instance


def _get_instance_line_for_set_part(
    session: Session,
    owned_set_id: int,
    catalog_line_id: int,
) -> OwnedSetInventoryLine | None:
    from sqlalchemy import select

    return session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == owned_set_id,
            OwnedSetInventoryLine.set_part_inventory_line_id == catalog_line_id,
        )
    )


def add_missing_item_for_set_line(
    session: Session,
    *,
    owned_set: OwnedSet,
    line: SetPartInventoryLine,
    quantity_missing: int = 1,
) -> MissingItem:
    instance = add_instance_line_for_set_part(
        session,
        owned_set=owned_set,
        catalog_line=line,
        quantity_missing=quantity_missing,
    )
    item = MissingItem(
        owned_set_id=owned_set.id,
        owned_set_inventory_line_id=instance.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(item)
    session.flush()
    return item


def add_part_alias(session: Session, part: Part, alias: str) -> PartAlias:
    row = PartAlias(part_id=part.id, alias=alias, source="rebrickable")
    session.add(row)
    session.flush()
    return row


def add_minifig_with_parts(
    session: Session,
    *,
    catalog_set: CatalogSet,
    minifig_num: str = "cop01",
) -> tuple[CatalogMinifig, SetMinifigInventoryLine, MinifigPartInventoryLine]:
    minifig = CatalogMinifig(
        minifig_num=minifig_num,
        name="Officer",
        image_url=None,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(minifig)
    session.flush()
    mf_line = SetMinifigInventoryLine(
        catalog_set_id=catalog_set.id,
        catalog_minifig_id=minifig.id,
        quantity=1,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(mf_line)
    session.flush()
    part = add_part(session, part_num="973")
    color = add_color(session, external_id=99, name="Yellow")
    bom_line = MinifigPartInventoryLine(
        catalog_minifig_id=minifig.id,
        part_id=part.id,
        color_id=color.id,
        quantity=1,
        image_url=None,
        source="rebrickable",
        fetched_at=utc_now(),
    )
    session.add(bom_line)
    session.flush()
    return minifig, mf_line, bom_line
