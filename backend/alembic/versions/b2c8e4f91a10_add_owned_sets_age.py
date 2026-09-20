"""add owned_sets age

Revision ID: b2c8e4f91a10
Revises: 0a47cc7879de
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c8e4f91a10"
down_revision: Union[str, Sequence[str], None] = "0a47cc7879de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("owned_sets", sa.Column("age", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("owned_sets", "age")
