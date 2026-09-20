"""element image blobs keyed by LEGO element id

Revision ID: e7a1c4d90231
Revises: d4f2a19b7c30
Create Date: 2026-05-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1c4d90231"
down_revision: Union[str, None] = "d4f2a19b7c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "element_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=False),
        sa.Column("image_blob", sa.LargeBinary(), nullable=True),
        sa.Column("image_content_type", sa.Text(), nullable=True),
        sa.Column("image_byte_size", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("element_id"),
    )
    op.create_index("ix_element_images_element_id", "element_images", ["element_id"])


def downgrade() -> None:
    op.drop_index("ix_element_images_element_id", table_name="element_images")
    op.drop_table("element_images")
