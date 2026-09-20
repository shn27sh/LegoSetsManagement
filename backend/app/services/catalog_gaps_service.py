"""Detect and repair catalog lines missing Element IDs or display images."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CatalogSet,
    Color,
    MinifigPartInventoryLine,
    OwnedSet,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
)
from app.domain.lego_set_number import LegoSetId, to_rebrickable_set_num
from app.services.catalog_state import load_element_image_urls, resolve_line_image_url
from app.services.part_alias_service import part_equivalence_class_ids
from app.services.part_color_catalog_service import (
    element_ids_for_part_color,
    load_element_ids_for_part_colors,
)

CatalogLineKind = Literal["set", "minifig"]
CatalogLineRef = tuple[CatalogLineKind, int]


def _owned_catalog_set_ids(session: Session) -> list[int]:
    return list(
        session.scalars(
            select(CatalogSet.id).join(OwnedSet).distinct().order_by(CatalogSet.id)
        ).all()
    )


def _catalog_set_part_lines(
    session: Session,
    catalog_set_id: int,
) -> list[SetPartInventoryLine]:
    return session.scalars(
        select(SetPartInventoryLine)
        .where(SetPartInventoryLine.catalog_set_id == catalog_set_id)
        .options(
            selectinload(SetPartInventoryLine.part),
            selectinload(SetPartInventoryLine.color),
        )
    ).all()


def _catalog_minifig_part_lines(
    session: Session,
    catalog_set_id: int,
) -> list[MinifigPartInventoryLine]:
    return session.scalars(
        select(MinifigPartInventoryLine)
        .join(
            SetMinifigInventoryLine,
            SetMinifigInventoryLine.catalog_minifig_id
            == MinifigPartInventoryLine.catalog_minifig_id,
        )
        .where(SetMinifigInventoryLine.catalog_set_id == catalog_set_id)
        .options(
            selectinload(MinifigPartInventoryLine.part),
            selectinload(MinifigPartInventoryLine.color),
        )
    ).all()


def _element_ids_for_line(
    session: Session,
    line: SetPartInventoryLine | MinifigPartInventoryLine,
) -> list[str]:
    return element_ids_for_part_color(session, line.part_id, line.color_id)


def _line_gap_flags(
    session: Session,
    line: SetPartInventoryLine | MinifigPartInventoryLine,
    *,
    element_url_by_id: dict[str, str],
    element_ids: list[str] | None = None,
) -> tuple[bool, bool]:
    ids = (
        element_ids
        if element_ids is not None
        else _element_ids_for_line(session, line)
    )
    missing_element_id = len(ids) == 0
    image_url = resolve_line_image_url(
        element_ids=ids,
        part=line.part,
        element_url_by_id=element_url_by_id,
    )
    missing_image = image_url is None
    return missing_element_id, missing_image


def catalog_line_has_gap(
    session: Session,
    line: SetPartInventoryLine | MinifigPartInventoryLine,
    *,
    element_url_by_id: dict[str, str],
    element_ids: list[str] | None = None,
) -> bool:
    missing_element_id, missing_image = _line_gap_flags(
        session,
        line,
        element_url_by_id=element_url_by_id,
        element_ids=element_ids,
    )
    return missing_element_id or missing_image


def catalog_set_has_catalog_gap(session: Session, catalog_set_id: int) -> bool:
    lines = [
        *_catalog_set_part_lines(session, catalog_set_id),
        *_catalog_minifig_part_lines(session, catalog_set_id),
    ]
    if not lines:
        return False
    part_color_keys = {(line.part_id, line.color_id) for line in lines}
    element_id_map = load_element_ids_for_part_colors(session, part_color_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)
    return any(
        catalog_line_has_gap(
            session,
            line,
            element_url_by_id=element_url_by_id,
            element_ids=element_id_map.get((line.part_id, line.color_id), []),
        )
        for line in lines
    )


def snapshot_lines_without_element_id(
    session: Session,
    catalog_set_id: int,
) -> set[CatalogLineRef]:
    refs: set[CatalogLineRef] = set()
    for line in _catalog_set_part_lines(session, catalog_set_id):
        if not element_ids_for_part_color(session, line.part_id, line.color_id):
            refs.add(("set", line.id))
    for line in _catalog_minifig_part_lines(session, catalog_set_id):
        if not element_ids_for_part_color(session, line.part_id, line.color_id):
            refs.add(("minifig", line.id))
    return refs


def _color_db_id_for_external(session: Session, color_external_id: int) -> int | None:
    return session.scalar(
        select(Color.id).where(Color.external_id == color_external_id)
    )


def _catalog_set_ids_for_part_color(
    session: Session,
    part_id: int,
    color_external_id: int,
) -> set[int]:
    color_db_id = _color_db_id_for_external(session, color_external_id)
    if color_db_id is None:
        return set()

    class_ids = part_equivalence_class_ids(session, part_id)
    catalog_ids: set[int] = set()
    for catalog_id in session.scalars(
        select(SetPartInventoryLine.catalog_set_id).where(
            SetPartInventoryLine.part_id.in_(class_ids),
            SetPartInventoryLine.color_id == color_db_id,
        )
    ).all():
        catalog_ids.add(catalog_id)
    for catalog_id in session.scalars(
        select(SetMinifigInventoryLine.catalog_set_id)
        .join(
            MinifigPartInventoryLine,
            MinifigPartInventoryLine.catalog_minifig_id
            == SetMinifigInventoryLine.catalog_minifig_id,
        )
        .where(
            MinifigPartInventoryLine.part_id.in_(class_ids),
            MinifigPartInventoryLine.color_id == color_db_id,
        )
    ).all():
        catalog_ids.add(catalog_id)
    return catalog_ids


def resolve_set_nums_for_catalog_gap_sync(
    session: Session,
    *,
    owned_set_ids: list[int] | None,
    catalog_gap_part_keys: list[tuple[int, int]] | None,
) -> list[str]:
    """Distinct Rebrickable set_num keys eligible for catalog-gap sync."""
    catalog_set_ids: set[int] = set()
    if catalog_gap_part_keys:
        for part_id, color_external_id in catalog_gap_part_keys:
            catalog_set_ids.update(
                _catalog_set_ids_for_part_color(session, part_id, color_external_id)
            )
    elif owned_set_ids is not None:
        catalog_set_ids.update(
            session.scalars(
                select(OwnedSet.catalog_set_id).where(OwnedSet.id.in_(owned_set_ids))
            ).all()
        )
    else:
        catalog_set_ids.update(_owned_catalog_set_ids(session))

    catalog_set_ids = {
        catalog_id
        for catalog_id in catalog_set_ids
        if catalog_set_has_catalog_gap(session, catalog_id)
    }
    if not catalog_set_ids:
        return []

    keys: list[str] = []
    seen: set[str] = set()
    for set_number, set_variant in session.execute(
        select(CatalogSet.set_number, CatalogSet.set_variant)
        .where(CatalogSet.id.in_(catalog_set_ids))
        .order_by(CatalogSet.set_number, CatalogSet.set_variant)
    ):
        rb = to_rebrickable_set_num(LegoSetId(number=set_number, variant=set_variant))
        if rb not in seen:
            seen.add(rb)
            keys.append(rb)
    return keys


def iter_catalog_gap_lines(
    session: Session,
) -> list[tuple[SetPartInventoryLine | MinifigPartInventoryLine, int]]:
    """Return catalog inventory lines with gaps and their catalog_set_id."""
    catalog_ids = _owned_catalog_set_ids(session)
    if not catalog_ids:
        return []

    lines: list[tuple[SetPartInventoryLine | MinifigPartInventoryLine, int]] = []
    for catalog_id in catalog_ids:
        for line in _catalog_set_part_lines(session, catalog_id):
            lines.append((line, catalog_id))
        for line in _catalog_minifig_part_lines(session, catalog_id):
            lines.append((line, catalog_id))

    part_color_keys = {(line.part_id, line.color_id) for line, _ in lines}
    element_id_map = load_element_ids_for_part_colors(session, part_color_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)

    return [
        (line, catalog_id)
        for line, catalog_id in lines
        if catalog_line_has_gap(
            session,
            line,
            element_url_by_id=element_url_by_id,
            element_ids=element_id_map.get((line.part_id, line.color_id), []),
        )
    ]


def catalog_sets_for_gap_line(
    session: Session,
    catalog_set_id: int,
) -> list[int]:
    """Owned set copy ids for a catalog set."""
    return list(
        session.scalars(
            select(OwnedSet.id)
            .where(OwnedSet.catalog_set_id == catalog_set_id)
            .order_by(OwnedSet.id)
        ).all()
    )


def aggregate_catalog_gaps(
    session: Session,
) -> dict[tuple[int, int], dict]:
    """Aggregate gap lines by (part_id, color_db_id)."""
    gap_lines = iter_catalog_gap_lines(session)
    if not gap_lines:
        return {}

    catalog_ids = {catalog_id for _, catalog_id in gap_lines}
    owned_by_catalog: dict[int, list[int]] = defaultdict(list)
    for catalog_id in catalog_ids:
        owned_by_catalog[catalog_id] = catalog_sets_for_gap_line(session, catalog_id)

    catalog_rows = session.execute(
        select(CatalogSet.id, CatalogSet.set_number, CatalogSet.name).where(
            CatalogSet.id.in_(catalog_ids)
        )
    ).all()
    catalog_meta = {
        row.id: (row.set_number, row.name) for row in catalog_rows
    }

    from app.services.instance_labels import copy_index_map, display_label

    index_map = copy_index_map(session, list(catalog_ids))
    owned_meta: dict[int, tuple[int, str | None, str]] = {}
    all_owned_ids = [oid for ids in owned_by_catalog.values() for oid in ids]
    if all_owned_ids:
        for owned_set, catalog_set in session.execute(
            select(OwnedSet, CatalogSet)
            .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
            .where(OwnedSet.id.in_(all_owned_ids))
        ).all():
            copy_idx = index_map.get(catalog_set.id, {}).get(owned_set.id, 1)
            owned_meta[owned_set.id] = (
                catalog_set.set_number,
                catalog_set.name,
                display_label(owned_set.label, copy_idx),
            )

    part_color_keys = {(line.part_id, line.color_id) for line, _ in gap_lines}
    element_id_map = load_element_ids_for_part_colors(session, part_color_keys)
    all_element_ids: set[str] = set()
    for ids in element_id_map.values():
        all_element_ids.update(ids)
    element_url_by_id = load_element_image_urls(session, all_element_ids)

    aggregated: dict[tuple[int, int], dict] = {}
    for line, catalog_id in gap_lines:
        part = line.part
        color = line.color
        key = (part.id, color.id)
        line_element_ids = element_id_map.get((part.id, color.id), [])
        missing_element_id, missing_image = _line_gap_flags(
            session,
            line,
            element_url_by_id=element_url_by_id,
            element_ids=line_element_ids,
        )
        bucket = aggregated.get(key)
        if bucket is None:
            bucket = {
                "part": part,
                "color": color,
                "element_ids": set(line_element_ids),
                "part_image_url": resolve_line_image_url(
                    element_ids=line_element_ids,
                    part=part,
                    element_url_by_id=element_url_by_id,
                ),
                "missing_element_id": missing_element_id,
                "missing_image": missing_image,
                "catalog_set_ids": set(),
            }
            aggregated[key] = bucket
        else:
            bucket["missing_element_id"] = (
                bucket["missing_element_id"] or missing_element_id
            )
            bucket["missing_image"] = bucket["missing_image"] or missing_image
            bucket["element_ids"].update(line_element_ids)
            if bucket["part_image_url"] is None:
                bucket["part_image_url"] = resolve_line_image_url(
                    element_ids=line_element_ids,
                    part=part,
                    element_url_by_id=element_url_by_id,
                )
        bucket["catalog_set_ids"].add(catalog_id)

    for bucket in aggregated.values():
        sets: list[dict] = []
        for catalog_id in sorted(bucket["catalog_set_ids"]):
            for owned_set_id in owned_by_catalog.get(catalog_id, []):
                if owned_set_id not in owned_meta:
                    continue
                set_num, set_name, label = owned_meta[owned_set_id]
                sets.append(
                    {
                        "owned_set_id": owned_set_id,
                        "set_num": set_num,
                        "set_name": set_name,
                        "display_label": label,
                    }
                )
        bucket["sets"] = sorted(sets, key=lambda row: (row["set_num"], row["display_label"]))

    return aggregated
