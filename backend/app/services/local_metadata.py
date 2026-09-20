"""Update missing set metadata from local Rebrickable CSV exports."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CatalogSet, OwnedSet
from app.domain.lego_set_number import from_rebrickable_set_num
from app.importers.rebrickable_catalog import upsert_theme, utc_now
from app.services.theme_catalog import load_theme_catalog
from app.utils.age import parse_age_value


@dataclass(frozen=True)
class LocalMetadataUpdateResult:
    owned_set_ages_updated: int
    catalog_themes_updated: int
    age_values_available: int
    theme_values_available: int


def default_age_csv_path() -> Path:
    configured = os.environ.get("AGE_CSV_PATH")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "age.csv"


def default_sets_csv_path() -> Path:
    configured = os.environ.get("SETS_CSV_PATH")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "sets.csv"


def _load_ages(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}
    values: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            set_text = (row.get("set_number") or "").strip()
            age = parse_age_value(row.get("age"))
            if not set_text or age is None:
                continue
            try:
                set_number = int(set_text)
            except ValueError:
                continue
            values[set_number] = age
    return values


def _load_theme_ids(path: Path) -> dict[tuple[int, int], int]:
    if not path.exists():
        return {}
    values: dict[tuple[int, int], int] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            set_num = (row.get("set_num") or "").strip()
            theme_text = (row.get("theme_id") or "").strip()
            if not set_num or not theme_text:
                continue
            try:
                lsid = from_rebrickable_set_num(set_num)
                theme_id = int(theme_text)
            except ValueError:
                continue
            values[(lsid.number, lsid.variant)] = theme_id
    return values


def update_missing_local_metadata(
    session: Session,
    *,
    age_csv_path: str | None = None,
    sets_csv_path: str | None = None,
    themes_csv_path: str | None = None,
) -> LocalMetadataUpdateResult:
    ages = _load_ages(Path(age_csv_path) if age_csv_path else default_age_csv_path())
    theme_ids = _load_theme_ids(
        Path(sets_csv_path) if sets_csv_path else default_sets_csv_path()
    )
    theme_catalog = load_theme_catalog(themes_csv_path)
    fetched_at = utc_now()

    age_updates = 0
    owned_sets = session.scalars(
        select(OwnedSet).join(CatalogSet, OwnedSet.catalog_set_id == CatalogSet.id)
    ).all()
    for owned in owned_sets:
        if owned.age is not None:
            continue
        set_number = owned.catalog_set.set_number
        age = ages.get(set_number)
        if age is None:
            continue
        owned.age = age
        age_updates += 1

    theme_updates = 0
    catalog_sets = session.scalars(select(CatalogSet)).all()
    for catalog in catalog_sets:
        if catalog.theme_id is not None:
            continue
        theme_id = theme_ids.get((catalog.set_number, catalog.set_variant))
        if theme_id is None:
            continue
        theme_dto = theme_catalog.display_theme_for(theme_id)
        if theme_dto is None:
            continue
        theme = upsert_theme(session, theme_dto, fetched_at=fetched_at)
        catalog.theme_id = theme.id
        theme_updates += 1

    session.flush()
    return LocalMetadataUpdateResult(
        owned_set_ages_updated=age_updates,
        catalog_themes_updated=theme_updates,
        age_values_available=len(ages),
        theme_values_available=len(theme_ids),
    )
