"""part_image_user_removed on parts

Revision ID: f8c2d41a6b90
Revises: e7a1c4d90231
Create Date: 2026-05-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8c2d41a6b90"
down_revision: Union[str, None] = "e7a1c4d90231"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parts",
        sa.Column(
            "part_image_user_removed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("parts", "part_image_user_removed")
