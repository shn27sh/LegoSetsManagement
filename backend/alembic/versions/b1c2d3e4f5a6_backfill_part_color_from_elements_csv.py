"""backfill part_color element ids from elements.csv

Revision ID: b1c2d3e4f5a6
Revises: a9b3c4d5e6f7
Create Date: 2026-06-15

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from app.services.part_color_catalog_service import backfill_part_color_element_ids_from_csv

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        backfill_part_color_element_ids_from_csv(session)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    pass
