"""minifig image blobs

Revision ID: d4f2a19b7c30
Revises: c6d7e8f91a23
Create Date: 2026-05-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f2a19b7c30"
down_revision: Union[str, None] = "c6d7e8f91a23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalog_minifigs", sa.Column("image_blob", sa.LargeBinary(), nullable=True))
    op.add_column("catalog_minifigs", sa.Column("image_content_type", sa.Text(), nullable=True))
    op.add_column("catalog_minifigs", sa.Column("image_byte_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_minifigs", "image_byte_size")
    op.drop_column("catalog_minifigs", "image_content_type")
    op.drop_column("catalog_minifigs", "image_blob")
