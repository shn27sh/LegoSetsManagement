#!/usr/bin/env python3
"""Verify FastAPI exposes health, CSV import, and import jobs (step 4 of scripts/smoke.sh)."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _make_csv_stub():
    from app.importers.csv_import_service import import_set_list as real_csv_import
    from tests.test_imports_api import _csv_fake_client

    def _csv_stub(session, text, **kwargs):
        return real_csv_import(session, text, client=_csv_fake_client(), **kwargs)

    return _csv_stub


@contextmanager
def _mock_csv_import():
    csv_stub = _make_csv_stub()
    with (
        patch("app.api.routes.imports.import_set_list", side_effect=csv_stub),
        patch("app.importers.import_job_runner.import_set_list", side_effect=csv_stub),
    ):
        yield


def _fresh_db_hint() -> str:
    return (
        "Use a fresh database (./scripts/smoke.sh step 3): "
        "rm backend/data/smoke.db && cd backend && alembic upgrade head"
    )


def _report_missing_instances(body: dict, *, route: str) -> None:
    skipped = body.get("existing_sets_skipped", 0)
    if skipped:
        print(
            f"ERROR: {route} skipped all fixture sets ({skipped} existing). "
            f"{_fresh_db_hint()}",
            file=sys.stderr,
        )
    else:
        print(f"ERROR: expected instances_created >= 1, got {body}", file=sys.stderr)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1

    os.environ.setdefault("REBRICKABLE_API_KEY", "smoke-test-key")

    client = TestClient(app)

    health = client.get("/health")
    if health.status_code != 200 or health.json() != {"status": "ok"}:
        print(
            f"ERROR: GET /health failed: status={health.status_code} body={health.text}",
            file=sys.stderr,
        )
        return 1
    print('GET /health -> 200 {"status": "ok"}')

    paths = client.get("/openapi.json").json().get("paths", {})
    if "/api/imports/csv" not in paths:
        print("SKIP POST /api/imports/csv (route not registered on this branch)")
        return 0

    fixture = BACKEND / "tests" / "fixtures" / "csv" / "valid_comma.txt"
    if not fixture.is_file():
        print(f"ERROR: missing fixture {fixture}", file=sys.stderr)
        return 1

    content = fixture.read_text(encoding="utf-8")

    with _mock_csv_import():
        response = client.post(
            "/api/imports/csv",
            files={"file": ("smoke.txt", content.encode("utf-8"), "text/plain")},
        )
        if response.status_code != 200:
            print(
                f"ERROR: POST /api/imports/csv failed: status={response.status_code} body={response.text}",
                file=sys.stderr,
            )
            return 1

        body = response.json()
        for key in ("instances_created", "catalog_stubs_created", "errors"):
            if key not in body:
                print(f"ERROR: response missing key {key!r}: {body}", file=sys.stderr)
                return 1

        if body["instances_created"] < 1:
            _report_missing_instances(body, route="POST /api/imports/csv")
            return 1

        print(
            "POST /api/imports/csv -> 200 "
            f"(instances_created={body['instances_created']}, "
            f"catalog_stubs_created={body['catalog_stubs_created']})"
        )

        if "/api/imports/jobs" not in paths:
            print("SKIP POST /api/imports/jobs (route not registered on this branch)")
            return 0

        return _probe_import_jobs(client, content)


def _probe_import_jobs(client: TestClient, content: str) -> int:
    start = client.post(
        "/api/imports/jobs",
        data={"kind": "csv", "existing_set_mode": "copy"},
        files={"file": ("smoke.txt", content.encode("utf-8"), "text/plain")},
    )
    if start.status_code != 202:
        print(
            f"ERROR: POST /api/imports/jobs failed: status={start.status_code} body={start.text}",
            file=sys.stderr,
        )
        return 1

    job_id = start.json()["job_id"]
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        status = client.get(f"/api/imports/jobs/{job_id}")
        if status.status_code != 200:
            print(
                f"ERROR: GET /api/imports/jobs/{job_id} failed: "
                f"status={status.status_code} body={status.text}",
                file=sys.stderr,
            )
            return 1
        body = status.json()
        if body["status"] in ("completed", "failed", "cancelled"):
            if body["status"] != "completed":
                print(
                    f"ERROR: import job ended with status={body['status']!r}: {body}",
                    file=sys.stderr,
                )
                return 1
            result = body.get("result") or {}
            if result.get("instances_created", 0) < 1:
                _report_missing_instances(result, route="POST /api/imports/jobs")
                return 1
            print(
                "POST /api/imports/jobs -> poll completed "
                f"(instances_created={result.get('instances_created')}, "
                f"existing_set_mode=copy)"
            )
            active = client.get("/api/imports/jobs/active")
            if active.status_code != 404:
                print(
                    f"ERROR: expected no active job after completion, got {active.status_code}",
                    file=sys.stderr,
                )
                return 1
            return 0
        time.sleep(0.2)

    print("ERROR: import job did not complete within 30s", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
