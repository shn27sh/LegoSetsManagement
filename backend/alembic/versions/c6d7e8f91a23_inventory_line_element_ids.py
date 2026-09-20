"""inventory line element ids

Revision ID: c6d7e8f91a23
Revises: b4e5f6a71c02
Create Date: 2026-05-16

"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f91a23"
down_revision: Union[str, None] = "b4e5f6a71c02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _elements_csv_path() -> Path:
    configured = os.environ.get("ELEMENTS_CSV_PATH")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "elements.csv"


def _load_element_ids() -> dict[tuple[str, int], list[str]]:
    path = _elements_csv_path()
    if not path.exists():
        return {}

    values: dict[tuple[str, int], list[str]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            part_num = (row.get("part_num") or "").strip()
            element_id = (row.get("element_id") or "").strip()
            color_text = (row.get("color_id") or "").strip()
            if not part_num or not element_id or not color_text:
                continue
            try:
                color_id = int(color_text)
            except ValueError:
                continue
            key = (part_num, color_id)
            if element_id not in values[key]:
                values[key].append(element_id)
    return values


def _insert_element_ids(conn, element_ids: dict[tuple[str, int], list[str]]) -> None:
    if not element_ids:
        return

    set_rows = conn.execute(
        sa.text(
            """
            SELECT spl.id, p.part_num, c.external_id
            FROM set_part_inventory_lines spl
            JOIN parts p ON spl.part_id = p.id
            JOIN colors c ON spl.color_id = c.id
            """
        )
    ).fetchall()
    for line_id, part_num, color_external_id in set_rows:
        for element_id in element_ids.get((part_num, color_external_id), []):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO inventory_line_element_ids
                    (set_part_inventory_line_id, minifig_part_inventory_line_id, element_id)
                    VALUES (:line_id, NULL, :element_id)
                    """
                ),
                {"line_id": line_id, "element_id": element_id},
            )

    minifig_rows = conn.execute(
        sa.text(
            """
            SELECT mpl.id, p.part_num, c.external_id
            FROM minifig_part_inventory_lines mpl
            JOIN parts p ON mpl.part_id = p.id
            JOIN colors c ON mpl.color_id = c.id
            """
        )
    ).fetchall()
    for line_id, part_num, color_external_id in minifig_rows:
        for element_id in element_ids.get((part_num, color_external_id), []):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO inventory_line_element_ids
                    (set_part_inventory_line_id, minifig_part_inventory_line_id, element_id)
                    VALUES (NULL, :line_id, :element_id)
                    """
                ),
                {"line_id": line_id, "element_id": element_id},
            )


def upgrade() -> None:
    op.create_table(
        "inventory_line_element_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_part_inventory_line_id", sa.Integer(), nullable=True),
        sa.Column("minifig_part_inventory_line_id", sa.Integer(), nullable=True),
        sa.Column("element_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "(set_part_inventory_line_id IS NOT NULL AND minifig_part_inventory_line_id IS NULL) "
            "OR (set_part_inventory_line_id IS NULL AND minifig_part_inventory_line_id IS NOT NULL)",
            name="ck_inventory_line_element_ids_one_line_ref",
        ),
        sa.ForeignKeyConstraint(
            ["set_part_inventory_line_id"],
            ["set_part_inventory_lines.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["minifig_part_inventory_line_id"],
            ["minifig_part_inventory_lines.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_inventory_line_element_ids_set_line_element",
        "inventory_line_element_ids",
        ["set_part_inventory_line_id", "element_id"],
        unique=True,
        sqlite_where=sa.text("set_part_inventory_line_id IS NOT NULL"),
    )
    op.create_index(
        "uq_inventory_line_element_ids_minifig_line_element",
        "inventory_line_element_ids",
        ["minifig_part_inventory_line_id", "element_id"],
        unique=True,
        sqlite_where=sa.text("minifig_part_inventory_line_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_line_element_ids_element_id",
        "inventory_line_element_ids",
        ["element_id"],
    )

    _insert_element_ids(op.get_bind(), _load_element_ids())


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_line_element_ids_element_id",
        table_name="inventory_line_element_ids",
    )
    op.drop_index(
        "uq_inventory_line_element_ids_minifig_line_element",
        table_name="inventory_line_element_ids",
    )
    op.drop_index(
        "uq_inventory_line_element_ids_set_line_element",
        table_name="inventory_line_element_ids",
    )
    op.drop_table("inventory_line_element_ids")
