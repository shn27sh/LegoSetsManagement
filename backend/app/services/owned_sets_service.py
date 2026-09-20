"""List, read, mutate, duplicate, or delete user's physical set copies (`owned_sets`)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    Color,
    MinifigPartInventoryLine,
    MissingItem,
    OwnedSet,
    OwnedSetInventoryLine,
    Part,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
    Theme,
)
CSV_STUB_SOURCE = "csv_import"
USER_THEME_SOURCE = "user"
from app.schemas.owned_sets import (
    CatalogBlock,
    DuplicatePreviewResponse,
    InventoryBlock,
    MinifigInventoryBlock,
    MinifigPartLineDetail,
    OwnedSetDeleteResponse,
    OwnedSetDetailResponse,
    OwnedSetDuplicateResponse,
    OwnedSetListItem,
    OwnedSetListResponse,
    OwnedSetUpdateRequest,
    SetPartLineDetail,
)
from app.services.catalog_cleanup import delete_catalog_set_data
from app.services.catalog_state import (
    catalog_sync_state,
    load_element_image_urls,
    missing_image_url_for_part,
    resolve_catalog_image_url,
    resolve_catalog_minifig_image_url,
    resolve_line_image_url,
    resolve_part_image_url,
)
from app.services.instance_inventory import (
    clear_instance_inventory,
    clone_instance_inventory,
    count_lines_with_missing,
    ensure_instance_inventory,
)
from app.services.instance_labels import (
    copy_index_for_owned_set,
    copy_index_map,
    count_owned_instances,
    display_label,
    suggested_copy_label,
)
from app.services.part_color_catalog_service import load_element_ids_for_part_colors
from app.domain.lego_set_number import (
    LegoSetId,
    LegoSetNumberParseError,
    parse_user_set_number,
    to_rebrickable_set_num,
)
from app.utils.age import parse_age_value


class OwnedSetServiceError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aliases_for_part(part: Part) -> list[str]:
    return sorted(a.alias for a in part.aliases if a.alias != part.part_num)


def _missing_counts(session: Session, owned_set_ids: list[int]) -> dict[int, int]:
    return count_lines_with_missing(session, owned_set_ids)


def _to_list_item(
    owned_set: OwnedSet,
    catalog_set: CatalogSet,
    theme_name: str | None,
    missing_count: int,
    copy_index: int,
) -> OwnedSetListItem:
    return OwnedSetListItem(
        id=owned_set.id,
        set_num=catalog_set.set_number,
        name=catalog_set.name,
        year=catalog_set.year,
        theme_name=theme_name,
        image_url=resolve_catalog_image_url(catalog_set),
        catalog_sync_state=catalog_sync_state(catalog_set),
        investigated=owned_set.investigated,
        label=owned_set.label,
        display_label=display_label(owned_set.label, copy_index),
        copy_index=copy_index,
        age=owned_set.age,
        num_parts=catalog_set.num_parts,
        missing_count=missing_count,
    )


def _clear_instance_data_for_owned_set(session: Session, owned_set_id: int) -> None:
    clear_instance_inventory(session, owned_set_id)


def _apply_shared_age(
    session: Session,
    catalog_set_id: int,
    age: int | None,
) -> None:
    for owned in session.scalars(
        select(OwnedSet).where(OwnedSet.catalog_set_id == catalog_set_id)
    ).all():
        owned.age = age


def _find_or_create_theme_by_name(session: Session, theme_name: str) -> Theme:
    name = theme_name.strip()
    theme = session.scalar(
        select(Theme).where(func.lower(Theme.name) == name.lower())
    )
    if theme is not None:
        return theme

    min_user_external_id = session.scalar(
        select(func.min(Theme.external_id)).where(Theme.external_id < 0)
    )
    external_id = -1 if min_user_external_id is None else min_user_external_id - 1
    theme = Theme(
        external_id=external_id,
        name=name,
        source=USER_THEME_SOURCE,
        fetched_at=utc_now(),
    )
    session.add(theme)
    session.flush()
    return theme


def _count_catalog_sets_with_theme_name(session: Session, theme_name: str) -> int:
    name = theme_name.strip()
    if not name:
        return 0
    return int(
        session.scalar(
            select(func.count(CatalogSet.id))
            .join(Theme, CatalogSet.theme_id == Theme.id)
            .where(func.lower(Theme.name) == name.lower())
        )
        or 0
    )


def _apply_catalog_theme_name(
    session: Session,
    catalog_set: CatalogSet,
    theme_name: str,
    *,
    scope: str = "all",
) -> None:
    """Set or update theme on a catalog set (creates/links when theme_id was NULL)."""
    name = theme_name.strip()
    if not name:
        catalog_set.theme_id = None
        return

    if scope == "this_set" or catalog_set.theme is None:
        catalog_set.theme_id = _find_or_create_theme_by_name(session, name).id
        return

    existing = session.scalar(
        select(Theme).where(func.lower(Theme.name) == name.lower())
    )
    if existing is not None and catalog_set.theme_id != existing.id:
        source_theme_id = catalog_set.theme_id
        if source_theme_id is not None:
            session.execute(
                update(CatalogSet)
                .where(CatalogSet.theme_id == source_theme_id)
                .values(theme_id=existing.id)
            )
        catalog_set.theme_id = existing.id
        return

    if catalog_set.theme is not None:
        catalog_set.theme.name = name


def _relocate_to_lego_set(session: Session, owned_set: OwnedSet, lsid: LegoSetId) -> None:
    _clear_instance_data_for_owned_set(session, owned_set.id)

    existing = session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
    )
    rb_key = to_rebrickable_set_num(lsid)
    if existing is not None:
        owned_set.catalog_set_id = existing.id
        session.flush()
        clone_instance_inventory(session, owned_set.id)
    else:
        now = utc_now()
        stub = CatalogSet(
            set_number=lsid.number,
            set_variant=lsid.variant,
            name=None,
            year=None,
            theme_id=None,
            num_parts=None,
            image_url=None,
            source=CSV_STUB_SOURCE,
            source_ref=rb_key,
            fetched_at=now,
        )
        session.add(stub)
        session.flush()
        owned_set.catalog_set_id = stub.id
    session.flush()
    clone_instance_inventory(session, owned_set.id)


def list_owned_sets(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    investigated: bool | None = None,
    themes: list[str] | None = None,
    missing_only: bool = False,
    sort_by: str = "created",
    sort_dir: str = "asc",
) -> OwnedSetListResponse:
    theme_names = [theme for theme in themes or [] if theme]
    base = (
        select(OwnedSet, CatalogSet, Theme.name)
        .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .outerjoin(Theme, CatalogSet.theme_id == Theme.id)
    )
    if investigated is not None:
        base = base.where(OwnedSet.investigated == investigated)
    if theme_names:
        base = base.where(Theme.name.in_(theme_names))
    if missing_only:
        base = base.where(
            OwnedSet.id.in_(select(MissingItem.owned_set_id).distinct())
        )

    count_stmt = (
        select(func.count(OwnedSet.id))
        .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .outerjoin(Theme, CatalogSet.theme_id == Theme.id)
    )
    if investigated is not None:
        count_stmt = count_stmt.where(OwnedSet.investigated == investigated)
    if theme_names:
        count_stmt = count_stmt.where(Theme.name.in_(theme_names))
    if missing_only:
        count_stmt = count_stmt.where(
            OwnedSet.id.in_(select(MissingItem.owned_set_id).distinct())
        )
    total = session.scalar(count_stmt) or 0

    sort_columns = {
        "created": OwnedSet.id,
        "set_num": CatalogSet.set_number,
        "name": func.lower(func.coalesce(CatalogSet.name, "")),
        "theme": func.lower(func.coalesce(Theme.name, "")),
        "num_parts": func.coalesce(CatalogSet.num_parts, -1),
        "age": func.coalesce(OwnedSet.age, -1),
    }
    sort_column = sort_columns.get(sort_by, OwnedSet.id)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    rows = session.execute(
        base.order_by(order, OwnedSet.id).limit(limit).offset(offset)
    ).all()

    owned_ids = [row[0].id for row in rows]
    catalog_ids = list({row[1].id for row in rows})
    missing_map = _missing_counts(session, owned_ids)
    index_map = copy_index_map(session, catalog_ids)

    items = [
        _to_list_item(
            owned_set,
            catalog_set,
            theme_name,
            missing_map.get(owned_set.id, 0),
            index_map.get(catalog_set.id, {}).get(owned_set.id, 1),
        )
        for owned_set, catalog_set, theme_name in rows
    ]
    return OwnedSetListResponse(items=items, total=total)


def list_owned_set_theme_options(session: Session) -> list[str]:
    rows = session.scalars(
        select(Theme.name)
        .join(CatalogSet, CatalogSet.theme_id == Theme.id)
        .join(OwnedSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .where(Theme.name.is_not(None), func.trim(Theme.name) != "")
        .distinct()
        .order_by(func.lower(Theme.name))
    )
    return list(rows)


def get_owned_set_detail(
    session: Session,
    owned_set_id: int,
) -> OwnedSetDetailResponse | None:
    owned_set = session.scalar(
        select(OwnedSet)
        .where(OwnedSet.id == owned_set_id)
        .options(
            selectinload(OwnedSet.catalog_set).selectinload(CatalogSet.theme),
            selectinload(OwnedSet.missing_items),
        )
    )
    if owned_set is None:
        return None

    ensure_instance_inventory(session, owned_set_id)

    catalog_set = owned_set.catalog_set
    theme_name = catalog_set.theme.name if catalog_set.theme else None
    theme_shared_catalog_set_count = (
        _count_catalog_sets_with_theme_name(session, theme_name)
        if theme_name
        else 0
    )
    copy_idx = copy_index_for_owned_set(session, owned_set)

    instance_by_set_line: dict[int, OwnedSetInventoryLine] = {}
    instance_by_minifig_line: dict[int, OwnedSetInventoryLine] = {}
    for instance_line in session.scalars(
        select(OwnedSetInventoryLine)
        .where(OwnedSetInventoryLine.owned_set_id == owned_set_id)
        .options(selectinload(OwnedSetInventoryLine.missing_item))
    ).all():
        if instance_line.set_part_inventory_line_id is not None:
            instance_by_set_line[instance_line.set_part_inventory_line_id] = instance_line
        if instance_line.minifig_part_inventory_line_id is not None:
            instance_by_minifig_line[
                instance_line.minifig_part_inventory_line_id
            ] = instance_line

    set_part_catalog_lines = session.scalars(
        select(SetPartInventoryLine)
        .where(SetPartInventoryLine.catalog_set_id == catalog_set.id)
        .options(
            selectinload(SetPartInventoryLine.part).selectinload(Part.aliases),
            selectinload(SetPartInventoryLine.color),
        )
        .order_by(SetPartInventoryLine.id)
    ).all()

    set_part_keys = {(line.part_id, line.color_id) for line in set_part_catalog_lines}
    element_id_map = load_element_ids_for_part_colors(session, set_part_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)

    set_parts: list[SetPartLineDetail] = []
    for line in set_part_catalog_lines:
        part = line.part
        color = line.color
        instance_line = instance_by_set_line.get(line.id)
        if instance_line is None:
            continue
        missing = instance_line.missing_item
        line_element_ids = element_id_map.get((line.part_id, line.color_id), [])
        resolved_image_url = resolve_line_image_url(
            element_ids=line_element_ids,
            part=part,
            element_url_by_id=element_url_by_id,
        )
        set_parts.append(
            SetPartLineDetail(
                instance_line_id=instance_line.id,
                catalog_line_id=line.id,
                part_id=part.id,
                part_num=part.part_num,
                part_name=part.name,
                color_id=color.external_id,
                color_name=color.name,
                quantity=instance_line.quantity,
                element_ids=line_element_ids,
                aliases=_aliases_for_part(part),
                image_url=resolved_image_url,
                part_image_url=resolve_part_image_url(part),
                part_image_user_removed=part.part_image_user_removed,
                missing_quantity=instance_line.quantity_missing,
                missing_item_id=missing.id if missing else None,
                missing_image_url=missing_image_url_for_part(
                    part,
                    quantity_missing=instance_line.quantity_missing,
                    element_ids=line_element_ids,
                    element_url_by_id=element_url_by_id,
                ),
            )
        )

    minifig_rows = session.execute(
        select(SetMinifigInventoryLine, CatalogMinifig)
        .join(
            CatalogMinifig,
            SetMinifigInventoryLine.catalog_minifig_id == CatalogMinifig.id,
        )
        .where(SetMinifigInventoryLine.catalog_set_id == catalog_set.id)
        .order_by(SetMinifigInventoryLine.id)
    ).all()

    minifigs: list[MinifigInventoryBlock] = []
    for mf_line, catalog_minifig in minifig_rows:
        part_rows = session.execute(
            select(MinifigPartInventoryLine, Part, Color)
            .join(Part, MinifigPartInventoryLine.part_id == Part.id)
            .join(Color, MinifigPartInventoryLine.color_id == Color.id)
            .where(MinifigPartInventoryLine.catalog_minifig_id == catalog_minifig.id)
            .order_by(MinifigPartInventoryLine.id)
        ).all()

        minifig_keys = {(part_line.part_id, part_line.color_id) for part_line, _, _ in part_rows}
        minifig_element_map = load_element_ids_for_part_colors(session, minifig_keys)
        minifig_element_ids: set[str] = set()
        for ids in minifig_element_map.values():
            minifig_element_ids.update(ids)
        element_url_by_id.update(
            load_element_image_urls(session, minifig_element_ids - set(element_url_by_id))
        )

        parts: list[MinifigPartLineDetail] = []
        for part_line, part, color in part_rows:
            instance_line = instance_by_minifig_line.get(part_line.id)
            if instance_line is None:
                continue
            missing = instance_line.missing_item
            line_element_ids = minifig_element_map.get(
                (part_line.part_id, part_line.color_id), []
            )
            resolved_image_url = resolve_line_image_url(
                element_ids=line_element_ids,
                part=part,
                element_url_by_id=element_url_by_id,
            )
            parts.append(
                MinifigPartLineDetail(
                    instance_line_id=instance_line.id,
                    catalog_line_id=part_line.id,
                    part_id=part.id,
                    part_num=part.part_num,
                    part_name=part.name,
                    color_id=color.external_id,
                    color_name=color.name,
                    quantity=instance_line.quantity,
                    element_ids=line_element_ids,
                    image_url=resolved_image_url,
                    part_image_url=resolve_part_image_url(part),
                    part_image_user_removed=part.part_image_user_removed,
                    missing_quantity=instance_line.quantity_missing,
                    missing_item_id=missing.id if missing else None,
                    missing_image_url=missing_image_url_for_part(
                        part,
                        quantity_missing=instance_line.quantity_missing,
                        element_ids=line_element_ids,
                        element_url_by_id=element_url_by_id,
                    ),
                )
            )

        minifigs.append(
            MinifigInventoryBlock(
                line_id=mf_line.id,
                catalog_minifig_id=catalog_minifig.id,
                minifig_num=catalog_minifig.minifig_num,
                name=catalog_minifig.name,
                image_url=resolve_catalog_minifig_image_url(catalog_minifig),
                quantity=mf_line.quantity,
                parts=parts,
            )
        )

    return OwnedSetDetailResponse(
        id=owned_set.id,
        investigated=owned_set.investigated,
        label=owned_set.label,
        display_label=display_label(owned_set.label, copy_idx),
        copy_index=copy_idx,
        age=owned_set.age,
        notes=owned_set.notes,
        catalog=CatalogBlock(
            catalog_set_id=catalog_set.id,
            set_num=catalog_set.set_number,
            name=catalog_set.name,
            year=catalog_set.year,
            theme_name=theme_name,
            theme_shared_catalog_set_count=theme_shared_catalog_set_count,
            image_url=resolve_catalog_image_url(catalog_set),
            num_parts=catalog_set.num_parts,
        ),
        inventory=InventoryBlock(set_parts=set_parts, minifigs=minifigs),
    )


def update_owned_set(
    session: Session,
    owned_set_id: int,
    body: OwnedSetUpdateRequest,
) -> OwnedSetListItem | None:
    owned_set = session.scalar(
        select(OwnedSet)
        .where(OwnedSet.id == owned_set_id)
        .options(selectinload(OwnedSet.catalog_set).selectinload(CatalogSet.theme))
    )
    if owned_set is None:
        return None

    catalog_set = owned_set.catalog_set

    if body.investigated is not None:
        owned_set.investigated = body.investigated
    if body.label is not None:
        owned_set.label = body.label.strip() or None
    if body.notes is not None:
        owned_set.notes = body.notes.strip() or None

    if "age" in body.model_fields_set:
        parsed_age = parse_age_value(body.age) if body.age is not None else None
        _apply_shared_age(session, catalog_set.id, parsed_age)

    if body.catalog_name is not None:
        catalog_set.name = body.catalog_name.strip() or None
    if body.catalog_num_parts is not None:
        catalog_set.num_parts = body.catalog_num_parts
    if body.catalog_year is not None:
        catalog_set.year = body.catalog_year
    if body.catalog_theme_name is not None:
        _apply_catalog_theme_name(
            session,
            catalog_set,
            body.catalog_theme_name,
            scope=body.catalog_theme_scope,
        )

    if body.set_num is not None:
        try:
            lsid = parse_user_set_number(str(body.set_num))
        except LegoSetNumberParseError as exc:
            raise OwnedSetServiceError(str(exc)) from exc
        if (catalog_set.set_number, catalog_set.set_variant) != (
            lsid.number,
            lsid.variant,
        ):
            _relocate_to_lego_set(session, owned_set, lsid)
        session.refresh(owned_set, attribute_names=["catalog_set"])
        catalog_set = owned_set.catalog_set

    session.flush()
    if body.catalog_theme_name is not None:
        session.refresh(catalog_set, attribute_names=["theme"])
    elif catalog_set.theme_id is not None and catalog_set.theme is None:
        session.refresh(catalog_set, attribute_names=["theme"])

    theme_name = catalog_set.theme.name if catalog_set.theme else None
    missing_count = _missing_counts(session, [owned_set_id]).get(owned_set_id, 0)
    copy_idx = copy_index_for_owned_set(session, owned_set)
    return _to_list_item(owned_set, catalog_set, theme_name, int(missing_count), copy_idx)


def get_duplicate_preview(
    session: Session,
    source_id: int,
) -> DuplicatePreviewResponse | None:
    source = session.scalar(
        select(OwnedSet)
        .where(OwnedSet.id == source_id)
        .options(selectinload(OwnedSet.catalog_set))
    )
    if source is None:
        return None

    catalog_set = source.catalog_set
    count = count_owned_instances(session, catalog_set.id)
    return DuplicatePreviewResponse(
        source_owned_set_id=source_id,
        set_num=catalog_set.set_number,
        set_name=catalog_set.name,
        existing_copy_count=count,
        suggested_label=suggested_copy_label(count),
    )


def duplicate_owned_set(
    session: Session,
    source_id: int,
    *,
    label: str | None = None,
) -> OwnedSetDuplicateResponse | None:
    source = session.scalar(
        select(OwnedSet)
        .where(OwnedSet.id == source_id)
        .options(selectinload(OwnedSet.catalog_set).selectinload(CatalogSet.theme))
    )
    if source is None:
        return None

    count = count_owned_instances(session, source.catalog_set_id)
    resolved_label = (label or "").strip() or suggested_copy_label(count)

    new_owned = OwnedSet(
        catalog_set_id=source.catalog_set_id,
        investigated=False,
        label=resolved_label,
        age=source.age,
        notes=None,
        created_at=utc_now(),
    )
    session.add(new_owned)
    session.flush()
    clone_instance_inventory(session, new_owned.id)

    catalog_set = source.catalog_set
    theme_name = catalog_set.theme.name if catalog_set.theme else None
    copy_idx = copy_index_for_owned_set(session, new_owned)
    item = _to_list_item(new_owned, catalog_set, theme_name, 0, copy_idx)
    return OwnedSetDuplicateResponse(
        **item.model_dump(),
        duplicated_from_owned_set_id=source_id,
    )


def delete_owned_set(
    session: Session,
    owned_set_id: int,
) -> OwnedSetDeleteResponse | None:
    owned_set = session.scalar(
        select(OwnedSet)
        .where(OwnedSet.id == owned_set_id)
        .options(selectinload(OwnedSet.missing_items))
    )
    if owned_set is None:
        return None

    catalog_set_id = owned_set.catalog_set_id
    _clear_instance_data_for_owned_set(session, owned_set_id)
    session.delete(owned_set)
    session.flush()

    remaining = count_owned_instances(session, catalog_set_id)
    if remaining == 0:
        delete_catalog_set_data(session, catalog_set_id)
        session.flush()

    return OwnedSetDeleteResponse(deleted=True, id=owned_set_id)
