"""catalog_sets: integer set_number + variant (Rebrickable suffix)

Revision ID: b4e5f6a71c02
Revises: a3c7e2f41b90

"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "b4e5f6a71c02"
down_revision: Union[str, None] = "a3c7e2f41b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _migrate_legacy_set_num(set_num: str) -> tuple[int, int]:
    """Parse old TEXT set_num; Rebrickable form is ``\\d+-\\d+`` or legacy ``\\d+``."""
    s = set_num.strip()
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", s)
    if not m:
        raise ValueError(f"unmigratable catalog_sets.set_num: {set_num!r}")
    n = int(m.group(1))
    v = int(m.group(2)) if m.group(2) else 1
    return n, v


def _column_names(conn, table: str) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _uq_catalog_pair_exists(conn) -> bool:
    for uc in inspect(conn).get_unique_constraints("catalog_sets"):
        if uc.get("name") == "uq_catalog_sets_number_variant":
            return True
        cols = uc.get("column_names") or ()
        if set(cols) == {"set_number", "set_variant"}:
            return True
    return False


def upgrade() -> None:
    conn = op.get_bind()
    cols = _column_names(conn, "catalog_sets")

    if "set_number" not in cols:
        with op.batch_alter_table("catalog_sets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("set_number", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("set_variant", sa.Integer(), nullable=True))
        cols = _column_names(conn, "catalog_sets")

    if "set_num" in cols:
        rows = conn.execute(sa.text("SELECT id, set_num FROM catalog_sets")).fetchall()
        for cid, set_num in rows:
            if set_num is None:
                continue
            n, v = _migrate_legacy_set_num(set_num)
            conn.execute(
                sa.text(
                    "UPDATE catalog_sets SET set_number=:n, set_variant=:v WHERE id=:id"
                ),
                {"n": n, "v": v, "id": cid},
            )
        with op.batch_alter_table("catalog_sets", schema=None) as batch_op:
            batch_op.drop_column("set_num")

    with op.batch_alter_table("catalog_sets", schema=None) as batch_op:
        batch_op.alter_column(
            "set_number",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "set_variant",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        )
        if not _uq_catalog_pair_exists(conn):
            batch_op.create_unique_constraint(
                "uq_catalog_sets_number_variant",
                ["set_number", "set_variant"],
            )


def downgrade() -> None:
    conn = op.get_bind()
    try:
        op.drop_constraint("uq_catalog_sets_number_variant", "catalog_sets", type_="unique")
    except Exception:
        pass

    cols = _column_names(conn, "catalog_sets")
    if "set_num" not in cols:
        with op.batch_alter_table("catalog_sets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("set_num", sa.Text(), nullable=True))

        for row in conn.execute(
            sa.text("SELECT id, set_number, set_variant FROM catalog_sets")
        ).fetchall():
            cid, n, v = row[0], row[1], row[2]
            s = f"{n}-{v}"
            conn.execute(
                sa.text("UPDATE catalog_sets SET set_num=:s WHERE id=:id"),
                {"s": s, "id": cid},
            )

        with op.batch_alter_table("catalog_sets", schema=None) as batch_op:
            batch_op.drop_column("set_number")
            batch_op.drop_column("set_variant")
            batch_op.alter_column("set_num", existing_type=sa.Text(), nullable=False)

        op.create_unique_constraint("catalog_sets_set_num_key", "catalog_sets", ["set_num"])
