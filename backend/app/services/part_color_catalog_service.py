"""Canonical Element IDs per part alias class + color (shared across all sets)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Part,
    PartAlias,
    PartColorElementId,
    PartColorKey,
    Color,
)
from app.services.element_catalog import element_ids_for_import
from app.services.part_alias_service import part_equivalence_class_ids

REBRICKABLE_SOURCE = "rebrickable"
USER_SOURCE = "user"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def anchor_part_id_for_class(session: Session, part_id: int) -> int:
    class_ids = part_equivalence_class_ids(session, part_id)
    return min(class_ids)


def _part_aliases(session: Session, part_id: int) -> tuple[str, ...]:
    part = session.get(Part, part_id)
    if part is None:
        return ()
    aliases = session.scalars(
        select(PartAlias.alias).where(PartAlias.part_id == part_id)
    ).all()
    return tuple(sorted(set(aliases)))


def get_part_color_key(
    session: Session,
    part_id: int,
    color_db_id: int,
) -> PartColorKey | None:
    anchor_id = anchor_part_id_for_class(session, part_id)
    return session.scalar(
        select(PartColorKey)
        .where(
            PartColorKey.anchor_part_id == anchor_id,
            PartColorKey.color_id == color_db_id,
        )
        .options(selectinload(PartColorKey.element_ids))
    )


def element_ids_for_part_color(
    session: Session,
    part_id: int,
    color_db_id: int,
) -> list[str]:
    key = get_part_color_key(session, part_id, color_db_id)
    if key is None:
        return []
    return sorted(row.element_id for row in key.element_ids)


def load_element_ids_for_part_colors(
    session: Session,
    keys: set[tuple[int, int]],
) -> dict[tuple[int, int], list[str]]:
    if not keys:
        return {}

    anchor_by_key: dict[tuple[int, int], int] = {}
    for part_id, color_db_id in keys:
        anchor_by_key[(part_id, color_db_id)] = anchor_part_id_for_class(
            session, part_id
        )

    anchor_color_pairs = {(anchor_by_key[k], k[1]) for k in keys}
    anchors = {pair[0] for pair in anchor_color_pairs}
    colors = {pair[1] for pair in anchor_color_pairs}

    rows = session.scalars(
        select(PartColorKey)
        .where(
            PartColorKey.anchor_part_id.in_(anchors),
            PartColorKey.color_id.in_(colors),
        )
        .options(selectinload(PartColorKey.element_ids))
    ).all()
    by_anchor_color: dict[tuple[int, int], list[str]] = {}
    for row in rows:
        by_anchor_color[(row.anchor_part_id, row.color_id)] = sorted(
            element.element_id for element in row.element_ids
        )

    result: dict[tuple[int, int], list[str]] = {}
    for key in keys:
        anchor = anchor_by_key[key]
        result[key] = list(by_anchor_color.get((anchor, key[1]), []))
    return result


def find_part_color_keys_by_element_prefix(
    session: Session,
    prefix: str,
) -> list[tuple[int, int]]:
    """Return distinct ``(anchor_part_id, color_db_id)`` pairs matching an Element ID prefix."""
    if not prefix:
        return []
    rows = session.execute(
        select(PartColorKey.anchor_part_id, PartColorKey.color_id)
        .join(
            PartColorElementId,
            PartColorElementId.part_color_key_id == PartColorKey.id,
        )
        .where(PartColorElementId.element_id.startswith(prefix))
        .distinct()
    ).all()
    return [(int(anchor_part_id), int(color_db_id)) for anchor_part_id, color_db_id in rows]


def _upsert_part_color_key(
    session: Session,
    anchor_part_id: int,
    color_db_id: int,
    *,
    source: str,
    when: datetime,
) -> PartColorKey:
    key = session.scalar(
        select(PartColorKey).where(
            PartColorKey.anchor_part_id == anchor_part_id,
            PartColorKey.color_id == color_db_id,
        )
    )
    if key is None:
        key = PartColorKey(
            anchor_part_id=anchor_part_id,
            color_id=color_db_id,
            source=source,
            updated_at=when,
        )
        session.add(key)
    else:
        key.source = source
        key.updated_at = when
    session.flush()
    return key


def set_element_ids_for_part_color(
    session: Session,
    part_id: int,
    color_db_id: int,
    element_ids: tuple[str, ...],
    *,
    source: str = REBRICKABLE_SOURCE,
    merge: bool = False,
) -> PartColorKey:
    """Write canonical Element IDs for a part alias class + color."""
    when = utc_now()
    anchor_id = anchor_part_id_for_class(session, part_id)
    key = _upsert_part_color_key(
        session, anchor_id, color_db_id, source=source, when=when
    )

    desired = tuple(sorted(set(element_ids)))
    if merge and key.element_ids:
        existing = {row.element_id for row in key.element_ids}
        desired = tuple(sorted(existing | set(desired)))

    session.execute(
        delete(PartColorElementId).where(PartColorElementId.part_color_key_id == key.id)
    )
    for element_id in desired:
        session.add(PartColorElementId(part_color_key_id=key.id, element_id=element_id))
    session.flush()
    return key


def enrich_element_ids_for_part_color(
    session: Session,
    part_id: int,
    color_db_id: int,
    *,
    part_num: str,
    color_external_id: int,
    aliases: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Resolve Element IDs from elements.csv and persist on the canonical part-color."""
    computed = element_ids_for_import(part_num, color_external_id, aliases)
    if computed:
        set_element_ids_for_part_color(
            session,
            part_id,
            color_db_id,
            computed,
            source=REBRICKABLE_SOURCE,
            merge=True,
        )
    return computed


