"""failedSets.csv retry file for catalog-level Rebrickable failures."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.importers.csv_import_service import import_set_list
from app.importers.rebrickable_sync_service import sync_catalog_for_set_nums
from app.rebrickable.dto import CatalogSetDTO, ThemeDTO
from app.services.failed_sets_csv import (
    begin_failed_sets_run,
    failed_sets_csv_path,
    finalize_failed_sets_run,
    record_failed_set,
)
from tests.factories import add_catalog_set, add_owned_set
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_set


def test_begin_record_finalize_writes_deduped_keys(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))

    begin_failed_sets_run()
    record_failed_set("9999-1")
    record_failed_set("6024-1")
    record_failed_set("9999-1")
    finalize_failed_sets_run()

    assert csv_path.read_text(encoding="utf-8") == "9999-1,6024-1"


def test_second_run_overwrites_previous_file(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))

    begin_failed_sets_run()
    record_failed_set("1111-1")
    finalize_failed_sets_run()

    begin_failed_sets_run()
    record_failed_set("2222-1")
    finalize_failed_sets_run()

    assert csv_path.read_text(encoding="utf-8") == "2222-1"


def test_finalize_with_no_failures_writes_empty_file(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))

    begin_failed_sets_run()
    finalize_failed_sets_run()

    assert csv_path.read_text(encoding="utf-8") == ""


def test_csv_import_records_rebrickable_failures_only(
    tmp_path, monkeypatch, db_session
) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))
    client = FakeRebrickableClient(
        sets={
            "6024-1": _sample_set(),
            "9999-1": CatalogSetDTO(
                set_num="9999-1",
                name="Missing",
                year=2020,
                theme_external_id=None,
                num_parts=1,
                image_url=None,
            ),
        },
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={"6024-1": []},
        fail_set_nums={"9999-1"},
    )

    result = import_set_list(db_session, "6024-1,9999-1", client=client)

    assert result.sets_fetched == 1
    assert len(result.sets_failed) == 1
    assert csv_path.read_text(encoding="utf-8") == "9999-1"


def test_sync_records_rebrickable_api_failures(
    tmp_path, monkeypatch, db_session
) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))
    catalog = add_catalog_set(db_session, set_number=77777)
    add_owned_set(db_session, catalog)
    db_session.commit()
    client = FakeRebrickableClient(
        sets={
            "77777-1": CatalogSetDTO(
                set_num="77777-1",
                name="Broken",
                year=2024,
                theme_external_id=None,
                num_parts=1,
                image_url=None,
            )
        },
        fail_set_nums={"77777-1"},
    )

    sync_catalog_for_set_nums(db_session, client, ["77777-1"])

    assert csv_path.read_text(encoding="utf-8") == "77777-1"


def test_download_failed_sets_csv_endpoint(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))
    csv_path.write_text("6024-1,9999-1", encoding="utf-8")

    response = api_client.get("/api/imports/failed-sets.csv")

    assert response.status_code == 200
    assert response.text == "6024-1,9999-1"
    assert "text/plain" in response.headers.get("content-type", "")


def test_download_failed_sets_csv_404_when_empty(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))
    csv_path.write_text("", encoding="utf-8")

    response = api_client.get("/api/imports/failed-sets.csv")

    assert response.status_code == 404


def test_download_failed_sets_csv_404_when_missing(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(tmp_path / "missing.csv"))

    response = api_client.get("/api/imports/failed-sets.csv")

    assert response.status_code == 404


def test_failed_sets_path_default_under_data() -> None:
    assert failed_sets_csv_path().name == "failedSets.csv"
