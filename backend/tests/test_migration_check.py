"""Database migration gate tests."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.db.migration_check import (
    DatabaseMigrationError,
    ensure_database_at_head,
    get_alembic_head_revision,
)


def test_get_alembic_head_revision() -> None:
    head = get_alembic_head_revision()
    assert head


def test_ensure_database_at_head_passes_when_migrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migrated.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("SKIP_DB_MIGRATION_CHECK", raising=False)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    ensure_database_at_head(database_url)


def test_migration_creates_part_color_catalog_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "part_color.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        key_columns = {
            column["name"] for column in inspect(engine).get_columns("part_color_keys")
        }
        element_columns = {
            column["name"]
            for column in inspect(engine).get_columns("part_color_element_ids")
        }
    finally:
        engine.dispose()
    assert {
        "id",
        "anchor_part_id",
        "color_id",
        "source",
        "updated_at",
    }.issubset(key_columns)
    assert {"id", "part_color_key_id", "element_id"}.issubset(element_columns)


def test_part_color_migration_backfills_alias_class_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "part_color_backfill.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "f8c2d41a6b90")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO parts (id, part_num, name, source, source_ref, fetched_at)
                VALUES
                  (1, '4079', 'Part A', 'test', '4079', '2026-06-15T00:00:00+00:00'),
                  (2, '4079b', 'Part B', 'test', '4079b', '2026-06-15T00:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO part_aliases (part_id, alias, source)
                VALUES (2, '4079', 'rebrickable')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO colors (id, external_id, name, source, fetched_at)
                VALUES (1, 70, 'Reddish Brown', 'test', '2026-06-15T00:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO catalog_minifigs (id, minifig_num, name, source, fetched_at)
                VALUES (1, 'cop001', 'Officer', 'test', '2026-06-15T00:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO minifig_part_inventory_lines
                  (id, catalog_minifig_id, part_id, color_id, quantity, source, fetched_at)
                VALUES
                  (1, 1, 1, 1, 1, 'test', '2026-06-15T00:00:00+00:00'),
                  (2, 1, 2, 1, 1, 'test', '2026-06-15T00:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO inventory_line_element_ids
                  (minifig_part_inventory_line_id, element_id)
                VALUES
                  (1, '4211206'),
                  (2, '6127738')
                """
            )
        )

    command.upgrade(config, "head")

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT pck.anchor_part_id, pck.color_id, pck.source, pce.element_id
                FROM part_color_keys pck
                JOIN part_color_element_ids pce ON pce.part_color_key_id = pck.id
                ORDER BY pce.element_id
                """
            )
        ).fetchall()
        table_names = set(inspect(conn).get_table_names())
    engine.dispose()

    assert rows == [
        (1, 1, "migration", "4211206"),
        (1, 1, "migration", "6127738"),
    ]
    assert "inventory_line_element_ids" not in table_names


def test_migration_creates_part_image_user_removed_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "part_flag.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        part_columns = {c["name"] for c in inspect(engine).get_columns("parts")}
    finally:
        engine.dispose()
    assert "part_image_user_removed" in part_columns


def test_ensure_database_at_head_fails_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.delenv("SKIP_DB_MIGRATION_CHECK", raising=False)

    with pytest.raises(DatabaseMigrationError, match="no Alembic revision"):
        ensure_database_at_head(database_url)
