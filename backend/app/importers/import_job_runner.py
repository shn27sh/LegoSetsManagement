"""In-process background import jobs (single active job per process)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from app.db.session import get_session_factory
from app.importers.csv_import_service import import_set_list
from app.importers.database_import_service import import_from_database
from app.importers.import_job_exceptions import (
    ImportJobCancelled,
    ImportJobConflictError,
    ImportJobNotFoundError,
)
from app.importers.import_job_types import ProgressCallback
from app.importers.import_progress_callback import check_import_cancelled
from app.importers.rebrickable_sync_service import sync_rebrickable
from app.rebrickable.exceptions import RebrickableConfigError
from app.services.failed_sets_csv import failed_sets_csv_path
from app.services.image_download import image_downloader_for_sync

logger = logging.getLogger(__name__)

ImportJobKind = Literal["csv", "rebrickable_sync", "database"]
ImportJobStatus = Literal[
    "queued", "running", "completed", "failed", "cancelled"
]

_store_lock = threading.Lock()
_jobs: dict[str, "ImportJobRecord"] = {}


@dataclass
class ImportJobProgress:
    current: int
    total: int
    label: str


@dataclass
class ImportJobRecord:
    job_id: str
    kind: ImportJobKind
    status: ImportJobStatus
    progress: ImportJobProgress | None = None
    result: Any = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


@dataclass(frozen=True)
class CsvJobParams:
    content: str
    existing_set_mode: str = "skip"


@dataclass(frozen=True)
class SyncJobParams:
    owned_set_ids: list[int] | None = None
    download_set_images: bool = False
    download_missing_part_images: bool = False
    download_all_part_images: bool = False
    download_no_element_id_part_images: bool = False
    catalog_gap_part_keys: tuple[tuple[int, int], ...] | None = None


@dataclass(frozen=True)
class DatabaseJobParams:
    source_db_path: str
    mode: str = "add_only_new"
    delete_source_after: bool = True


def _active_job() -> ImportJobRecord | None:
    for job in _jobs.values():
        if job.status in ("queued", "running"):
            return job
    return None


def _set_progress(job_id: str, current: int, total: int, label: str) -> None:
    with _store_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.progress = ImportJobProgress(
                current=current, total=total, label=label
            )


def _progress_callback(job_id: str) -> ProgressCallback:
    def report(current: int, total: int, label: str) -> None:
        _set_progress(job_id, current, total, label)

    return report


def start_csv_job(params: CsvJobParams) -> str:
    return _start_job("csv", params)


def start_sync_job(params: SyncJobParams) -> str:
    return _start_job("rebrickable_sync", params)


def start_database_job(params: DatabaseJobParams) -> str:
    return _start_job("database", params)


def _start_job(kind: ImportJobKind, params: Any) -> str:
    with _store_lock:
        if _active_job() is not None:
            raise ImportJobConflictError(
                "An import job is already queued or running"
            )
        job_id = str(uuid4())
        _jobs[job_id] = ImportJobRecord(
            job_id=job_id,
            kind=kind,
            status="queued",
        )

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, kind, params),
        name=f"import-job-{kind}-{job_id[:8]}",
        daemon=True,
    )
    thread.start()
    return job_id


def get_active_job() -> ImportJobRecord | None:
    """Return the queued or running job for this process, if any."""
    with _store_lock:
        return _active_job()


def get_job(job_id: str) -> ImportJobRecord:
    with _store_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise ImportJobNotFoundError(f"Unknown import job: {job_id}")
        return job


def cancel_job(job_id: str) -> ImportJobRecord:
    with _store_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise ImportJobNotFoundError(f"Unknown import job: {job_id}")
        if job.status in ("queued", "running"):
            job.cancel_event.set()
        return job


def failed_sets_download_path() -> str | None:
    path = failed_sets_csv_path()
    if path.is_file() and path.stat().st_size > 0:
        return str(path)
    return None


def _run_job(job_id: str, kind: ImportJobKind, params: Any) -> None:
    with _store_lock:
        job = _jobs[job_id]
        job.status = "running"
        cancel_event = job.cancel_event

    session = get_session_factory()()
    try:
        on_progress = _progress_callback(job_id)
        if kind == "csv":
            assert isinstance(params, CsvJobParams)
            result = import_set_list(
                session,
                params.content,
                existing_set_mode=params.existing_set_mode,
                cancel_event=cancel_event,
                on_progress=on_progress,
            )
        elif kind == "rebrickable_sync":
            assert isinstance(params, SyncJobParams)
            images_enabled = (
                params.download_set_images
                or params.download_missing_part_images
                or params.download_all_part_images
                or params.download_no_element_id_part_images
            )
            with image_downloader_for_sync(
                None, images_enabled=images_enabled
            ) as image_downloader:
                result = sync_rebrickable(
                    session,
                    owned_set_ids=params.owned_set_ids,
                    download_set_images=params.download_set_images,
                    download_missing_part_images=params.download_missing_part_images,
                    download_all_part_images=params.download_all_part_images,
                    download_no_element_id_part_images=(
                        params.download_no_element_id_part_images
                    ),
                    catalog_gap_part_keys=params.catalog_gap_part_keys,
                    image_downloader=image_downloader,
                    cancel_event=cancel_event,
                    on_progress=on_progress,
                )
        elif kind == "database":
            assert isinstance(params, DatabaseJobParams)
            result = import_from_database(
                session,
                params.source_db_path,
                mode=params.mode,  # type: ignore[arg-type]
                cancel_event=cancel_event,
                on_progress=on_progress,
            )
        else:
            raise ValueError(f"Unknown job kind: {kind}")

        session.commit()
        with _store_lock:
            job = _jobs.get(job_id)
            if job is not None:
                if job.cancel_event.is_set():
                    job.status = "cancelled"
                else:
                    job.status = "completed"
                job.result = result
    except ImportJobCancelled:
        session.rollback()
        with _store_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.status = "cancelled"
    except RebrickableConfigError as exc:
        session.rollback()
        with _store_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
    except Exception as exc:
        logger.exception("Import job failed job_id=%s kind=%s", job_id, kind)
        session.rollback()
        with _store_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
    finally:
        session.close()
        if kind == "database" and isinstance(params, DatabaseJobParams):
            if params.delete_source_after:
                try:
                    from pathlib import Path

                    Path(params.source_db_path).unlink(missing_ok=True)
                except OSError:
                    logger.exception(
                        "Failed to delete temp database job_id=%s",
                        job_id,
                    )


def reset_jobs_for_tests() -> None:
    """Clear the in-memory job store (tests only)."""
    with _store_lock:
        _jobs.clear()
