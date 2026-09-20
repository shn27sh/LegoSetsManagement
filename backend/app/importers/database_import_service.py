"""Import catalog and collection data from another LEGO Collection Manager SQLite database."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.import_progress import commit_import_progress
from app.importers.import_job_types import ProgressCallback
from app.importers.import_progress_callback import check_import_cancelled
from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    Color,
    ElementImage,
    MinifigPartInventoryLine,
    MissingItem,
    OwnedSet,
    OwnedSetInventoryLine,
    Part,
    PartAlias,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
    Theme,
)
from app.services.instance_inventory import (
    ensure_instance_inventory_for_catalog,
    refresh_instance_quantities_for_catalog,
)
from app.services.part_color_catalog_service import (
    element_ids_for_part_color,
    set_element_ids_for_part_color,
)

DatabaseImportMode = Literal["add_only_new", "add_and_update"]


@dataclass
class _CatalogImportStats:
    instances_created: int = 0
    parts_upserted: int = 0
    inventory_lines_written: int = 0


@dataclass
class DatabaseImportResult:
    sets_added: int = 0
    sets_updated: int = 0
    sets_skipped: int = 0
    skipped_set_nums: list[str] = field(default_factory=list)
    instances_created: int = 0
    parts_upserted: int = 0
    inventory_lines_written: int = 0


def validate_source_database(path: str) -> None:
    """Raise ValueError if path is not a compatible SQLite database."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ValueError("Not a valid SQLite database file") from exc
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_sets'"
        )
        if cursor.fetchone() is None:
            raise ValueError("Database is missing catalog_sets table")
    except sqlite3.Error as exc:
        raise ValueError("Not a valid SQLite database file") from exc
    finally:
        conn.close()


def import_from_database(
    target_session: Session,
    source_db_path: str,
    *,
    mode: DatabaseImportMode,
    cancel_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> DatabaseImportResult:
    validate_source_database(source_db_path)
    source_engine = create_engine(
        f"sqlite:///{source_db_path}",
        connect_args={"check_same_thread": False},
    )
    source_session = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)()
    try:
        return _import_from_sessions(
            target_session,
            source_session,
            mode=mode,
            cancel_event=cancel_event,
            on_progress=on_progress,
        )
    finally:
        source_session.close()
        source_engine.dispose()


def import_from_database_session(
    target_session: Session,
    source_session: Session,
    *,
    mode: DatabaseImportMode,
) -> DatabaseImportResult:
    """Import from an open source session (used in tests)."""
    return _import_from_sessions(target_session, source_session, mode=mode)


