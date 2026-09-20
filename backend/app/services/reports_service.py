"""Collection reporting aggregates."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CatalogSet,
    MinifigPartInventoryLine,
    OwnedSet,
    OwnedSetInventoryLine,
    SetPartInventoryLine,
    Theme,
)
from app.schemas.reports import (
    IncompleteCatalogReportItem,
    IncompleteCatalogReportResponse,
    IncompleteSetMissingLine,
    IncompleteSetReportItem,
    IncompleteSetsReportResponse,
    CatalogGapSetOccurrence,
    MissingPartNeededSet,
    MissingPartReportItem,
    MissingPartsReportResponse,
    ReportsSummaryResponse,
)
from app.services.catalog_gaps_service import aggregate_catalog_gaps
from app.services.catalog_state import load_element_image_urls, resolve_line_image_url
from app.services.instance_inventory import count_lines_with_missing
from app.services.instance_labels import copy_index_map, display_label
from app.services.part_color_catalog_service import load_element_ids_for_part_colors


def get_summary(session: Session) -> ReportsSummaryResponse:
    total_sets = int(session.scalar(select(func.count()).select_from(OwnedSet)) or 0)

    investigated_sets = int(
        session.scalar(
            select(func.count())
            .select_from(OwnedSet)
            .where(OwnedSet.investigated.is_(True))
        )
        or 0
    )

    incomplete_owned_set_ids = (
        select(OwnedSetInventoryLine.owned_set_id)
        .where(OwnedSetInventoryLine.quantity_missing > 0)
        .distinct()
    )
    complete_sets = int(
        session.scalar(
            select(func.count())
            .select_from(OwnedSet)
            .where(
                OwnedSet.investigated.is_(True),
                OwnedSet.id.not_in(incomplete_owned_set_ids),
            )
        )
        or 0
    )

    total_parts, missing_parts = session.execute(
        select(
            func.coalesce(func.sum(OwnedSetInventoryLine.quantity), 0),
            func.coalesce(func.sum(OwnedSetInventoryLine.quantity_missing), 0),
        )
    ).one()

    return ReportsSummaryResponse(
        total_sets=total_sets,
        investigated_sets=investigated_sets,
        complete_sets=complete_sets,
        total_parts=int(total_parts),
        missing_parts=int(missing_parts),
    )


def _incomplete_owned_set_ids_subquery():
    return (
        select(OwnedSetInventoryLine.owned_set_id)
        .where(OwnedSetInventoryLine.quantity_missing > 0)
        .distinct()
    )


def _element_ids_for_catalog_line(
    session: Session,
    line: SetPartInventoryLine | MinifigPartInventoryLine,
    *,
    element_id_map: dict[tuple[int, int], list[str]] | None = None,
) -> list[str]:
    if element_id_map is not None:
        return list(element_id_map.get((line.part_id, line.color_id), []))
    from app.services.part_color_catalog_service import element_ids_for_part_color

    return element_ids_for_part_color(session, line.part_id, line.color_id)


def _sort_key_color_then_element_id(line: IncompleteSetMissingLine) -> tuple[str, int, str]:
    primary_element = line.element_ids[0] if line.element_ids else ""
    return (
        (line.color_name or "").casefold(),
        line.color_id,
        primary_element,
    )


def _element_ids_for_instance_line(
    session: Session,
    instance_line: OwnedSetInventoryLine,
    *,
    element_id_map: dict[tuple[int, int], list[str]] | None = None,
) -> list[str]:
    if instance_line.set_part_inventory_line is not None:
        return _element_ids_for_catalog_line(
            session,
            instance_line.set_part_inventory_line,
            element_id_map=element_id_map,
        )
    if instance_line.minifig_part_inventory_line is not None:
        return _element_ids_for_catalog_line(
            session,
            instance_line.minifig_part_inventory_line,
            element_id_map=element_id_map,
        )
    return []


def _missing_line_from_instance(
    session: Session,
    instance_line: OwnedSetInventoryLine,
    *,
    element_url_by_id: dict[str, str],
    element_id_map: dict[tuple[int, int], list[str]],
) -> IncompleteSetMissingLine | None:
    if instance_line.quantity_missing <= 0:
        return None

    if instance_line.set_part_inventory_line is not None:
        catalog_line = instance_line.set_part_inventory_line
        part = catalog_line.part
        color = catalog_line.color
    elif instance_line.minifig_part_inventory_line is not None:
        catalog_line = instance_line.minifig_part_inventory_line
        part = catalog_line.part
        color = catalog_line.color
    else:
        return None

    element_ids = _element_ids_for_catalog_line(
        session, catalog_line, element_id_map=element_id_map
    )
    image_url = resolve_line_image_url(
        element_ids=element_ids,
        part=part,
        element_url_by_id=element_url_by_id,
    )

    return IncompleteSetMissingLine(
        part_id=part.id,
        part_num=part.part_num,
        part_name=part.name,
        color_id=color.external_id,
        color_name=color.name,
        quantity_missing=instance_line.quantity_missing,
        element_ids=element_ids,
        part_image_url=image_url,
    )


def list_incomplete_sets(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> IncompleteSetsReportResponse:
    incomplete_ids = _incomplete_owned_set_ids_subquery()

    total = int(
        session.scalar(
            select(func.count()).select_from(OwnedSet).where(OwnedSet.id.in_(incomplete_ids))
        )
        or 0
    )

    rows = session.execute(
        select(OwnedSet, CatalogSet, Theme.name)
        .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .outerjoin(Theme, CatalogSet.theme_id == Theme.id)
        .where(OwnedSet.id.in_(incomplete_ids))
        .order_by(CatalogSet.set_number.asc(), OwnedSet.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()

    owned_ids = [owned_set.id for owned_set, _, _ in rows]
    if not owned_ids:
        return IncompleteSetsReportResponse(items=[], total=total)

    catalog_ids = list({catalog_set.id for _, catalog_set, _ in rows})
    index_map = copy_index_map(session, catalog_ids)
    missing_line_counts = count_lines_with_missing(session, owned_ids)

    instance_lines = session.scalars(
        select(OwnedSetInventoryLine)
        .where(
            OwnedSetInventoryLine.owned_set_id.in_(owned_ids),
            OwnedSetInventoryLine.quantity_missing > 0,
        )
        .options(
            selectinload(OwnedSetInventoryLine.set_part_inventory_line).selectinload(
                SetPartInventoryLine.part
            ),
            selectinload(OwnedSetInventoryLine.set_part_inventory_line).selectinload(
                SetPartInventoryLine.color
            ),
            selectinload(OwnedSetInventoryLine.minifig_part_inventory_line).selectinload(
                MinifigPartInventoryLine.part
            ),
            selectinload(OwnedSetInventoryLine.minifig_part_inventory_line).selectinload(
                MinifigPartInventoryLine.color
            ),
        )
    ).all()

    part_color_keys: set[tuple[int, int]] = set()
    for instance_line in instance_lines:
        if instance_line.set_part_inventory_line is not None:
            line = instance_line.set_part_inventory_line
            part_color_keys.add((line.part_id, line.color_id))
        elif instance_line.minifig_part_inventory_line is not None:
            line = instance_line.minifig_part_inventory_line
            part_color_keys.add((line.part_id, line.color_id))
    element_id_map = load_element_ids_for_part_colors(session, part_color_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)

    lines_by_owned_set: dict[int, list[IncompleteSetMissingLine]] = defaultdict(list)
    missing_parts_totals: dict[int, int] = defaultdict(int)
    for instance_line in instance_lines:
        missing_line = _missing_line_from_instance(
            session,
            instance_line,
            element_url_by_id=element_url_by_id,
            element_id_map=element_id_map,
        )
        if missing_line is None:
            continue
        lines_by_owned_set[instance_line.owned_set_id].append(missing_line)
        missing_parts_totals[instance_line.owned_set_id] += instance_line.quantity_missing

    items: list[IncompleteSetReportItem] = []
    for owned_set, catalog_set, _theme_name in rows:
        copy_idx = index_map.get(catalog_set.id, {}).get(owned_set.id, 1)
        missing_lines = sorted(
            lines_by_owned_set.get(owned_set.id, []),
            key=_sort_key_color_then_element_id,
        )
        items.append(
            IncompleteSetReportItem(
                id=owned_set.id,
                set_num=catalog_set.set_number,
                name=catalog_set.name,
                display_label=display_label(owned_set.label, copy_idx),
                investigated=owned_set.investigated,
                missing_line_count=missing_line_counts.get(owned_set.id, 0),
                missing_parts_total=missing_parts_totals.get(owned_set.id, 0),
                missing_lines=missing_lines,
            )
        )

    return IncompleteSetsReportResponse(items=items, total=total)


def _scope_owned_set_ids_with_missing(
    session: Session,
    owned_set_ids: list[int] | None,
) -> list[int]:
    incomplete_ids = _incomplete_owned_set_ids_subquery()
    if not owned_set_ids:
        return list(
            session.scalars(select(OwnedSet.id).where(OwnedSet.id.in_(incomplete_ids))).all()
        )
    return list(
        session.scalars(
            select(OwnedSet.id).where(
                OwnedSet.id.in_(owned_set_ids),
                OwnedSet.id.in_(incomplete_ids),
            )
        ).all()
    )


def _owned_set_metadata(
    session: Session,
    owned_set_ids: list[int],
) -> dict[int, tuple[int, str | None, str]]:
    if not owned_set_ids:
        return {}

    rows = session.execute(
        select(OwnedSet, CatalogSet)
        .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .where(OwnedSet.id.in_(owned_set_ids))
    ).all()
    catalog_ids = list({catalog_set.id for _, catalog_set in rows})
    index_map = copy_index_map(session, catalog_ids)
    return {
        owned_set.id: (
            catalog_set.set_number,
            catalog_set.name,
            display_label(
                owned_set.label,
                index_map.get(catalog_set.id, {}).get(owned_set.id, 1),
            ),
        )
        for owned_set, catalog_set in rows
    }


def list_missing_parts(
    session: Session,
    *,
    owned_set_ids: list[int] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MissingPartsReportResponse:
    scope_ids = _scope_owned_set_ids_with_missing(session, owned_set_ids)
    if not scope_ids:
        return MissingPartsReportResponse(items=[], total=0)

    instance_lines = session.scalars(
        select(OwnedSetInventoryLine)
        .where(
            OwnedSetInventoryLine.owned_set_id.in_(scope_ids),
            OwnedSetInventoryLine.quantity_missing > 0,
        )
        .options(
            selectinload(OwnedSetInventoryLine.set_part_inventory_line).selectinload(
                SetPartInventoryLine.part
            ),
            selectinload(OwnedSetInventoryLine.set_part_inventory_line).selectinload(
                SetPartInventoryLine.color
            ),
            selectinload(OwnedSetInventoryLine.minifig_part_inventory_line).selectinload(
                MinifigPartInventoryLine.part
            ),
            selectinload(OwnedSetInventoryLine.minifig_part_inventory_line).selectinload(
                MinifigPartInventoryLine.color
            ),
        )
    ).all()

    owned_set_meta = _owned_set_metadata(session, scope_ids)

    part_color_keys: set[tuple[int, int]] = set()
    for instance_line in instance_lines:
        if instance_line.set_part_inventory_line is not None:
            line = instance_line.set_part_inventory_line
            part_color_keys.add((line.part_id, line.color_id))
        elif instance_line.minifig_part_inventory_line is not None:
            line = instance_line.minifig_part_inventory_line
            part_color_keys.add((line.part_id, line.color_id))
    element_id_map = load_element_ids_for_part_colors(session, part_color_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)

    aggregated: dict[tuple[int, int], dict] = {}
    for instance_line in instance_lines:
        missing_line = _missing_line_from_instance(
            session,
            instance_line,
            element_url_by_id=element_url_by_id,
            element_id_map=element_id_map,
        )
        if missing_line is None:
            continue

        if instance_line.set_part_inventory_line is not None:
            color_db_id = instance_line.set_part_inventory_line.color_id
        else:
            assert instance_line.minifig_part_inventory_line is not None
            color_db_id = instance_line.minifig_part_inventory_line.color_id

        key = (missing_line.part_id, color_db_id)
        bucket = aggregated.get(key)
        if bucket is None:
            bucket = {
                "missing_line": missing_line,
                "total": 0,
                "needed_by_set": defaultdict(int),
                "element_ids": set(missing_line.element_ids),
            }
            aggregated[key] = bucket

        bucket["total"] += instance_line.quantity_missing
        bucket["needed_by_set"][instance_line.owned_set_id] += instance_line.quantity_missing
        bucket["element_ids"].update(missing_line.element_ids)

    sorted_buckets = sorted(
        aggregated.values(),
        key=lambda bucket: _sort_key_color_then_element_id(bucket["missing_line"]),
    )
    total = len(sorted_buckets)
    page_buckets = sorted_buckets[offset : offset + limit]

    items: list[MissingPartReportItem] = []
    for bucket in page_buckets:
        missing_line: IncompleteSetMissingLine = bucket["missing_line"]
        needed_sets = sorted(
            [
                MissingPartNeededSet(
                    owned_set_id=owned_set_id,
                    set_num=owned_set_meta[owned_set_id][0],
                    set_name=owned_set_meta[owned_set_id][1],
                    display_label=owned_set_meta[owned_set_id][2],
                    quantity_missing=quantity,
                )
                for owned_set_id, quantity in bucket["needed_by_set"].items()
            ],
            key=lambda row: (row.set_num, row.display_label),
        )
        items.append(
            MissingPartReportItem(
                part_id=missing_line.part_id,
                part_num=missing_line.part_num,
                part_name=missing_line.part_name,
                color_id=missing_line.color_id,
                color_name=missing_line.color_name,
                quantity_missing_total=bucket["total"],
                element_ids=sorted(bucket["element_ids"]),
                part_image_url=missing_line.part_image_url,
                needed_sets=needed_sets,
            )
        )

    return MissingPartsReportResponse(items=items, total=total)


def list_incomplete_catalog_parts(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> IncompleteCatalogReportResponse:
    aggregated = aggregate_catalog_gaps(session)
    sorted_buckets = sorted(
        aggregated.values(),
        key=lambda bucket: (
            (bucket["color"].name or "").casefold(),
            bucket["color"].external_id,
            bucket["part"].part_num.casefold(),
        ),
    )
    total = len(sorted_buckets)
    page_buckets = sorted_buckets[offset : offset + limit]

    items: list[IncompleteCatalogReportItem] = []
    for bucket in page_buckets:
        part = bucket["part"]
        color = bucket["color"]
        items.append(
            IncompleteCatalogReportItem(
                part_id=part.id,
                part_num=part.part_num,
                part_name=part.name,
                color_id=color.external_id,
                color_name=color.name,
                element_ids=sorted(bucket["element_ids"]),
                part_image_url=bucket["part_image_url"],
                missing_element_id=bucket["missing_element_id"],
                missing_image=bucket["missing_image"],
                sets=[
                    CatalogGapSetOccurrence(**row) for row in bucket["sets"]
                ],
            )
        )

    return IncompleteCatalogReportResponse(items=items, total=total)
