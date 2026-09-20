"""phase 9 owned set inventory lines

Revision ID: d9f3a2b18e40
Revises: b2c8e4f91a10
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9f3a2b18e40"
down_revision: Union[str, Sequence[str], None] = "b2c8e4f91a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "owned_set_inventory_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owned_set_id", sa.Integer(), nullable=False),
        sa.Column("set_part_inventory_line_id", sa.Integer(), nullable=True),
        sa.Column("minifig_part_inventory_line_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("quantity_missing", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "(set_part_inventory_line_id IS NOT NULL AND minifig_part_inventory_line_id IS NULL) "
            "OR (set_part_inventory_line_id IS NULL AND minifig_part_inventory_line_id IS NOT NULL)",
            name="ck_owned_set_inventory_lines_one_line_ref",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_owned_set_inventory_lines_quantity"),
        sa.CheckConstraint(
            "quantity_missing >= 0 AND quantity_missing <= quantity",
            name="ck_owned_set_inventory_lines_missing",
        ),
        sa.ForeignKeyConstraint(["owned_set_id"], ["owned_sets.id"], ondelete="CASCADE"),
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
        "ix_owned_set_inventory_lines_owned_set_id",
        "owned_set_inventory_lines",
        ["owned_set_id"],
    )
    op.create_index(
        "uq_owned_set_inventory_lines_owned_set_part",
        "owned_set_inventory_lines",
        ["owned_set_id", "set_part_inventory_line_id"],
        unique=True,
        sqlite_where=sa.text("set_part_inventory_line_id IS NOT NULL"),
    )
    op.create_index(
        "uq_owned_set_inventory_lines_owned_minifig_part",
        "owned_set_inventory_lines",
        ["owned_set_id", "minifig_part_inventory_line_id"],
        unique=True,
        sqlite_where=sa.text("minifig_part_inventory_line_id IS NOT NULL"),
    )

    conn = op.get_bind()

    owned_sets = conn.execute(sa.text("SELECT id, catalog_set_id FROM owned_sets")).fetchall()
    for owned_set_id, catalog_set_id in owned_sets:
        set_part_lines = conn.execute(
            sa.text(
                "SELECT id, quantity FROM set_part_inventory_lines "
                "WHERE catalog_set_id = :catalog_set_id"
            ),
            {"catalog_set_id": catalog_set_id},
        ).fetchall()
        for line_id, quantity in set_part_lines:
            missing_qty = conn.execute(
                sa.text(
                    "SELECT quantity_missing FROM missing_items "
                    "WHERE owned_set_id = :owned_set_id "
                    "AND set_part_inventory_line_id = :line_id"
                ),
                {"owned_set_id": owned_set_id, "line_id": line_id},
            ).scalar_one_or_none()
            conn.execute(
                sa.text(
                    "INSERT INTO owned_set_inventory_lines "
                    "(owned_set_id, set_part_inventory_line_id, minifig_part_inventory_line_id, "
                    "quantity, quantity_missing) "
                    "VALUES (:owned_set_id, :line_id, NULL, :quantity, :missing)"
                ),
                {
                    "owned_set_id": owned_set_id,
                    "line_id": line_id,
                    "quantity": quantity,
                    "missing": missing_qty or 0,
                },
            )

        minifig_ids = conn.execute(
            sa.text(
                "SELECT catalog_minifig_id FROM set_minifig_inventory_lines "
                "WHERE catalog_set_id = :catalog_set_id"
            ),
            {"catalog_set_id": catalog_set_id},
        ).fetchall()
        for (minifig_id,) in minifig_ids:
            bom_lines = conn.execute(
                sa.text(
                    "SELECT id, quantity FROM minifig_part_inventory_lines "
                    "WHERE catalog_minifig_id = :minifig_id"
                ),
                {"minifig_id": minifig_id},
            ).fetchall()
            for line_id, quantity in bom_lines:
                missing_qty = conn.execute(
                    sa.text(
                        "SELECT quantity_missing FROM missing_items "
                        "WHERE owned_set_id = :owned_set_id "
                        "AND minifig_part_inventory_line_id = :line_id"
                    ),
                    {"owned_set_id": owned_set_id, "line_id": line_id},
                ).scalar_one_or_none()
                conn.execute(
                    sa.text(
                        "INSERT INTO owned_set_inventory_lines "
                        "(owned_set_id, set_part_inventory_line_id, minifig_part_inventory_line_id, "
                        "quantity, quantity_missing) "
                        "VALUES (:owned_set_id, NULL, :line_id, :quantity, :missing)"
                    ),
                    {
                        "owned_set_id": owned_set_id,
                        "line_id": line_id,
                        "quantity": quantity,
                        "missing": missing_qty or 0,
                    },
                )

    with op.batch_alter_table("missing_items") as batch_op:
        batch_op.add_column(
            sa.Column("owned_set_inventory_line_id", sa.Integer(), nullable=True)
        )

    conn.execute(
        sa.text(
            """
            UPDATE missing_items
            SET owned_set_inventory_line_id = (
                SELECT osil.id
                FROM owned_set_inventory_lines osil
                WHERE osil.owned_set_id = missing_items.owned_set_id
                  AND (
                    osil.set_part_inventory_line_id = missing_items.set_part_inventory_line_id
                    OR osil.minifig_part_inventory_line_id =
                       missing_items.minifig_part_inventory_line_id
                  )
            )
            """
        )
    )

    conn.execute(sa.text("DELETE FROM missing_items WHERE owned_set_inventory_line_id IS NULL"))

    with op.batch_alter_table("missing_items") as batch_op:
        batch_op.drop_index("uq_missing_items_owned_set_part_line")
        batch_op.drop_index("uq_missing_items_owned_minifig_part_line")
        batch_op.drop_constraint("ck_missing_items_one_line_ref", type_="check")
        batch_op.drop_constraint("ck_missing_items_quantity_missing", type_="check")
        batch_op.drop_column("set_part_inventory_line_id")
        batch_op.drop_column("minifig_part_inventory_line_id")
        batch_op.drop_column("quantity_missing")
        batch_op.alter_column(
            "owned_set_inventory_line_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_missing_items_owned_set_inventory_line",
            "owned_set_inventory_lines",
            ["owned_set_inventory_line_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "uq_missing_items_owned_set_inventory_line",
            ["owned_set_inventory_line_id"],
            unique=True,
        )


def downgrade() -> None:
    raise NotImplementedError("Phase 9 downgrade is not supported")
