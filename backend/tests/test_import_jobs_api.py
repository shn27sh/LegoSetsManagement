"""Background import jobs API (Phase 3)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.importers.csv_import_service import import_set_list as real_csv_import
from app.importers.import_job_runner import _jobs, _store_lock, reset_jobs_for_tests
from app.rebrickable.dto import CatalogSetDTO, ThemeDTO
from tests.test_database_import_service import _populate_source_set
from tests.test_imports_api import FIXTURES, _csv_fake_client
from tests.test_rebrickable_sync_service import FakeRebrickableClient, _sample_set


@pytest.fixture(autouse=True)
def _clear_import_jobs() -> None:
    reset_jobs_for_tests()
    yield
    reset_jobs_for_tests()


@pytest.fixture
def job_api_client(api_client, db_session):
    """Import jobs use their own session factory — bind it to the test database."""
    factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )

    with patch(
        "app.importers.import_job_runner.get_session_factory",
        return_value=factory,
    ):
        yield api_client
        _wait_for_all_jobs_idle(timeout=15.0)


def _wait_for_all_jobs_idle(*, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _store_lock:
            if not any(
                job.status in ("queued", "running") for job in _jobs.values()
            ):
                return
        time.sleep(0.05)


def _wait_for_terminal_status(api_client, job_id: str, *, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = api_client.get(f"/api/imports/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("completed", "failed", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_start_csv_job_and_poll_to_completion(job_api_client, monkeypatch) -> None:
    api_client = job_api_client
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    content = (FIXTURES / "valid_comma.txt").read_text(encoding="utf-8")
    def _csv_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=_csv_fake_client(), **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_csv_stub):
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    body = _wait_for_terminal_status(api_client, job_id)
    assert body["status"] == "completed"
    assert body["kind"] == "csv"
    assert body["result"]["instances_created"] == 3
    assert body["progress"]["total"] == 3


def test_get_active_import_job(job_api_client, monkeypatch) -> None:
    api_client = job_api_client
    assert api_client.get("/api/imports/jobs/active").status_code == 404

    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    content = (FIXTURES / "valid_comma.txt").read_text(encoding="utf-8")

    def _csv_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=_csv_fake_client(), **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_csv_stub):
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    active = api_client.get("/api/imports/jobs/active")
    assert active.status_code == 200
    assert active.json()["job_id"] == job_id
    assert active.json()["status"] in ("queued", "running", "completed")
    _wait_for_terminal_status(api_client, job_id)
    assert api_client.get("/api/imports/jobs/active").status_code == 404


def test_second_job_returns_409(job_api_client, monkeypatch) -> None:
    api_client = job_api_client
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    base_client = _csv_fake_client()

    class SlowClient(FakeRebrickableClient):
        def __init__(self) -> None:
            super().__init__(
                sets=base_client.sets,
                themes=base_client.themes,
                set_parts=base_client.set_parts,
            )

        def get_set(self, set_num: str) -> CatalogSetDTO:
            time.sleep(0.2)
            return super().get_set(set_num)

    content = "6024-1"

    def _slow_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=SlowClient(), **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_slow_stub):
        first = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
        assert first.status_code == 202
        second = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
    assert second.status_code == 409


def test_health_available_while_job_running(job_api_client, monkeypatch) -> None:
    api_client = job_api_client
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    base_client = _csv_fake_client()

    class SlowClient(FakeRebrickableClient):
        def __init__(self) -> None:
            super().__init__(
                sets=base_client.sets,
                themes=base_client.themes,
                set_parts=base_client.set_parts,
            )

        def get_set(self, set_num: str) -> CatalogSetDTO:
            time.sleep(0.15)
            return super().get_set(set_num)

    content = "6024-1,10281-1,21309-1"

    def _slow_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=SlowClient(), **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_slow_stub):
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
        assert start.status_code == 202
        job_id = start.json()["job_id"]
        saw_running = False
        for _ in range(40):
            status = api_client.get(f"/api/imports/jobs/{job_id}")
            if status.json()["status"] == "running":
                saw_running = True
                health = api_client.get("/health")
                assert health.status_code == 200
                assert health.json() == {"status": "ok"}
                break
            time.sleep(0.05)
        _wait_for_terminal_status(api_client, job_id)
    assert saw_running


def test_cancel_csv_job(job_api_client, monkeypatch) -> None:
    api_client = job_api_client
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    base_client = _csv_fake_client()

    class SlowClient(FakeRebrickableClient):
        def __init__(self) -> None:
            super().__init__(
                sets=base_client.sets,
                themes=base_client.themes,
                set_parts=base_client.set_parts,
            )

        def get_set(self, set_num: str) -> CatalogSetDTO:
            time.sleep(1.0)
            return super().get_set(set_num)

    content = "6024-1"

    def _slow_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=SlowClient(), **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_slow_stub):
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", content.encode("utf-8"), "text/plain")},
        )
        job_id = start.json()["job_id"]
        cancel = api_client.delete(f"/api/imports/jobs/{job_id}")
        assert cancel.status_code == 200
        body = _wait_for_terminal_status(api_client, job_id, timeout=15.0)
    assert body["status"] == "cancelled"


def test_csv_job_writes_failed_sets_csv(
    job_api_client, monkeypatch, tmp_path
) -> None:
    api_client = job_api_client
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    csv_path = tmp_path / "failedSets.csv"
    monkeypatch.setenv("FAILED_SETS_CSV_PATH", str(csv_path))
    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        fail_set_nums={"6024-1"},
    )

    def _fail_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=client, **kwargs)

    with patch("app.importers.import_job_runner.import_set_list", side_effect=_fail_stub):
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "csv"},
            files={"file": ("sets.txt", b"6024-1", "text/plain")},
        )
        body = _wait_for_terminal_status(api_client, start.json()["job_id"])
    assert body["status"] == "completed"
    assert len(body["result"]["sets_failed"]) == 1
    assert csv_path.read_text(encoding="utf-8") == "6024-1"
    assert body["failed_sets_csv_path"] == str(csv_path)


def test_get_unknown_job_404(api_client) -> None:
    response = api_client.get("/api/imports/jobs/not-a-real-id")
    assert response.status_code == 404


def test_database_import_job(job_api_client, tmp_path) -> None:
    api_client = job_api_client
    source_path = tmp_path / "source.db"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.db.sqlite_pragmas import configure_sqlite_engine

    engine = create_engine(
        f"sqlite:///{source_path.resolve()}",
        connect_args={"check_same_thread": False},
    )
    configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    _populate_source_set(session, set_number=8888, name="From Source")
    session.commit()
    session.close()
    engine.dispose()

    with open(source_path, "rb") as handle:
        start = api_client.post(
            "/api/imports/jobs",
            data={"kind": "database", "mode": "add_only_new"},
            files={"file": ("other.db", handle.read(), "application/octet-stream")},
        )
    assert start.status_code == 202
    body = _wait_for_terminal_status(api_client, start.json()["job_id"])
    assert body["status"] == "completed"
    assert body["result"]["sets_added"] == 1
