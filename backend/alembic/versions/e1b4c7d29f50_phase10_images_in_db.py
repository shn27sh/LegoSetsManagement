"""phase 10 images in sqlite blobs

Revision ID: e1b4c7d29f50
Revises: d9f3a2b18e40
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1b4c7d29f50"
down_revision: Union[str, None] = "d9f3a2b18e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("parts", "catalog_sets"):
        op.add_column(table, sa.Column("image_blob", sa.LargeBinary(), nullable=True))
        op.add_column(table, sa.Column("image_content_type", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("image_byte_size", sa.Integer(), nullable=True))

    with op.batch_alter_table("missing_items") as batch_op:
        batch_op.drop_column("image_path")


def downgrade() -> None:
    raise NotImplementedError("Phase 10 downgrade is not supported")
