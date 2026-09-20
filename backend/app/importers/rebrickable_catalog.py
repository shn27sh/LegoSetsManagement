"""Upsert Rebrickable DTOs into ORM catalog tables."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    Color,
    MinifigPartInventoryLine,
    OwnedSetInventoryLine,
    Part,
    PartAlias,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
    Theme,
)
from app.importers.rebrickable_inventory_filters import (
    include_minifig_part_line,
    include_set_part_line,
)
from app.rebrickable.dto import (
    CatalogSetDTO,
    ColorDTO,
    MinifigPartLineDTO,
    PartDTO,
    SetMinifigLineDTO,
    SetPartLineDTO,
    ThemeDTO,
)
from app.domain.lego_set_number import from_rebrickable_set_num
from app.services.part_color_catalog_service import enrich_element_ids_for_part_color

SOURCE = "rebrickable"


def _stored_image_url(url: str | None, *, persist_image_urls: bool) -> str | None:
    return url if persist_image_urls else None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_theme(session: Session, dto: ThemeDTO, *, fetched_at: datetime) -> Theme:
    theme = session.scalar(select(Theme).where(Theme.external_id == dto.external_id))
    if theme is None:
        theme = Theme(
            external_id=dto.external_id,
            name=dto.name,
            source=SOURCE,
            fetched_at=fetched_at,
        )
        session.add(theme)
    else:
        theme.name = dto.name
        theme.fetched_at = fetched_at
    session.flush()
    return theme


def upsert_color(session: Session, dto: ColorDTO, *, fetched_at: datetime) -> Color:
    color = session.scalar(select(Color).where(Color.external_id == dto.external_id))
    if color is None:
        color = Color(
            external_id=dto.external_id,
            name=dto.name,
            rgb=dto.rgb,
            source=SOURCE,
            fetched_at=fetched_at,
        )
        session.add(color)
    else:
        color.name = dto.name
        color.rgb = dto.rgb
        color.fetched_at = fetched_at
    session.flush()
    return color


def upsert_part_counting(
    session: Session,
    dto: PartDTO,
    *,
    fetched_at: datetime,
    persist_image_urls: bool = True,
) -> tuple[Part, bool]:
    """Return (part, True if newly created)."""
    part = session.scalar(select(Part).where(Part.part_num == dto.part_num))
    created = part is None
    if created:
        part = Part(
            part_num=dto.part_num,
            name=dto.name,
            image_url=_stored_image_url(dto.image_url, persist_image_urls=persist_image_urls),
            source=SOURCE,
            source_ref=dto.part_num,
            fetched_at=fetched_at,
        )
        session.add(part)
    else:
        part.name = dto.name
        if persist_image_urls:
            part.image_url = dto.image_url
        part.fetched_at = fetched_at

    session.flush()

    for alias in dto.aliases:
        if alias == dto.part_num:
            continue
        exists = session.scalar(
            select(PartAlias.id).where(
                PartAlias.part_id == part.id,
                PartAlias.alias == alias,
                PartAlias.source == SOURCE,
            )
        )
        if exists is None:
            session.add(PartAlias(part_id=part.id, alias=alias, source=SOURCE))

    session.flush()
    return part, created


def _ensure_part_image_url_from_line(
    part: Part,
    line_image_url: str | None,
    *,
    persist_image_urls: bool,
) -> None:
    if persist_image_urls and part.image_url is None and line_image_url:
        part.image_url = line_image_url


def upsert_catalog_set(
    session: Session,
    dto: CatalogSetDTO,
    *,
    theme_id: int | None,
    fetched_at: datetime,
    persist_image_urls: bool = True,
    update_theme: bool = True,
    update_year: bool = True,
) -> CatalogSet:
    lsid = from_rebrickable_set_num(dto.set_num)
    catalog_set = session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
    )
    if catalog_set is None:
        catalog_set = CatalogSet(
            set_number=lsid.number,
            set_variant=lsid.variant,
            name=dto.name,
            year=dto.year,
            theme_id=theme_id,
            num_parts=dto.num_parts,
            image_url=_stored_image_url(dto.image_url, persist_image_urls=persist_image_urls),
            source=SOURCE,
            source_ref=dto.set_num,
            fetched_at=fetched_at,
        )
        session.add(catalog_set)
    else:
        catalog_set.name = dto.name
        if update_year:
            catalog_set.year = dto.year
        if update_theme:
            catalog_set.theme_id = theme_id
        catalog_set.num_parts = dto.num_parts
        if persist_image_urls:
            catalog_set.image_url = dto.image_url
        catalog_set.source = SOURCE
        catalog_set.source_ref = dto.set_num
        catalog_set.fetched_at = fetched_at
    session.flush()
    return catalog_set


def upsert_catalog_minifig(
    session: Session,
    dto: SetMinifigLineDTO,
    *,
    fetched_at: datetime,
    persist_image_urls: bool = True,
) -> CatalogMinifig:
    minifig = session.scalar(
        select(CatalogMinifig).where(CatalogMinifig.minifig_num == dto.minifig_num)
    )
    if minifig is None:
        minifig = CatalogMinifig(
            minifig_num=dto.minifig_num,
            name=dto.name,
            image_url=_stored_image_url(dto.image_url, persist_image_urls=persist_image_urls),
            source=SOURCE,
            fetched_at=fetched_at,
        )
        session.add(minifig)
    else:
        minifig.name = dto.name
        if persist_image_urls:
            minifig.image_url = dto.image_url
        minifig.fetched_at = fetched_at
    session.flush()
    return minifig


def replace_set_part_inventory(
    session: Session,
    catalog_set_id: int,
    lines: list[SetPartLineDTO],
    *,
    fetched_at: datetime,
    persist_image_urls: bool = True,
) -> tuple[int, int]:
    """Upsert set part lines; return (parts_upserted, lines_written)."""
    parts_upserted = 0
    lines_written = 0
    new_keys: set[tuple[int, int]] = set()

    line_image = lambda url: _stored_image_url(url, persist_image_urls=persist_image_urls)

    for line in lines:
        if not include_set_part_line(line):
            continue
        part, created = upsert_part_counting(
            session,
            line.part,
            fetched_at=fetched_at,
            persist_image_urls=persist_image_urls,
        )
        _ensure_part_image_url_from_line(
            part,
            line.image_url,
            persist_image_urls=persist_image_urls,
        )
        if created:
            parts_upserted += 1
        color = upsert_color(session, line.color, fetched_at=fetched_at)

        key = (part.id, color.id)
        new_keys.add(key)

        existing = session.scalar(
            select(SetPartInventoryLine).where(
                SetPartInventoryLine.catalog_set_id == catalog_set_id,
                SetPartInventoryLine.part_id == part.id,
                SetPartInventoryLine.color_id == color.id,
            )
        )
        source_ref = str(line.inventory_id) if line.inventory_id is not None else None
        stored_line_image = line_image(line.image_url)
        if existing is None:
            existing = SetPartInventoryLine(
                catalog_set_id=catalog_set_id,
                part_id=part.id,
                color_id=color.id,
                quantity=line.quantity,
                image_url=stored_line_image,
                source=SOURCE,
                source_ref=source_ref,
                fetched_at=fetched_at,
            )
            session.add(existing)
        else:
            existing.quantity = line.quantity
            if persist_image_urls:
                existing.image_url = line.image_url
            existing.source_ref = source_ref
            existing.fetched_at = fetched_at
        session.flush()
        enrich_element_ids_for_part_color(
            session,
            part.id,
            color.id,
            part_num=part.part_num,
            color_external_id=color.external_id,
            aliases=line.part.aliases,
        )
        lines_written += 1

    existing_lines = session.scalars(
        select(SetPartInventoryLine).where(
            SetPartInventoryLine.catalog_set_id == catalog_set_id
        )
    ).all()
    for existing in existing_lines:
        key = (existing.part_id, existing.color_id)
        if key in new_keys:
            continue
        session.execute(
            delete(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.set_part_inventory_line_id == existing.id
            )
        )
        session.delete(existing)

    session.flush()
    return parts_upserted, lines_written


def replace_set_minifig_inventory(
    session: Session,
    catalog_set_id: int,
    minifigs: list[SetMinifigLineDTO],
    *,
    fetched_at: datetime,
) -> int:
    session.execute(
        delete(SetMinifigInventoryLine).where(
            SetMinifigInventoryLine.catalog_set_id == catalog_set_id
        )
    )
    lines_written = 0
    for dto in minifigs:
        catalog_minifig = upsert_catalog_minifig(session, dto, fetched_at=fetched_at)
        session.add(
            SetMinifigInventoryLine(
                catalog_set_id=catalog_set_id,
                catalog_minifig_id=catalog_minifig.id,
                quantity=dto.quantity,
                source=SOURCE,
                fetched_at=fetched_at,
            )
        )
        lines_written += 1
    session.flush()
    return lines_written


def replace_minifig_part_inventory(
    session: Session,
    catalog_minifig_id: int,
    lines: list[MinifigPartLineDTO],
    *,
    fetched_at: datetime,
    persist_image_urls: bool = True,
) -> tuple[int, int]:
    parts_upserted = 0
    lines_written = 0
    new_keys: set[tuple[int, int]] = set()

    line_image = lambda url: _stored_image_url(url, persist_image_urls=persist_image_urls)

    for line in lines:
        if not include_minifig_part_line(line):
            continue
        part, created = upsert_part_counting(
            session,
            line.part,
            fetched_at=fetched_at,
            persist_image_urls=persist_image_urls,
        )
        _ensure_part_image_url_from_line(
            part,
            line.image_url,
            persist_image_urls=persist_image_urls,
        )
        if created:
            parts_upserted += 1
        color = upsert_color(session, line.color, fetched_at=fetched_at)
        key = (part.id, color.id)
        new_keys.add(key)

        existing = session.scalar(
            select(MinifigPartInventoryLine).where(
                MinifigPartInventoryLine.catalog_minifig_id == catalog_minifig_id,
                MinifigPartInventoryLine.part_id == part.id,
                MinifigPartInventoryLine.color_id == color.id,
            )
        )
        stored_line_image = line_image(line.image_url)
        if existing is None:
            existing = MinifigPartInventoryLine(
                catalog_minifig_id=catalog_minifig_id,
                part_id=part.id,
                color_id=color.id,
                quantity=line.quantity,
                image_url=stored_line_image,
                source=SOURCE,
                fetched_at=fetched_at,
            )
            session.add(existing)
        else:
            existing.quantity = line.quantity
            if persist_image_urls:
                existing.image_url = line.image_url
            existing.fetched_at = fetched_at
        session.flush()
        enrich_element_ids_for_part_color(
            session,
            part.id,
            color.id,
            part_num=part.part_num,
            color_external_id=color.external_id,
            aliases=line.part.aliases,
        )
        lines_written += 1

    existing_lines = session.scalars(
        select(MinifigPartInventoryLine).where(
            MinifigPartInventoryLine.catalog_minifig_id == catalog_minifig_id
        )
    ).all()
    for existing in existing_lines:
        key = (existing.part_id, existing.color_id)
        if key in new_keys:
            continue
        session.execute(
            delete(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.minifig_part_inventory_line_id == existing.id
            )
        )
        session.delete(existing)

    session.flush()
    return parts_upserted, lines_written
