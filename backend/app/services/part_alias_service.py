"""Symmetric part alias equivalence classes (Phase 11B)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Part, PartAlias

USER_SOURCE = "user"
MAX_ALIASES_PER_PART = 20


class PartAliasError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _normalize_alias_strings(
    aliases: list[str],
    *,
    exclude: str | None = None,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in aliases:
        trimmed = raw.strip()
        if not trimmed:
            continue
        if exclude is not None and trimmed == exclude:
            continue
        if trimmed in seen:
            continue
        seen.add(trimmed)
        result.append(trimmed)
    return result


def _expand_equivalence_class(
    session: Session,
    anchor_id: int,
    seed_aliases: list[str],
) -> set[int]:
    """Union part ids linked by seed aliases, part_nums, and existing alias rows."""
    class_ids: set[int] = {anchor_id}
    known_strings: set[str] = set(seed_aliases)

    changed = True
    while changed:
        changed = False
        for alias_str in list(known_strings):
            linked = session.scalar(select(Part.id).where(Part.part_num == alias_str))
            if linked is not None and linked not in class_ids:
                class_ids.add(linked)
                changed = True

        for part_id in list(class_ids):
            part = session.get(Part, part_id)
            if part is not None and part.part_num not in known_strings:
                known_strings.add(part.part_num)
                changed = True
            rows = session.scalars(
                select(PartAlias.alias).where(PartAlias.part_id == part_id)
            ).all()
            for alias_str in rows:
                if alias_str not in known_strings:
                    known_strings.add(alias_str)
                    changed = True

    return class_ids


def part_equivalence_class_ids(session: Session, part_id: int) -> set[int]:
    """Return all part row ids in the alias-linked equivalence class."""
    return _expand_equivalence_class(session, part_id, [])


def _aliases_for_display(part: Part, alias_strings: list[str]) -> list[str]:
    return sorted(a for a in alias_strings if a != part.part_num)


def replace_part_aliases(
    session: Session,
    part_id: int,
    aliases: list[str],
) -> tuple[Part, list[str]]:
    anchor = session.get(Part, part_id)
    if anchor is None:
        raise PartAliasError("Part not found", status_code=404)

    normalized = _normalize_alias_strings(aliases, exclude=anchor.part_num)
    if len(normalized) > MAX_ALIASES_PER_PART:
        raise PartAliasError(
            f"At most {MAX_ALIASES_PER_PART} aliases allowed",
            status_code=422,
        )

    if normalized:
        class_ids = _expand_equivalence_class(session, anchor.id, normalized)
    else:
        existing = session.scalars(
            select(PartAlias.alias).where(
                PartAlias.part_id == anchor.id,
                PartAlias.source == USER_SOURCE,
            )
        ).all()
        if existing:
            class_ids = _expand_equivalence_class(session, anchor.id, list(existing))
        else:
            class_ids = {anchor.id}
    parts = session.scalars(select(Part).where(Part.id.in_(class_ids))).all()
    parts_by_id = {part.id: part for part in parts}

    if normalized:
        class_part_nums = {part.part_num for part in parts}
        full_vocab = class_part_nums | set(normalized)
    else:
        full_vocab: set[str] = set()

    per_part_aliases: dict[int, list[str]] = {}
    all_inserted: set[str] = set()
    for pid in class_ids:
        part = parts_by_id[pid]
        desired = _aliases_for_display(
            part,
            sorted(full_vocab - {part.part_num}),
        )
        if len(desired) > MAX_ALIASES_PER_PART:
            raise PartAliasError(
                f"At most {MAX_ALIASES_PER_PART} aliases allowed per part",
                status_code=422,
            )
        per_part_aliases[pid] = desired
        all_inserted.update(desired)

    if all_inserted:
        session.execute(
            delete(PartAlias).where(
                PartAlias.source == USER_SOURCE,
                PartAlias.alias.in_(all_inserted),
            )
        )
    session.execute(delete(PartAlias).where(PartAlias.part_id.in_(class_ids)))

    for pid, desired in per_part_aliases.items():
        for alias_str in desired:
            session.add(
                PartAlias(part_id=pid, alias=alias_str, source=USER_SOURCE)
            )

    session.flush()
    from app.services.part_color_catalog_service import merge_part_color_keys_for_class

    merge_part_color_keys_for_class(session, class_ids)
    return anchor, per_part_aliases[anchor.id]
