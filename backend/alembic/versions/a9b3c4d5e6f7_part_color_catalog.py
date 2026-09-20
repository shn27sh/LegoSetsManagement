"""part_color canonical element ids

Revision ID: a9b3c4d5e6f7
Revises: f8c2d41a6b90
Create Date: 2026-06-15

"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b3c4d5e6f7"
down_revision: Union[str, None] = "f8c2d41a6b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _build_equivalence_classes(conn) -> dict[int, set[int]]:
    parts = conn.execute(sa.text("SELECT id, part_num FROM parts")).fetchall()
    part_num_to_id = {part_num: part_id for part_id, part_num in parts}
    id_to_num = {part_id: part_num for part_id, part_num in parts}

    alias_rows = conn.execute(
        sa.text("SELECT part_id, alias FROM part_aliases")
    ).fetchall()
    adjacency: dict[int, set[int]] = defaultdict(set)
    for part_id, _alias in alias_rows:
        adjacency[part_id].add(part_id)

    for part_id, alias in alias_rows:
        linked = part_num_to_id.get(alias)
        if linked is not None:
            adjacency[part_id].add(linked)
            adjacency[linked].add(part_id)

    for part_id, part_num in parts:
        adjacency[part_id].add(part_id)

    classes: dict[int, set[int]] = {}
    visited: set[int] = set()

    def dfs(start: int) -> set[int]:
        stack = [start]
        component: set[int] = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in adjacency.get(node, {node}):
                if neighbor not in visited:
                    stack.append(neighbor)
        return component

    for part_id in id_to_num:
        if part_id in visited:
            continue
        component = dfs(part_id)
        anchor = min(component)
        for member in component:
            classes[member] = component
            _ = anchor
    return classes


def _backfill_part_color_keys(conn) -> None:
    classes = _build_equivalence_classes(conn)
    now = datetime.now(timezone.utc).isoformat()

    line_elements: dict[tuple[int, int], set[str]] = defaultdict(set)

    set_rows = conn.execute(
        sa.text(
            """
            SELECT ile.element_id, spl.part_id, spl.color_id
            FROM inventory_line_element_ids ile
            JOIN set_part_inventory_lines spl
              ON ile.set_part_inventory_line_id = spl.id
            """
        )
    ).fetchall()
    for element_id, part_id, color_id in set_rows:
        line_elements[(part_id, color_id)].add(element_id)

    minifig_rows = conn.execute(
        sa.text(
            """
            SELECT ile.element_id, mpl.part_id, mpl.color_id
            FROM inventory_line_element_ids ile
            JOIN minifig_part_inventory_lines mpl
              ON ile.minifig_part_inventory_line_id = mpl.id
            """
        )
    ).fetchall()
    for element_id, part_id, color_id in minifig_rows:
        line_elements[(part_id, color_id)].add(element_id)

    canonical: dict[tuple[int, int], set[str]] = defaultdict(set)
    for (part_id, color_id), element_ids in line_elements.items():
        class_ids = classes.get(part_id, {part_id})
        anchor = min(class_ids)
        for element_id in element_ids:
            canonical[(anchor, color_id)].add(element_id)

    key_ids: dict[tuple[int, int], int] = {}
    for (anchor, color_id), element_ids in sorted(canonical.items()):
        result = conn.execute(
            sa.text(
                """
                INSERT INTO part_color_keys (anchor_part_id, color_id, source, updated_at)
                VALUES (:anchor_part_id, :color_id, 'migration', :updated_at)
                """
            ),
            {
                "anchor_part_id": anchor,
                "color_id": color_id,
                "updated_at": now,
            },
        )
        key_id = result.lastrowid
        key_ids[(anchor, color_id)] = key_id
        for element_id in sorted(element_ids):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO part_color_element_ids (part_color_key_id, element_id)
                    VALUES (:key_id, :element_id)
                    """
                ),
                {"key_id": key_id, "element_id": element_id},
            )


def upgrade() -> None:
    op.create_table(
        "part_color_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("anchor_part_id", sa.Integer(), nullable=False),
        sa.Column("color_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["anchor_part_id"], ["parts.id"]),
        sa.ForeignKeyConstraint(["color_id"], ["colors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "anchor_part_id", "color_id", name="uq_part_color_keys_anchor_color"
        ),
    )
    op.create_index(
        "ix_part_color_keys_color_id",
        "part_color_keys",
        ["color_id"],
    )
    op.create_table(
        "part_color_element_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("part_color_key_id", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["part_color_key_id"], ["part_color_keys.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "part_color_key_id",
            "element_id",
            name="uq_part_color_element_ids_key_element",
        ),
    )
    op.create_index(
        "ix_part_color_element_ids_element_id",
        "part_color_element_ids",
        ["element_id"],
    )

    _backfill_part_color_keys(op.get_bind())

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


def downgrade() -> None:
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

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT pck.anchor_part_id, pck.color_id, pce.element_id
            FROM part_color_element_ids pce
            JOIN part_color_keys pck ON pck.id = pce.part_color_key_id
            """
        )
    ).fetchall()
    classes = _build_equivalence_classes(conn)
    for anchor_part_id, color_id, element_id in rows:
        class_ids = classes.get(anchor_part_id, {anchor_part_id})
        set_lines = conn.execute(
            sa.text(
                """
                SELECT id FROM set_part_inventory_lines
                WHERE part_id IN :part_ids AND color_id = :color_id
                """
            ).bindparams(sa.bindparam("part_ids", expanding=True)),
            {"part_ids": list(class_ids), "color_id": color_id},
        ).fetchall()
        for (line_id,) in set_lines:
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
        minifig_lines = conn.execute(
            sa.text(
                """
                SELECT id FROM minifig_part_inventory_lines
                WHERE part_id IN :part_ids AND color_id = :color_id
                """
            ).bindparams(sa.bindparam("part_ids", expanding=True)),
            {"part_ids": list(class_ids), "color_id": color_id},
        ).fetchall()
        for (line_id,) in minifig_lines:
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

    op.drop_index(
        "ix_part_color_element_ids_element_id",
        table_name="part_color_element_ids",
    )
    op.drop_table("part_color_element_ids")
    op.drop_index("ix_part_color_keys_color_id", table_name="part_color_keys")
    op.drop_table("part_color_keys")
