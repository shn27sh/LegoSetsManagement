from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.rebrickable.dto import CatalogSetDTO, ThemeDTO
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_set

FIXTURES = Path(__file__).parent / "fixtures" / "csv"


def _csv_fake_client() -> FakeRebrickableClient:
    def set_dto(num: str, name: str) -> CatalogSetDTO:
        return replace(_sample_set(), set_num=num, name=name)

    return FakeRebrickableClient(
        sets={
            "6024-1": set_dto("6024-1", "Police Car"),
            "10281-1": set_dto("10281-1", "Other"),
            "21309-1": set_dto("21309-1", "Third"),
        },
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={"6024-1": [], "10281-1": [], "21309-1": []},
    )


def _patch_csv_import(fake: FakeRebrickableClient):
    from app.importers.csv_import_service import import_set_list

    def stub(session, content, *, client=None, existing_set_mode="skip"):
        return import_set_list(
            session,
            content,
            client=fake,
            existing_set_mode=existing_set_mode,
        )

    return patch("app.api.routes.imports.import_set_list", stub)


def test_post_csv_import_requires_api_key(api_client, monkeypatch) -> None:
    monkeypatch.delenv("REBRICKABLE_API_KEY", raising=False)
    content = (FIXTURES / "valid_comma.txt").read_text(encoding="utf-8")
    response = api_client.post(
        "/api/imports/csv",
        files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 400
    assert "REBRICKABLE_API_KEY" in response.json()["detail"]


def test_post_csv_import_creates_instances(api_client, monkeypatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    content = (FIXTURES / "valid_comma.txt").read_text(encoding="utf-8")
    with _patch_csv_import(_csv_fake_client()):
        response = api_client.post(
            "/api/imports/csv",
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["instances_created"] == 3
    assert body["sets_fetched"] == 3
    assert body["existing_sets_skipped"] == 0
    assert body["skipped_existing_sets"] == []
    assert body["catalog_stubs_created"] == 0
    assert body["errors"] == []


def test_post_csv_import_skips_existing_sets(api_client, monkeypatch, db_session) -> None:
    from tests.factories import add_catalog_set, add_owned_set

    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    content = "6024-1,10281-1"
    with _patch_csv_import(_csv_fake_client()):
        response = api_client.post(
            "/api/imports/csv",
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["existing_sets_skipped"] == 1
    assert body["skipped_existing_sets"] == [
        {"token_index": 0, "set_num": "6024-1"},
    ]
    assert body["instances_created"] == 1
    assert body["sets_fetched"] == 1


def test_post_csv_import_passes_existing_set_mode(api_client, monkeypatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    content = "6024-1"
    seen_mode = None

    def stub(session, content, *, existing_set_mode="skip", client=None):
        nonlocal seen_mode
        seen_mode = existing_set_mode
        from app.importers.csv_import_service import import_set_list

        return import_set_list(
            session,
            content,
            client=_csv_fake_client(),
            existing_set_mode=existing_set_mode,
        )

    with patch("app.api.routes.imports.import_set_list", stub):
        response = api_client.post(
            "/api/imports/csv",
            data={"existing_set_mode": "copy"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )

    assert response.status_code == 200
    assert seen_mode == "copy"


def test_post_csv_returns_token_errors(api_client, monkeypatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    content = (FIXTURES / "with_errors.txt").read_text(encoding="utf-8")
    with _patch_csv_import(_csv_fake_client()):
        response = api_client.post(
            "/api/imports/csv",
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["instances_created"] == 2
    assert len(body["errors"]) == 2
    assert body["errors"][0]["token_index"] == 1
    assert "token_index" in body["errors"][0]
    assert "raw" in body["errors"][0]
    assert "message" in body["errors"][0]


def test_post_csv_rejects_non_utf8(api_client, monkeypatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    response = api_client.post(
        "/api/imports/csv",
        files={"file": ("sets.txt", b"\xff\xfe", "text/plain")},
    )
    assert response.status_code == 400


def test_post_csv_rejects_oversized_file(api_client, monkeypatch) -> None:
    import app.api.routes.imports as imports_route

    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    monkeypatch.setattr(imports_route, "MAX_CSV_BYTES", 10)
    response = api_client.post(
        "/api/imports/csv",
        files={"file": ("sets.txt", b"0" * 20, "text/plain")},
    )
    assert response.status_code == 413


def test_post_local_metadata_updates_missing_values(api_client) -> None:
    from app.api.routes import imports as imports_route
    from app.services.local_metadata import LocalMetadataUpdateResult

    seen_session = None

    def stub(session):
        nonlocal seen_session
        seen_session = session
        return LocalMetadataUpdateResult(
            owned_set_ages_updated=2,
            catalog_themes_updated=3,
            age_values_available=4,
            theme_values_available=5,
        )

    with patch.object(imports_route, "update_missing_local_metadata", stub):
        response = api_client.post("/api/imports/local-metadata")

    assert response.status_code == 200
    assert seen_session is not None
    assert response.json() == {
        "owned_set_ages_updated": 2,
        "catalog_themes_updated": 3,
        "age_values_available": 4,
        "theme_values_available": 5,
    }


def test_post_database_import_rejects_invalid_file(api_client) -> None:
    response = api_client.post(
        "/api/imports/database",
        data={"mode": "add_only_new"},
        files={"file": ("bad.db", b"not-a-database", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_post_database_import_add_only_new(api_client, db_session, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from tests.factories import add_catalog_set, add_owned_set

    source_engine = create_engine(
        f"sqlite:///{tmp_path / 'source.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(source_engine)
    source_session = sessionmaker(bind=source_engine)()
    catalog = add_catalog_set(source_session, set_number=8888)
    add_owned_set(source_session, catalog)
    source_session.commit()
    source_session.close()
    source_engine.dispose()

    db_path = tmp_path / "source.db"
    response = api_client.post(
        "/api/imports/database",
        data={"mode": "add_only_new"},
        files={
            "file": (
                "source.db",
                db_path.read_bytes(),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sets_added"] == 1
    assert body["instances_created"] == 1
    assert body["sets_skipped"] == 0

