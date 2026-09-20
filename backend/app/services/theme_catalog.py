"""Import-time LEGO theme lookup from Rebrickable's themes.csv."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.rebrickable.dto import ThemeDTO


@dataclass(frozen=True)
class ThemeCatalogRow:
    external_id: int
    name: str
    parent_id: int | None


@dataclass(frozen=True)
class ThemeCatalog:
    by_id: dict[int, ThemeCatalogRow]

    def display_theme_for(self, theme_id: int) -> ThemeDTO | None:
        row = self.by_id.get(theme_id)
        if row is None:
            return None
        if row.parent_id is not None:
            parent = self.by_id.get(row.parent_id)
            if parent is not None:
                row = parent
        return ThemeDTO(external_id=row.external_id, name=row.name)


def default_themes_csv_path() -> Path:
    configured = os.environ.get("THEMES_CSV_PATH")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "themes.csv"


@lru_cache(maxsize=4)
def load_theme_catalog(path_text: str | None = None) -> ThemeCatalog:
    path = Path(path_text) if path_text else default_themes_csv_path()
    if not path.exists():
        return ThemeCatalog(by_id={})

    rows: dict[int, ThemeCatalogRow] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            theme_text = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()
            parent_text = (row.get("parent_id") or "").strip()
            if not theme_text or not name:
                continue
            try:
                theme_id = int(theme_text)
                parent_id = int(parent_text) if parent_text else None
            except ValueError:
                continue
            rows[theme_id] = ThemeCatalogRow(
                external_id=theme_id,
                name=name,
                parent_id=parent_id,
            )

    return ThemeCatalog(by_id=rows)


def clear_theme_catalog_cache() -> None:
    load_theme_catalog.cache_clear()


def display_theme_for(theme_id: int) -> ThemeDTO | None:
    return load_theme_catalog().display_theme_for(theme_id)
