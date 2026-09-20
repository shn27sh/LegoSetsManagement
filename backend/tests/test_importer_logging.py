"""Importer logging must not emit secrets."""

import json
import logging

import pytest

from app.importers.csv_import_service import import_set_list
from app.importers.rebrickable_sync_service import sync_catalog_for_set_nums
from app.logging_config import configure_logging
from app.rebrickable.dto import CatalogSetDTO, ThemeDTO
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_set
from tests.factories import add_catalog_set, add_owned_set


def test_csv_import_logs_without_secrets(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.importers.csv_import_service")

    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
    )
    import_set_list(
        db_session,
        "6024-1, secret-token-should-not-appear@invalid",
        client=client,
    )

    assert "secret-token-should-not-appear" not in caplog.text
    assert "CSV import finished" in caplog.text


def test_rebrickable_sync_logs_set_summary(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.importers.rebrickable_sync_service")

    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
    )
    sync_catalog_for_set_nums(db_session, client, ["6024-1"])

    assert "Rebrickable sync set_ok set_num=6024-1" in caplog.text
    assert "your-api-key" not in caplog.text.lower()


def test_configure_logging_defaults_to_warning(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_writes_local_log_file(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "server.log"
    monkeypatch.setenv("LOG_FILE_PATH", str(log_path))
    monkeypatch.setenv("LOG_FILE_MAX_BYTES", "1024")
    monkeypatch.setenv("LOG_FILE_BACKUP_COUNT", "1")

    configure_logging()
    logging.getLogger("app.importers.csv_import_service").warning(
        "CSV import token_failed token_index=%s rb_key=%s error=%s",
        3,
        "9999-1",
        "not found",
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "CSV import token_failed" in content
    assert "9999-1" in content
    assert "not found" in content


def test_csv_import_stores_failure_record(tmp_path, monkeypatch, db_session) -> None:
    failure_log = tmp_path / "import_failures.log"
    monkeypatch.setenv("IMPORT_FAILURE_LOG_PATH", str(failure_log))
    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        fail_set_nums={"6024-1"},
    )

    result = import_set_list(db_session, "6024-1", client=client)

    assert len(result.sets_failed) == 1
    record = json.loads(failure_log.read_text(encoding="utf-8").strip())
    assert record["operation"] == "csv_import"
    assert record["token_index"] == 0
    assert record["set_num"] == 6024
    assert record["rb_key"] == "6024-1"
    assert "404" in record["message"]


def test_rebrickable_sync_stores_failure_record(
    tmp_path, monkeypatch, db_session
) -> None:
    failure_log = tmp_path / "import_failures.log"
    monkeypatch.setenv("IMPORT_FAILURE_LOG_PATH", str(failure_log))
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

    result = sync_catalog_for_set_nums(db_session, client, ["77777-1"])

    assert len(result.sets_failed) == 1
    record = json.loads(failure_log.read_text(encoding="utf-8").strip())
    assert record["operation"] == "rebrickable_sync"
    assert record["set_num"] == "77777-1"
    assert record["rb_key"] == "77777-1"
    assert "404" in record["message"]
