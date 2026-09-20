"""Search the user's collection (set copies) and parts appearing in their inventories."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import cast, func, or_, select, String
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    CatalogSet,
    Color,
    MinifigPartInventoryLine,
    OwnedSet,
    Part,
    PartAlias,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
)
from app.schemas.search import (
    SearchElementResult,
    SearchElementSetOccurrence,
    SearchPartColorOccurrence,
    SearchPartDisplayLine,
    SearchPartResult,
    SearchPartSetOccurrence,
    SearchResponse,
    SearchSetResult,
)
from app.services.catalog_state import resolve_part_image_url
from app.services.part_alias_service import part_equivalence_class_ids
from app.services.part_color_catalog_service import (
    element_ids_for_part_color,
    find_part_color_keys_by_element_prefix,
)


def search(
    session: Session,
    *,
    q: str,
    search_type: str = "all",
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    sets: list[SearchSetResult] = []
    parts: list[SearchPartResult] = []

    if search_type in ("set", "all"):
        sets = _search_sets(session, q=q, limit=limit, offset=offset)

    if search_type in ("part", "all"):
        parts = _search_parts(session, q=q, limit=limit, offset=offset)

    elements: list[SearchElementResult] = []
    if search_type in ("element", "all"):
        elements = _search_elements(session, q=q, limit=limit, offset=offset)

    return SearchResponse(sets=sets, parts=parts, elements=elements)


def _search_sets(
    session: Session,
    *,
    q: str,
    limit: int,
    offset: int,
) -> list[SearchSetResult]:
    set_prefix = cast(CatalogSet.set_number, String).like(f"{q}%")
    rows = session.execute(
        select(OwnedSet, CatalogSet)
        .join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
        .where(set_prefix)
        .order_by(OwnedSet.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        SearchSetResult(
            owned_set_id=owned.id,
            set_num=catalog.set_number,
            name=catalog.name,
            investigated=owned.investigated,
            label=owned.label,
        )
        for owned, catalog in rows
    ]


def _owned_catalog_ids_subquery():
    return select(OwnedSet.catalog_set_id).distinct().scalar_subquery()


def _owned_set_id_for_catalog(session: Session, catalog_set_id: int) -> int | None:
    return session.scalar(
        select(OwnedSet.id)
        .where(OwnedSet.catalog_set_id == catalog_set_id)
        .order_by(OwnedSet.id)
        .limit(1)
    )


def _catalogs_by_id(session: Session, catalog_ids: set[int]) -> dict[int, CatalogSet]:
    if not catalog_ids:
        return {}
    cats = session.scalars(select(CatalogSet).where(CatalogSet.id.in_(catalog_ids))).all()
    return {c.id: c for c in cats}


def _occurrences_for_part(
    session: Session,
    *,
    part_id: int,
) -> list[SearchPartSetOccurrence]:
    """Sum template quantities per catalog set and expose per-color totals."""
    owned = _owned_catalog_ids_subquery()
    color_totals: dict[int, dict[tuple[int, str], int]] = defaultdict(lambda: defaultdict(int))

    for cid, color_id, color_name, qty in session.execute(
        select(
            SetPartInventoryLine.catalog_set_id,
            Color.external_id,
            Color.name,
            func.sum(SetPartInventoryLine.quantity),
        )
        .join(Color, SetPartInventoryLine.color_id == Color.id)
        .where(
            SetPartInventoryLine.part_id == part_id,
            SetPartInventoryLine.catalog_set_id.in_(owned),
        )
        .group_by(SetPartInventoryLine.catalog_set_id, Color.external_id, Color.name)
    ).all():
        if cid is not None and qty is not None:
            color_totals[cid][(int(color_id), str(color_name))] += int(qty)

    for cid, color_id, color_name, qty in session.execute(
        select(
            SetMinifigInventoryLine.catalog_set_id,
            Color.external_id,
            Color.name,
            func.sum(
                SetMinifigInventoryLine.quantity * MinifigPartInventoryLine.quantity
            ),
        )
        .select_from(MinifigPartInventoryLine)
        .join(Color, MinifigPartInventoryLine.color_id == Color.id)
        .join(
            SetMinifigInventoryLine,
            SetMinifigInventoryLine.catalog_minifig_id
            == MinifigPartInventoryLine.catalog_minifig_id,
        )
        .where(
            MinifigPartInventoryLine.part_id == part_id,
            SetMinifigInventoryLine.catalog_set_id.in_(owned),
        )
        .group_by(SetMinifigInventoryLine.catalog_set_id, Color.external_id, Color.name)
    ).all():
        if cid is not None and qty is not None:
            color_totals[cid][(int(color_id), str(color_name))] += int(qty)

    if not color_totals:
        return []

    by_id = _catalogs_by_id(session, set(color_totals.keys()))

    def sort_key(cid: int) -> tuple[int, int]:
        c = by_id[cid]
        return (c.set_number, c.set_variant)

    out: list[SearchPartSetOccurrence] = []
    for cid in sorted(color_totals.keys(), key=sort_key):
        cat = by_id[cid]
        owned_set_id = _owned_set_id_for_catalog(session, cid)
        if owned_set_id is None:
            continue
        colors = [
            SearchPartColorOccurrence(
                color_id=color_id,
                color_name=color_name,
                quantity=qty,
            )
            for (color_id, color_name), qty in sorted(
                color_totals[cid].items(), key=lambda item: item[0][1].casefold()
            )
        ]
        out.append(
            SearchPartSetOccurrence(
                set_num=cat.set_number,
                quantity=sum(color.quantity for color in colors),
                owned_set_id=owned_set_id,
                colors=colors,
            )
        )
    return out


def _expand_part_class(session: Session, seed: Part) -> list[Part]:
    """Return part rows connected by alias strings, preserving actual part numbers.

    Alias rows describe equivalence, but set BOM lines still point at the concrete
    `parts.part_num` that was imported or entered for that set. Search display uses
    those concrete part rows so each alias line can show only its own occurrences.
    """
    class_ids: set[int] = {seed.id}
    known_strings: set[str] = {seed.part_num}

    changed = True
    while changed:
        changed = False
        alias_strings = session.scalars(
            select(PartAlias.alias).where(PartAlias.part_id.in_(class_ids))
        ).all()
        for alias in alias_strings:
            if alias not in known_strings:
                known_strings.add(alias)
                changed = True

        linked_parts = session.scalars(
            select(Part)
            .options(selectinload(Part.aliases))
            .where(Part.part_num.in_(known_strings))
        ).all()
        for part in linked_parts:
            if part.id not in class_ids:
                class_ids.add(part.id)
                changed = True
            if part.part_num not in known_strings:
                known_strings.add(part.part_num)
                changed = True

    parts = session.scalars(
        select(Part)
        .options(selectinload(Part.aliases))
        .where(Part.id.in_(class_ids))
    ).all()
    by_id = {part.id: part for part in parts}
    return [by_id[seed.id], *sorted(
        (part for part in parts if part.id != seed.id),
        key=lambda p: p.part_num.casefold(),
    )]


def _search_parts(
    session: Session,
    *,
    q: str,
    limit: int,
    offset: int,
) -> list[SearchPartResult]:
    part_match = or_(Part.part_num.startswith(q), PartAlias.alias.startswith(q))

    part_ids = [
        row[0]
        for row in session.execute(
            select(Part.id)
            .outerjoin(PartAlias, PartAlias.part_id == Part.id)
            .where(part_match)
            .group_by(Part.id, Part.part_num)
            .order_by(Part.part_num)
            .limit(limit)
            .offset(offset)
        ).all()
    ]

    if not part_ids:
        return []

    parts = session.scalars(
        select(Part)
        .options(selectinload(Part.aliases))
        .where(Part.id.in_(part_ids))
    ).all()
    by_id = {p.id: p for p in parts}
    ordered_parts = [by_id[pid] for pid in part_ids if pid in by_id]

    results: list[SearchPartResult] = []
    seen_classes: set[frozenset[int]] = set()
    for part in ordered_parts:
        class_parts = _expand_part_class(session, part)
        class_key = frozenset(p.id for p in class_parts)
        if class_key in seen_classes:
            continue
        seen_classes.add(class_key)

        lines: list[SearchPartDisplayLine] = []
        for class_part in class_parts:
            occurrences = _occurrences_for_part(session, part_id=class_part.id)
            if not occurrences:
                continue
            lines.append(
                SearchPartDisplayLine(
                    display_part_num=class_part.part_num,
                    sets=list(occurrences),
                )
            )
        if not lines:
            continue

        results.append(
            SearchPartResult(
                part_num=part.part_num,
                name=part.name,
                image_url=resolve_part_image_url(part),
                lines=lines,
            )
        )

    return results


def _occurrences_for_part_color(
    session: Session,
    *,
    part_id: int,
    color_external_id: int,
) -> list[SearchElementSetOccurrence]:
    owned = _owned_catalog_ids_subquery()
    totals: dict[int, int] = defaultdict(int)
    class_ids = part_equivalence_class_ids(session, part_id)

    for cid, qty in session.execute(
        select(
            SetPartInventoryLine.catalog_set_id,
            func.sum(SetPartInventoryLine.quantity),
        )
        .join(Color, SetPartInventoryLine.color_id == Color.id)
        .where(
            SetPartInventoryLine.part_id.in_(class_ids),
            Color.external_id == color_external_id,
            SetPartInventoryLine.catalog_set_id.in_(owned),
        )
        .group_by(SetPartInventoryLine.catalog_set_id)
    ).all():
        if cid is not None and qty is not None:
            totals[cid] += int(qty)

    for cid, qty in session.execute(
        select(
            SetMinifigInventoryLine.catalog_set_id,
            func.sum(
                SetMinifigInventoryLine.quantity * MinifigPartInventoryLine.quantity
            ),
        )
        .select_from(MinifigPartInventoryLine)
        .join(Color, MinifigPartInventoryLine.color_id == Color.id)
        .join(
            SetMinifigInventoryLine,
            SetMinifigInventoryLine.catalog_minifig_id
            == MinifigPartInventoryLine.catalog_minifig_id,
        )
        .where(
            MinifigPartInventoryLine.part_id.in_(class_ids),
            Color.external_id == color_external_id,
            SetMinifigInventoryLine.catalog_set_id.in_(owned),
        )
        .group_by(SetMinifigInventoryLine.catalog_set_id)
    ).all():
        if cid is not None and qty is not None:
            totals[cid] += int(qty)

    by_id = _catalogs_by_id(session, set(totals.keys()))
    out: list[SearchElementSetOccurrence] = []
    for cid in sorted(totals, key=lambda key: (by_id[key].set_number, by_id[key].set_variant)):
        owned_set_id = _owned_set_id_for_catalog(session, cid)
        if owned_set_id is None:
            continue
        out.append(
            SearchElementSetOccurrence(
                set_num=by_id[cid].set_number,
                quantity=totals[cid],
                owned_set_id=owned_set_id,
            )
        )
    return out


def _persisted_element_ids_for_part_color(
    session: Session,
    *,
    part_id: int,
    color_external_id: int,
) -> list[str]:
    color_db_id = session.scalar(
        select(Color.id).where(Color.external_id == color_external_id)
    )
    if color_db_id is None:
        return []
    return element_ids_for_part_color(session, part_id, color_db_id)


def _search_elements(
    session: Session,
    *,
    q: str,
    limit: int,
    offset: int,
) -> list[SearchElementResult]:
    anchor_color_keys = find_part_color_keys_by_element_prefix(session, q)
    if not anchor_color_keys:
        return []

    part_ids = {part_id for part_id, _ in anchor_color_keys}
    color_db_ids = {color_db_id for _, color_db_id in anchor_color_keys}
    parts_by_id = {
        row.id: row for row in session.scalars(select(Part).where(Part.id.in_(part_ids))).all()
    }
    colors_by_id = {
        row.id: row
        for row in session.scalars(select(Color).where(Color.id.in_(color_db_ids))).all()
    }
    ordered = sorted(
        [
            (parts_by_id[part_id], colors_by_id[color_db_id])
            for part_id, color_db_id in anchor_color_keys
            if part_id in parts_by_id and color_db_id in colors_by_id
        ],
        key=lambda item: (item[0].part_num.casefold(), item[1].name.casefold()),
    )[offset : offset + limit]

    results: list[SearchElementResult] = []
    for part, color in ordered:
        occurrences = _occurrences_for_part_color(
            session, part_id=part.id, color_external_id=color.external_id
        )
        if not occurrences:
            continue
        results.append(
            SearchElementResult(
                element_ids=_persisted_element_ids_for_part_color(
                    session, part_id=part.id, color_external_id=color.external_id
                ),
                part_num=part.part_num,
                part_name=part.name,
                color_id=color.external_id,
                color_name=color.name,
                sets=occurrences,
            )
        )
    return results
