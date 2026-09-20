from dataclasses import replace

from sqlalchemy import func, select

from app.db.models import CatalogSet, OwnedSet
from app.importers.csv_import_service import CsvImportSkippedExistingSet, import_set_list
from app.rebrickable.dto import ThemeDTO
from tests.factories import add_catalog_set, add_owned_set
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_set


def _client() -> FakeRebrickableClient:
    return FakeRebrickableClient(
        sets={
            "6024-1": _sample_set(),
            "10281-1": replace(_sample_set(), set_num="10281-1", name="Other"),
        },
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={"6024-1": [], "10281-1": []},
    )


def test_import_creates_instances_with_rebrickable_fetch(db_session) -> None:
    result = import_set_list(db_session, "6024-1,10281-1", client=_client())
    db_session.commit()

    assert result.instances_created == 2
    assert result.sets_fetched == 2
    assert result.existing_sets_skipped == 0
    assert result.catalog_stubs_created == 0
    assert result.errors == []
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 2


def test_import_reuses_existing_catalog_set(db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    result = import_set_list(db_session, "6024-1", client=_client())
    db_session.commit()

    assert result.instances_created == 0
    assert result.sets_fetched == 0
    assert result.existing_sets_skipped == 1
    assert result.skipped_existing_sets == [
        CsvImportSkippedExistingSet(token_index=0, set_num="6024-1")
    ]
    assert result.catalog_stubs_created == 0
    assert db_session.scalar(select(func.count()).select_from(CatalogSet)) == 1
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 1


def test_import_existing_catalog_can_create_copy(db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    result = import_set_list(
        db_session,
        "6024-1",
        client=_client(),
        existing_set_mode="copy",
    )
    db_session.commit()

    assert result.instances_created == 1
    assert result.sets_fetched == 0
    assert result.existing_sets_skipped == 0
    assert db_session.scalar(select(func.count()).select_from(CatalogSet)) == 1
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 2


def test_import_duplicate_tokens_create_multiple_instances(db_session) -> None:
    result = import_set_list(
        db_session,
        "6024-1,6024-1",
        client=_client(),
        existing_set_mode="copy",
    )
    db_session.commit()

    assert result.instances_created == 2
    assert result.sets_fetched == 1
    assert result.catalog_stubs_created == 0
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 2


def test_import_skips_invalid_tokens_but_imports_valid(db_session) -> None:
    result = import_set_list(db_session, "6024-1,,bad!", client=_client())
    db_session.commit()

    assert result.instances_created == 1
    assert result.sets_fetched == 1
    assert len(result.errors) == 2
