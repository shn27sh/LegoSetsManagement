"""remove spare and alternate inventory flags

Revision ID: f2a8b3c19d60
Revises: e1b4c7d29f50
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a8b3c19d60"
down_revision: Union[str, None] = "e1b4c7d29f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            DELETE FROM owned_set_inventory_lines
            WHERE set_part_inventory_line_id IN (
                SELECT id FROM set_part_inventory_lines
                WHERE is_spare = 1 OR is_alternate = 1
            )
            """
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM set_part_inventory_lines WHERE is_spare = 1 OR is_alternate = 1"
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM owned_set_inventory_lines
            WHERE minifig_part_inventory_line_id IN (
                SELECT id FROM minifig_part_inventory_lines
                WHERE is_spare = 1
            )
            """
        )
    )
    conn.execute(
        sa.text("DELETE FROM minifig_part_inventory_lines WHERE is_spare = 1")
    )

    with op.batch_alter_table("set_part_inventory_lines") as batch_op:
        batch_op.drop_constraint(
            "uq_set_part_inventory_lines_natural_key",
            type_="unique",
        )
        batch_op.drop_column("is_spare")
        batch_op.drop_column("is_alternate")
        batch_op.create_unique_constraint(
            "uq_set_part_inventory_lines_natural_key",
            ["catalog_set_id", "part_id", "color_id"],
        )

    with op.batch_alter_table("minifig_part_inventory_lines") as batch_op:
        batch_op.drop_constraint(
            "uq_minifig_part_inventory_lines_natural_key",
            type_="unique",
        )
        batch_op.drop_column("is_spare")
        batch_op.create_unique_constraint(
            "uq_minifig_part_inventory_lines_natural_key",
            ["catalog_minifig_id", "part_id", "color_id"],
        )


def downgrade() -> None:
    raise NotImplementedError("f2a8b3c19d60 downgrade is not supported")