def _import_from_sessions(
    target_session: Session,
    source_session: Session,
    *,
    mode: DatabaseImportMode,
    cancel_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> DatabaseImportResult:
    result = DatabaseImportResult()
    source_catalogs = source_session.scalars(
        select(CatalogSet).order_by(CatalogSet.set_number, CatalogSet.set_variant)
    ).all()
    total_sets = len(source_catalogs)

    for step, source_catalog in enumerate(source_catalogs):
        check_import_cancelled(cancel_event)
        set_num = f"{source_catalog.set_number}-{source_catalog.set_variant}"
        if on_progress is not None:
            on_progress(step, total_sets, f"Importing {set_num}")
        target_catalog = target_session.scalar(
            select(CatalogSet).where(
                CatalogSet.set_number == source_catalog.set_number,
                CatalogSet.set_variant == source_catalog.set_variant,
            )
        )
        if target_catalog is None:
            stats = _import_new_catalog_set(
                target_session, source_session, source_catalog
            )
            result.sets_added += 1
            result.instances_created += stats.instances_created
            result.parts_upserted += stats.parts_upserted
            result.inventory_lines_written += stats.inventory_lines_written
            commit_import_progress(target_session)
        elif mode == "add_only_new":
            result.sets_skipped += 1
            result.skipped_set_nums.append(set_num)
        else:
            stats = _update_existing_catalog_set(
                target_session,
                source_session,
                source_catalog,
                target_catalog,
            )
            result.sets_updated += 1
            result.parts_upserted += stats.parts_upserted
            result.inventory_lines_written += stats.inventory_lines_written
            commit_import_progress(target_session)

    return result


def _import_new_catalog_set(
    target_session: Session,
    source_session: Session,
    source_catalog: CatalogSet,
) -> _CatalogImportStats:
    stats = _CatalogImportStats()
    theme_id = _upsert_theme_from_source(
        target_session, source_session, source_catalog.theme_id
    )
    target_catalog = CatalogSet(
        set_number=source_catalog.set_number,
        set_variant=source_catalog.set_variant,
        name=source_catalog.name,
        year=source_catalog.year,
        theme_id=theme_id,
        num_parts=source_catalog.num_parts,
        image_url=source_catalog.image_url,
        image_blob=source_catalog.image_blob,
        image_content_type=source_catalog.image_content_type,
        image_byte_size=source_catalog.image_byte_size,
        source=source_catalog.source,
        source_ref=source_catalog.source_ref,
        fetched_at=source_catalog.fetched_at,
    )
    target_session.add(target_catalog)
    target_session.flush()

    set_part_line_map = _copy_set_part_inventory(
        target_session,
        source_session,
        source_catalog.id,
        target_catalog.id,
        stats,
        replace=False,
    )
    minifig_part_line_map = _copy_minifig_inventory(
        target_session,
        source_session,
        source_catalog.id,
        target_catalog.id,
        stats,
        replace=False,
    )

    source_owned_sets = source_session.scalars(
        select(OwnedSet).where(OwnedSet.catalog_set_id == source_catalog.id)
    ).all()
    for source_owned in source_owned_sets:
        target_owned = OwnedSet(
            catalog_set_id=target_catalog.id,
            investigated=source_owned.investigated,
            label=source_owned.label,
            age=source_owned.age,
            created_at=source_owned.created_at,
            notes=source_owned.notes,
        )
        target_session.add(target_owned)
        target_session.flush()
        stats.instances_created += 1

        source_lines = source_session.scalars(
            select(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.owned_set_id == source_owned.id
            )
        ).all()
        for source_line in source_lines:
            target_set_part_line_id = None
            target_minifig_part_line_id = None
            if source_line.set_part_inventory_line_id is not None:
                target_set_part_line_id = set_part_line_map.get(
                    source_line.set_part_inventory_line_id
                )
            if source_line.minifig_part_inventory_line_id is not None:
                target_minifig_part_line_id = minifig_part_line_map.get(
                    source_line.minifig_part_inventory_line_id
                )
            if target_set_part_line_id is None and target_minifig_part_line_id is None:
                continue
            target_line = OwnedSetInventoryLine(
                owned_set_id=target_owned.id,
                set_part_inventory_line_id=target_set_part_line_id,
                minifig_part_inventory_line_id=target_minifig_part_line_id,
                quantity=source_line.quantity,
                quantity_missing=source_line.quantity_missing,
            )
            target_session.add(target_line)
            target_session.flush()
            if source_line.quantity_missing > 0:
                source_missing = source_session.scalar(
                    select(MissingItem).where(
                        MissingItem.owned_set_inventory_line_id == source_line.id
                    )
                )
                if source_missing is not None:
                    target_session.add(
                        MissingItem(
                            owned_set_id=target_owned.id,
                            owned_set_inventory_line_id=target_line.id,
                            created_at=source_missing.created_at,
                            updated_at=source_missing.updated_at,
                        )
                    )
                    target_session.flush()

    return stats


def _update_existing_catalog_set(
    target_session: Session,
    source_session: Session,
    source_catalog: CatalogSet,
    target_catalog: CatalogSet,
) -> _CatalogImportStats:
    stats = _CatalogImportStats()

    if target_catalog.theme_id is None and source_catalog.theme_id is not None:
        target_catalog.theme_id = _upsert_theme_from_source(
            target_session, source_session, source_catalog.theme_id
        )

    target_catalog.name = source_catalog.name
    target_catalog.year = source_catalog.year
    target_catalog.num_parts = source_catalog.num_parts
    target_catalog.image_url = source_catalog.image_url
    target_catalog.image_blob = source_catalog.image_blob
    target_catalog.image_content_type = source_catalog.image_content_type
    target_catalog.image_byte_size = source_catalog.image_byte_size
    target_catalog.source = source_catalog.source
    target_catalog.source_ref = source_catalog.source_ref
    target_catalog.fetched_at = source_catalog.fetched_at
    target_session.flush()

    _copy_set_part_inventory(
        target_session,
        source_session,
        source_catalog.id,
        target_catalog.id,
        stats,
        replace=True,
    )
    _copy_minifig_inventory(
        target_session,
        source_session,
        source_catalog.id,
        target_catalog.id,
        stats,
        replace=True,
    )

    target_copies = target_session.scalars(
        select(OwnedSet).where(OwnedSet.catalog_set_id == target_catalog.id)
    ).all()
    target_has_age = any(copy.age is not None for copy in target_copies)
    if not target_has_age:
        source_age = source_session.scalar(
            select(OwnedSet.age)
            .where(
                OwnedSet.catalog_set_id == source_catalog.id,
                OwnedSet.age.is_not(None),
            )
            .limit(1)
        )
        if source_age is not None:
            for copy in target_copies:
                copy.age = source_age

    ensure_instance_inventory_for_catalog(target_session, target_catalog.id)
    refresh_instance_quantities_for_catalog(target_session, target_catalog.id)
    target_session.flush()
    return stats


def _upsert_theme_from_source(
    target_session: Session,
    source_session: Session,
    theme_id: int | None,
) -> int | None:
    if theme_id is None:
        return None
    source_theme = source_session.get(Theme, theme_id)
    if source_theme is None:
        return None
    target_theme = target_session.scalar(
        select(Theme).where(Theme.external_id == source_theme.external_id)
    )
    if target_theme is None:
        target_theme = Theme(
            external_id=source_theme.external_id,
            name=source_theme.name,
            source=source_theme.source,
            fetched_at=source_theme.fetched_at,
        )
        target_session.add(target_theme)
    else:
        target_theme.name = source_theme.name
        target_theme.fetched_at = source_theme.fetched_at
    target_session.flush()
    return target_theme.id


def _upsert_color_from_source(
    target_session: Session,
    source_session: Session,
    color_id: int,
) -> Color | None:
    source_color = source_session.get(Color, color_id)
    if source_color is None:
        return None
    target_color = target_session.scalar(
        select(Color).where(Color.external_id == source_color.external_id)
    )
    if target_color is None:
        target_color = Color(
            external_id=source_color.external_id,
            name=source_color.name,
            rgb=source_color.rgb,
            source=source_color.source,
            fetched_at=source_color.fetched_at,
        )
        target_session.add(target_color)
    else:
        target_color.name = source_color.name
        target_color.rgb = source_color.rgb
        target_color.fetched_at = source_color.fetched_at
    target_session.flush()
    return target_color


def _upsert_part_from_source(
    target_session: Session,
    source_session: Session,
    part_id: int,
    stats: _CatalogImportStats,
) -> Part | None:
    source_part = source_session.get(Part, part_id)
    if source_part is None:
        return None
    target_part = target_session.scalar(
        select(Part).where(Part.part_num == source_part.part_num)
    )
    if target_part is None:
        target_part = Part(
            part_num=source_part.part_num,
            name=source_part.name,
            image_url=source_part.image_url,
            image_blob=source_part.image_blob,
            image_content_type=source_part.image_content_type,
            image_byte_size=source_part.image_byte_size,
            source=source_part.source,
            source_ref=source_part.source_ref,
            fetched_at=source_part.fetched_at,
        )
        target_session.add(target_part)
        stats.parts_upserted += 1
    else:
        target_part.name = source_part.name
        target_part.image_url = source_part.image_url
        target_part.image_blob = source_part.image_blob
        target_part.image_content_type = source_part.image_content_type
        target_part.image_byte_size = source_part.image_byte_size
        target_part.part_image_user_removed = source_part.part_image_user_removed
        target_part.fetched_at = source_part.fetched_at
    target_session.flush()
    _copy_part_aliases(target_session, source_session, source_part.id, target_part.id)
    return target_part


def _copy_part_aliases(
    target_session: Session,
    source_session: Session,
    source_part_id: int,
    target_part_id: int,
) -> None:
    source_aliases = source_session.scalars(
        select(PartAlias).where(PartAlias.part_id == source_part_id)
    ).all()
    for source_alias in source_aliases:
        exists = target_session.scalar(
            select(PartAlias.id).where(
                PartAlias.part_id == target_part_id,
                PartAlias.alias == source_alias.alias,
                PartAlias.source == source_alias.source,
            )
        )
        if exists is None:
            target_session.add(
                PartAlias(
                    part_id=target_part_id,
                    alias=source_alias.alias,
                    source=source_alias.source,
                )
            )
    target_session.flush()


def _upsert_minifig_from_source(
    target_session: Session,
    source_session: Session,
    minifig_id: int,
) -> CatalogMinifig | None:
    source_minifig = source_session.get(CatalogMinifig, minifig_id)
    if source_minifig is None:
        return None
    target_minifig = target_session.scalar(
        select(CatalogMinifig).where(
            CatalogMinifig.minifig_num == source_minifig.minifig_num
        )
    )
    if target_minifig is None:
        target_minifig = CatalogMinifig(
            minifig_num=source_minifig.minifig_num,
            name=source_minifig.name,
            image_url=source_minifig.image_url,
            image_blob=source_minifig.image_blob,
            image_content_type=source_minifig.image_content_type,
            image_byte_size=source_minifig.image_byte_size,
            source=source_minifig.source,
            fetched_at=source_minifig.fetched_at,
        )
        target_session.add(target_minifig)
    else:
        target_minifig.name = source_minifig.name
        target_minifig.image_url = source_minifig.image_url
        target_minifig.image_blob = source_minifig.image_blob
        target_minifig.image_content_type = source_minifig.image_content_type
        target_minifig.image_byte_size = source_minifig.image_byte_size
        target_minifig.fetched_at = source_minifig.fetched_at
    target_session.flush()
    return target_minifig


def _copy_part_color_catalog(
    target_session: Session,
    source_session: Session,
    *,
    source_part_id: int,
    source_color_id: int,
    target_part_id: int,
    target_color_id: int,
) -> None:
    source_ids = element_ids_for_part_color(
        source_session, source_part_id, source_color_id
    )
    if not source_ids:
        return
    for element_id in source_ids:
        _upsert_element_image(target_session, source_session, element_id)
    set_element_ids_for_part_color(
        target_session,
        target_part_id,
        target_color_id,
        tuple(source_ids),
        merge=True,
    )
    target_session.flush()


def _upsert_element_image(
    target_session: Session,
    source_session: Session,
    element_id: str,
) -> None:
    source_image = source_session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if source_image is None:
        return
    target_image = target_session.scalar(
        select(ElementImage).where(ElementImage.element_id == element_id)
    )
    if target_image is None:
        target_session.add(
            ElementImage(
                element_id=source_image.element_id,
                image_blob=source_image.image_blob,
                image_content_type=source_image.image_content_type,
                image_byte_size=source_image.image_byte_size,
                source=source_image.source,
                fetched_at=source_image.fetched_at,
            )
        )
    else:
        target_image.image_blob = source_image.image_blob
        target_image.image_content_type = source_image.image_content_type
        target_image.image_byte_size = source_image.image_byte_size
        target_image.fetched_at = source_image.fetched_at
    target_session.flush()


def _copy_set_part_inventory(
    target_session: Session,
    source_session: Session,
    source_catalog_id: int,
    target_catalog_id: int,
    stats: _CatalogImportStats,
    *,
    replace: bool,
) -> dict[int, int]:
    """Return map of source set_part_inventory_line.id -> target line id."""
    line_map: dict[int, int] = {}
    new_keys: set[tuple[int, int]] = set()

    source_lines = source_session.scalars(
        select(SetPartInventoryLine).where(
            SetPartInventoryLine.catalog_set_id == source_catalog_id
        )
    ).all()

    for source_line in source_lines:
        part = _upsert_part_from_source(
            target_session, source_session, source_line.part_id, stats
        )
        color = _upsert_color_from_source(
            target_session, source_session, source_line.color_id
        )
        if part is None or color is None:
            continue

        key = (part.id, color.id)
        new_keys.add(key)

        target_line = target_session.scalar(
            select(SetPartInventoryLine).where(
                SetPartInventoryLine.catalog_set_id == target_catalog_id,
                SetPartInventoryLine.part_id == part.id,
                SetPartInventoryLine.color_id == color.id,
            )
        )
        if target_line is None:
            target_line = SetPartInventoryLine(
                catalog_set_id=target_catalog_id,
                part_id=part.id,
                color_id=color.id,
                quantity=source_line.quantity,
                image_url=source_line.image_url,
                source=source_line.source,
                source_ref=source_line.source_ref,
                fetched_at=source_line.fetched_at,
            )
            target_session.add(target_line)
        else:
            target_line.quantity = source_line.quantity
            target_line.image_url = source_line.image_url
            target_line.source_ref = source_line.source_ref
            target_line.fetched_at = source_line.fetched_at
        target_session.flush()
        _copy_part_color_catalog(
            target_session,
            source_session,
            source_part_id=source_line.part_id,
            source_color_id=source_line.color_id,
            target_part_id=part.id,
            target_color_id=color.id,
        )
        line_map[source_line.id] = target_line.id
        stats.inventory_lines_written += 1

    if replace:
        existing_lines = target_session.scalars(
            select(SetPartInventoryLine).where(
                SetPartInventoryLine.catalog_set_id == target_catalog_id
            )
        ).all()
        for existing in existing_lines:
            key = (existing.part_id, existing.color_id)
            if key in new_keys:
                continue
            target_session.execute(
                delete(OwnedSetInventoryLine).where(
                    OwnedSetInventoryLine.set_part_inventory_line_id == existing.id
                )
            )
            target_session.delete(existing)
        target_session.flush()

    return line_map


def _copy_minifig_bom(
    target_session: Session,
    source_session: Session,
    source_minifig_id: int,
    target_minifig_id: int,
    stats: _CatalogImportStats,
    *,
    replace: bool,
) -> dict[int, int]:
    """Return map of source minifig_part_inventory_line.id -> target line id."""
    line_map: dict[int, int] = {}
    new_keys: set[tuple[int, int]] = set()

    source_lines = source_session.scalars(
        select(MinifigPartInventoryLine).where(
            MinifigPartInventoryLine.catalog_minifig_id == source_minifig_id
        )
    ).all()

    for source_line in source_lines:
        part = _upsert_part_from_source(
            target_session, source_session, source_line.part_id, stats
        )
        color = _upsert_color_from_source(
            target_session, source_session, source_line.color_id
        )
        if part is None or color is None:
            continue

        key = (part.id, color.id)
        new_keys.add(key)

        target_line = target_session.scalar(
            select(MinifigPartInventoryLine).where(
                MinifigPartInventoryLine.catalog_minifig_id == target_minifig_id,
                MinifigPartInventoryLine.part_id == part.id,
                MinifigPartInventoryLine.color_id == color.id,
            )
        )
        if target_line is None:
            target_line = MinifigPartInventoryLine(
                catalog_minifig_id=target_minifig_id,
                part_id=part.id,
                color_id=color.id,
                quantity=source_line.quantity,
                image_url=source_line.image_url,
                source=source_line.source,
                fetched_at=source_line.fetched_at,
            )
            target_session.add(target_line)
        else:
            target_line.quantity = source_line.quantity
            target_line.image_url = source_line.image_url
            target_line.fetched_at = source_line.fetched_at
        target_session.flush()
        _copy_part_color_catalog(
            target_session,
            source_session,
            source_part_id=source_line.part_id,
            source_color_id=source_line.color_id,
            target_part_id=part.id,
            target_color_id=color.id,
        )
        line_map[source_line.id] = target_line.id
        stats.inventory_lines_written += 1

    if replace:
        existing_lines = target_session.scalars(
            select(MinifigPartInventoryLine).where(
                MinifigPartInventoryLine.catalog_minifig_id == target_minifig_id
            )
        ).all()
        for existing in existing_lines:
            key = (existing.part_id, existing.color_id)
            if key in new_keys:
                continue
            target_session.execute(
                delete(OwnedSetInventoryLine).where(
                    OwnedSetInventoryLine.minifig_part_inventory_line_id == existing.id
                )
            )
            target_session.delete(existing)
        target_session.flush()

    return line_map


def _copy_minifig_inventory(
    target_session: Session,
    source_session: Session,
    source_catalog_id: int,
    target_catalog_id: int,
    stats: _CatalogImportStats,
    *,
    replace: bool,
) -> dict[int, int]:
    """Return map of source minifig_part_inventory_line.id -> target line id."""
    minifig_part_line_map: dict[int, int] = {}

    if replace:
        target_session.execute(
            delete(SetMinifigInventoryLine).where(
                SetMinifigInventoryLine.catalog_set_id == target_catalog_id
            )
        )
        target_session.flush()

    source_minifig_lines = source_session.scalars(
        select(SetMinifigInventoryLine).where(
            SetMinifigInventoryLine.catalog_set_id == source_catalog_id
        )
    ).all()

    for source_mf_line in source_minifig_lines:
        target_minifig = _upsert_minifig_from_source(
            target_session, source_session, source_mf_line.catalog_minifig_id
        )
        if target_minifig is None:
            continue

        target_session.add(
            SetMinifigInventoryLine(
                catalog_set_id=target_catalog_id,
                catalog_minifig_id=target_minifig.id,
                quantity=source_mf_line.quantity,
                source=source_mf_line.source,
                fetched_at=source_mf_line.fetched_at,
            )
        )
        target_session.flush()
        stats.inventory_lines_written += 1

        bom_map = _copy_minifig_bom(
            target_session,
            source_session,
            source_mf_line.catalog_minifig_id,
            target_minifig.id,
            stats,
            replace=replace,
        )
        minifig_part_line_map.update(bom_map)

    return minifig_part_line_map
