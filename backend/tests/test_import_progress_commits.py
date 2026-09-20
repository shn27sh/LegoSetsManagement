"""Per-unit commits during import/sync (Phase 1 DB foundation)."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.models import CatalogSet
from app.db.sqlite_pragmas import configure_sqlite_engine
from app.importers.csv_import_service import import_set_list
from app.importers import database_import_service
from app.importers.database_import_service import import_from_database_session
from app.rebrickable.dto import CatalogSetDTO, ThemeDTO
from tests.test_database_import_service import _populate_source_set
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_part_line, _sample_set


def _sample_set_10281() -> CatalogSetDTO:
    return replace(
        _sample_set(),
        set_num="10281-1",
        name="Bonsai Tree",
        num_parts=878,
    )


def _engine(base_dir, filename: str = "progress.db"):
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / filename
    engine = create_engine(
        f"sqlite:///{db_path.resolve()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    return engine


def test_sqlite_engine_uses_wal_journal_mode(tmp_path) -> None:
    engine = _engine(tmp_path, "wal.db")
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    engine.dispose()
    assert mode == "wal"


def test_csv_import_commits_first_token_before_second(tmp_path) -> None:
    engine = _engine(tmp_path, "progress.db")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    first_token_visible: bool | None = None

    class ProgressCheckingClient(FakeRebrickableClient):
        def get_set(self, set_num: str) -> CatalogSetDTO:
            nonlocal first_token_visible
            if set_num == "10281-1":
                other = session_factory()
                try:
                    catalog = other.scalar(
                        select(CatalogSet).where(
                            CatalogSet.set_number == 6024,
                            CatalogSet.set_variant == 1,
                        )
                    )
                    first_token_visible = (
                        catalog is not None and catalog.name == "Police Car"
                    )
                finally:
                    other.close()
            return super().get_set(set_num)

    client = ProgressCheckingClient(
        sets={"6024-1": _sample_set(), "10281-1": _sample_set_10281()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={
            "6024-1": [_sample_part_line()],
            "10281-1": [_sample_part_line("3001")],
        },
    )

    try:
        result = import_set_list(session, "6024-1,10281-1", client=client)
        assert result.instances_created == 2
        assert result.sets_fetched == 2
        assert first_token_visible is True
    finally:
        session.close()
        engine.dispose()


def test_database_import_commits_first_set_before_second(tmp_path) -> None:
    source_engine = _engine(tmp_path, "source.db")
    target_engine = _engine(tmp_path, "target.db")
    source_factory = sessionmaker(
        bind=source_engine, autoflush=False, autocommit=False
    )
    target_factory = sessionmaker(
        bind=target_engine, autoflush=False, autocommit=False
    )
    source = source_factory()
    target = target_factory()
    _populate_source_set(source, set_number=6024, name="Police Car")
    _populate_source_set(source, set_number=9999, name="New Set")
    source.commit()

    first_set_visible: bool | None = None
    original_import = database_import_service._import_new_catalog_set

    def tracking_import_new(target_session, source_session, source_catalog):
        nonlocal first_set_visible
        if source_catalog.set_number == 9999:
            other = target_factory()
            try:
                catalog = other.scalar(
                    select(CatalogSet).where(
                        CatalogSet.set_number == 6024,
                        CatalogSet.set_variant == 1,
                    )
                )
                first_set_visible = (
                    catalog is not None and catalog.name == "Police Car"
                )
            finally:
                other.close()
        return original_import(target_session, source_session, source_catalog)

    try:
        with patch.object(
            database_import_service,
            "_import_new_catalog_set",
            side_effect=tracking_import_new,
        ):
            result = import_from_database_session(target, source, mode="add_only_new")
        assert result.sets_added == 2
        assert first_set_visible is True
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()
