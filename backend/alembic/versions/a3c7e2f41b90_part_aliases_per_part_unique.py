"""part_aliases unique per part_id

Revision ID: a3c7e2f41b90
Revises: f2a8b3c19d60
Create Date: 2026-05-15

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a3c7e2f41b90"
down_revision: Union[str, None] = "f2a8b3c19d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("part_aliases", schema=None) as batch_op:
        batch_op.drop_constraint("uq_part_aliases_alias_source", type_="unique")
        batch_op.create_unique_constraint(
            "uq_part_aliases_part_alias_source",
            ["part_id", "alias", "source"],
        )


def downgrade() -> None:
    with op.batch_alter_table("part_aliases", schema=None) as batch_op:
        batch_op.drop_constraint("uq_part_aliases_part_alias_source", type_="unique")
        batch_op.create_unique_constraint(
            "uq_part_aliases_alias_source",
            ["alias", "source"],
        )
