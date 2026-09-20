"""Database migration helpers for portable and dev runtimes."""

from __future__ import annotations

from alembic import command

from app.runtime_paths import make_alembic_config


def upgrade_database_to_head() -> None:
    command.upgrade(make_alembic_config(), "head")
