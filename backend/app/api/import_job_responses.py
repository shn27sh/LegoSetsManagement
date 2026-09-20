"""Map import job results to API response payloads."""

from __future__ import annotations

from app.importers.csv_import_service import CsvImportResult
from app.importers.database_import_service import DatabaseImportResult
from app.importers.import_job_runner import ImportJobRecord, ImportJobProgress
from app.importers.rebrickable_sync_service import RebrickableSyncResult
from app.schemas.imports import (
    CsvImportResponse,
    CsvImportSetFailure,
    CsvImportSkippedExistingSet,
    CsvTokenError,
    DatabaseImportResponse,
    ImageDownloadFailure,
    ImportJobProgress as ImportJobProgressSchema,
    ImportJobStatusResponse,
    RebrickableSetSyncFailure,
    RebrickableSyncResponse,
)


def _progress_to_schema(
    progress: ImportJobProgress | None,
) -> ImportJobProgressSchema | None:
    if progress is None:
        return None
    return ImportJobProgressSchema(
        current=progress.current,
        total=progress.total,
        label=progress.label,
    )


def _csv_result_payload(result: CsvImportResult) -> dict:
    return CsvImportResponse(
        instances_created=result.instances_created,
        catalog_stubs_created=result.catalog_stubs_created,
        sets_fetched=result.sets_fetched,
        existing_sets_skipped=result.existing_sets_skipped,
        skipped_existing_sets=[
            CsvImportSkippedExistingSet(
                token_index=skipped.token_index,
                set_num=skipped.set_num,
            )
            for skipped in result.skipped_existing_sets
        ],
        sets_failed=[
            CsvImportSetFailure(
                token_index=f.token_index,
                set_num=f.set_num,
                message=f.message,
            )
            for f in result.sets_failed
        ],
        errors=[
            CsvTokenError(
                token_index=e.token_index,
                raw=e.raw,
                message=e.message,
            )
            for e in result.errors
        ],
        set_images_downloaded=result.set_images_downloaded,
        minifig_images_downloaded=result.minifig_images_downloaded,
        part_images_downloaded=result.part_images_downloaded,
        image_downloads_failed=[
            ImageDownloadFailure(
                target=f.target,
                url=f.url,
                message=f.message,
            )
            for f in result.image_downloads_failed
        ],
    ).model_dump()


def _sync_result_payload(result: RebrickableSyncResult) -> dict:
    return RebrickableSyncResponse(
        sets_synced=result.sets_synced,
        sets_failed=[
            RebrickableSetSyncFailure(set_num=f.set_num, message=f.message)
            for f in result.sets_failed
        ],
        parts_upserted=result.parts_upserted,
        inventory_lines_written=result.inventory_lines_written,
        set_images_downloaded=result.set_images_downloaded,
        minifig_images_downloaded=result.minifig_images_downloaded,
        part_images_downloaded=result.part_images_downloaded,
        image_downloads_failed=[
            ImageDownloadFailure(
                target=f.target,
                url=f.url,
                message=f.message,
            )
            for f in result.image_downloads_failed
        ],
    ).model_dump()


def _database_result_payload(result: DatabaseImportResult) -> dict:
    return DatabaseImportResponse(
        sets_added=result.sets_added,
        sets_updated=result.sets_updated,
        sets_skipped=result.sets_skipped,
        skipped_set_nums=result.skipped_set_nums,
        instances_created=result.instances_created,
        parts_upserted=result.parts_upserted,
        inventory_lines_written=result.inventory_lines_written,
    ).model_dump()


def job_to_status_response(
    job: ImportJobRecord,
    *,
    failed_sets_csv_path: str | None,
) -> ImportJobStatusResponse:
    result_payload: dict | None = None
    if job.status == "completed" and job.result is not None:
        if job.kind == "csv":
            result_payload = _csv_result_payload(job.result)
        elif job.kind == "rebrickable_sync":
            result_payload = _sync_result_payload(job.result)
        elif job.kind == "database":
            result_payload = _database_result_payload(job.result)

    return ImportJobStatusResponse(
        job_id=job.job_id,
        kind=job.kind,
        status=job.status,
        progress=_progress_to_schema(job.progress),
        result=result_payload,
        error=job.error,
        failed_sets_csv_path=failed_sets_csv_path,
    )