def backfill_part_color_element_ids_from_csv(session: Session) -> int:
    """Enrich canonical part-color rows from elements.csv for all inventory pairs."""
    from app.db.models import MinifigPartInventoryLine, SetPartInventoryLine

    keys: set[tuple[int, int]] = set()
    for part_id, color_id in session.execute(
        select(SetPartInventoryLine.part_id, SetPartInventoryLine.color_id).distinct()
    ):
        keys.add((part_id, color_id))
    for part_id, color_id in session.execute(
        select(MinifigPartInventoryLine.part_id, MinifigPartInventoryLine.color_id).distinct()
    ):
        keys.add((part_id, color_id))

    existing_map = load_element_ids_for_part_colors(session, keys)
    part_ids = {part_id for part_id, _ in keys}
    color_ids = {color_id for _, color_id in keys}
    parts_by_id = {
        part.id: part
        for part in session.scalars(select(Part).where(Part.id.in_(part_ids))).all()
    }
    colors_by_id = {
        color.id: color
        for color in session.scalars(select(Color).where(Color.id.in_(color_ids))).all()
    }
    aliases_by_part: dict[int, tuple[str, ...]] = {}
    for part_id in part_ids:
        aliases_by_part[part_id] = _part_aliases(session, part_id)

    enriched = 0
    for part_id, color_id in keys:
        if existing_map.get((part_id, color_id)):
            continue
        part = parts_by_id.get(part_id)
        color = colors_by_id.get(color_id)
        if part is None or color is None:
            continue
        computed = element_ids_for_import(
            part.part_num,
            color.external_id,
            aliases_by_part.get(part_id, ()),
        )
        if not computed:
            continue
        set_element_ids_for_part_color(
            session,
            part_id,
            color_id,
            computed,
            source=REBRICKABLE_SOURCE,
            merge=True,
        )
        enriched += 1
        if enriched % 200 == 0:
            session.flush()
    session.flush()
    return enriched


def merge_part_color_keys_for_class(
    session: Session,
    class_part_ids: set[int],
) -> None:
    """After alias-class merge, unify part-color keys that belonged to former anchors."""
    if not class_part_ids:
        return

    anchor_id = min(class_part_ids)
    keys = session.scalars(
        select(PartColorKey)
        .where(PartColorKey.anchor_part_id.in_(class_part_ids))
        .options(selectinload(PartColorKey.element_ids))
    ).all()
    if not keys:
        return

    by_color: dict[int, list[PartColorKey]] = {}
    for key in keys:
        by_color.setdefault(key.color_id, []).append(key)

    when = utc_now()
    for color_db_id, color_keys in by_color.items():
        merged_ids = sorted(
            {
                element.element_id
                for key in color_keys
                for element in key.element_ids
            }
        )
        canonical = _upsert_part_color_key(
            session,
            anchor_id,
            color_db_id,
            source=color_keys[0].source,
            when=when,
        )
        session.execute(
            delete(PartColorElementId).where(
                PartColorElementId.part_color_key_id == canonical.id
            )
        )
        for element_id in merged_ids:
            session.add(
                PartColorElementId(part_color_key_id=canonical.id, element_id=element_id)
            )
        for key in color_keys:
            if key.id != canonical.id:
                session.delete(key)
    session.flush()
