"""Copy index and display labels for set copies (`owned_sets`)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import OwnedSet


def display_label(label: str | None, copy_index: int) -> str:
    if label and label.strip():
        return label.strip()
    return f"Copy #{copy_index}"


def suggested_copy_label(existing_copy_count: int) -> str:
    return f"Copy #{existing_copy_count + 1}"


def copy_index_map(session: Session, catalog_set_ids: list[int]) -> dict[int, dict[int, int]]:
    """Map catalog_set_id -> {owned_set_id -> 1-based copy_index}."""
    if not catalog_set_ids:
        return {}

    rows = session.execute(
        select(OwnedSet.id, OwnedSet.catalog_set_id, OwnedSet.created_at)
        .where(OwnedSet.catalog_set_id.in_(catalog_set_ids))
        .order_by(OwnedSet.catalog_set_id, OwnedSet.created_at, OwnedSet.id)
    ).all()

    result: dict[int, dict[int, int]] = {}
    counters: dict[int, int] = {}
    for owned_id, catalog_id, _created in rows:
        counters[catalog_id] = counters.get(catalog_id, 0) + 1
        result.setdefault(catalog_id, {})[owned_id] = counters[catalog_id]
    return result


def copy_index_for_owned_set(session: Session, owned_set: OwnedSet) -> int:
    mapping = copy_index_map(session, [owned_set.catalog_set_id])
    return mapping.get(owned_set.catalog_set_id, {}).get(owned_set.id, 1)


def count_owned_instances(session: Session, catalog_set_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(OwnedSet)
            .where(OwnedSet.catalog_set_id == catalog_set_id)
        )
        or 0
    )
