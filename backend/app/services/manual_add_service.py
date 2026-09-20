"""Create a new physical set copy manually (new shared catalog or additional copy)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CatalogSet, Color, OwnedSet, Part, SetPartInventoryLine, Theme
from app.domain.lego_set_number import (
    LegoSetId,
    LegoSetNumberParseError,
    parse_user_set_number,
    to_rebrickable_set_num,
)
from app.schemas.manual_add import (
    AddPreviewPartLine,
    ManualAddCatalogInput,
    ManualAddPartInput,
    OwnedSetAddPreviewResponse,
    OwnedSetCreateRequest,
    OwnedSetCreateResponse,
)
from app.services.catalog_state import resolve_catalog_image_url
from app.services.instance_inventory import clone_instance_inventory
from app.services.inventory_parts_service import upsert_set_part_catalog_line
from app.services.instance_labels import (
    copy_index_for_owned_set,
    count_owned_instances,
    display_label,
    suggested_copy_label,
)
from app.services.owned_sets_service import (
    OwnedSetServiceError,
    USER_THEME_SOURCE,
    _apply_catalog_theme_name,
    _apply_shared_age,
    _to_list_item,
    utc_now,
)

MANUAL_SOURCE = "user"


def normalize_set_num(set_num: int | str) -> LegoSetId:
    """Parse user/CSV input into a catalog key (default Rebrickable variant ``-1`` when omitted)."""
    if not set_num or not str(set_num).strip():
        raise OwnedSetServiceError("Set number is required")
    try:
        return parse_user_set_number(str(set_num))
    except LegoSetNumberParseError as exc:
        raise OwnedSetServiceError(str(exc)) from exc


def _shared_age_for_catalog(session: Session, catalog_set_id: int) -> int | None:
    return session.scalar(
        select(OwnedSet.age)
        .where(OwnedSet.catalog_set_id == catalog_set_id, OwnedSet.age.is_not(None))
        .limit(1)
    )


def _catalog_part_lines(session: Session, catalog_set_id: int) -> list[AddPreviewPartLine]:
    rows = session.execute(
        select(SetPartInventoryLine, Part, Color)
        .join(Part, SetPartInventoryLine.part_id == Part.id)
        .join(Color, SetPartInventoryLine.color_id == Color.id)
        .where(SetPartInventoryLine.catalog_set_id == catalog_set_id)
        .order_by(Part.part_num, Color.name, SetPartInventoryLine.id)
    ).all()
    return [
        AddPreviewPartLine(
            part_num=part.part_num,
            part_name=part.name,
            color_name=color.name,
            quantity=line.quantity,
        )
        for line, part, color in rows
    ]


def get_add_preview(session: Session, set_num: str) -> OwnedSetAddPreviewResponse:
    lsid = normalize_set_num(set_num)
    catalog = session.scalar(
        select(CatalogSet)
        .where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
        .options(selectinload(CatalogSet.theme))
    )
    if catalog is None:
        return OwnedSetAddPreviewResponse(
            set_num=lsid.number,
            catalog_exists=False,
            set_name=None,
            existing_copy_count=0,
            suggested_label=suggested_copy_label(0),
        )

    count = count_owned_instances(session, catalog.id)
    theme_name = catalog.theme.name if catalog.theme else None
    return OwnedSetAddPreviewResponse(
        set_num=lsid.number,
        catalog_exists=True,
        set_name=catalog.name,
        existing_copy_count=count,
        suggested_label=suggested_copy_label(count),
        theme_name=theme_name,
        year=catalog.year,
        num_parts=catalog.num_parts,
        age=_shared_age_for_catalog(session, catalog.id),
        image_url=resolve_catalog_image_url(catalog),
        set_parts=_catalog_part_lines(session, catalog.id),
    )


def _apply_catalog_metadata(
    session: Session,
    catalog_set: CatalogSet,
    catalog: ManualAddCatalogInput | None,
) -> None:
    if catalog is None:
        return
    if catalog.name is not None:
        catalog_set.name = catalog.name.strip() or None
    if catalog.year is not None:
        catalog_set.year = catalog.year
    if catalog.num_parts is not None:
        catalog_set.num_parts = catalog.num_parts
    if catalog.theme_name is not None:
        _apply_catalog_theme_name(session, catalog_set, catalog.theme_name)


def create_owned_set_manual(
    session: Session,
    body: OwnedSetCreateRequest,
) -> OwnedSetCreateResponse:
    lsid = normalize_set_num(body.set_num)
    rb_key = to_rebrickable_set_num(lsid)
    catalog = session.scalar(
        select(CatalogSet)
        .where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
        .options(selectinload(CatalogSet.theme))
    )
    now = utc_now()
    catalog_created = False

    if catalog is not None:
        if body.catalog is not None or body.parts:
            raise OwnedSetServiceError(
                "Set number already exists; omit catalog and parts to add another copy",
            )
    else:
        catalog = CatalogSet(
            set_number=lsid.number,
            set_variant=lsid.variant,
            name=None,
            year=None,
            theme_id=None,
            num_parts=None,
            image_url=None,
            source=MANUAL_SOURCE,
            source_ref=rb_key,
            fetched_at=now,
        )
        session.add(catalog)
        session.flush()
        catalog_created = True
        _apply_catalog_metadata(session, catalog, body.catalog)
        if body.parts:
            for part_line in body.parts:
                upsert_set_part_catalog_line(
                    session,
                    catalog.id,
                    part_line,
                    fetched_at=now,
                )

    resolved_label = (body.label or "").strip() or suggested_copy_label(
        count_owned_instances(session, catalog.id)
    )
    owned = OwnedSet(
        catalog_set_id=catalog.id,
        investigated=False,
        label=resolved_label or None,
        age=body.age,
        notes=None,
        created_at=now,
    )
    session.add(owned)
    session.flush()

    if body.age is not None:
        _apply_shared_age(session, catalog.id, body.age)

    clone_instance_inventory(session, owned.id)
    session.refresh(catalog, attribute_names=["theme"])
    theme_name = catalog.theme.name if catalog.theme else None
    copy_idx = copy_index_for_owned_set(session, owned)
    item = _to_list_item(owned, catalog, theme_name, 0, copy_idx)
    return OwnedSetCreateResponse(catalog_created=catalog_created, **item.model_dump())
