"""Alembic migration smoke tests."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_all_tables(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config("alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    engine.dispose()

    expected = {
        "alembic_version",
        "themes",
        "catalog_sets",
        "owned_sets",
        "parts",
        "part_aliases",
        "colors",
        "set_part_inventory_lines",
        "catalog_minifigs",
        "set_minifig_inventory_lines",
        "minifig_part_inventory_lines",
        "missing_items",
    }
    assert expected <= table_names
