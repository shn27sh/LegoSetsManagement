import json
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.import_job_responses import _csv_result_payload, job_to_status_response
from app.db.deps import get_db
from app.importers.import_job_exceptions import (
    ImportJobConflictError,
    ImportJobNotFoundError,
)
from app.importers.import_job_runner import (
    CsvJobParams,
    DatabaseJobParams,
    SyncJobParams,
    cancel_job,
    failed_sets_download_path,
    get_active_job,
    get_job,
    start_csv_job,
    start_database_job,
    start_sync_job,
)
from app.importers.csv_import_service import import_set_list
from app.importers.database_import_service import (
    import_from_database,
    validate_source_database,
)
from app.importers.rebrickable_sync_service import (
    ensure_api_key_configured,
    sync_rebrickable,
)
from app.rebrickable.exceptions import RebrickableConfigError
from app.schemas.imports import (
    CsvImportResponse,
    DatabaseImportMode,
    DatabaseImportResponse,
    ExistingSetImportMode,
    ImageDownloadFailure,
    ImportJobKind,
    ImportJobStartResponse,
    ImportJobStatusResponse,
    LocalMetadataUpdateResponse,
    RebrickableSetSyncFailure,
    RebrickableSyncRequest,
    RebrickableSyncResponse,
)
from app.services.failed_sets_csv import failed_sets_csv_path
from app.services.local_metadata import update_missing_local_metadata

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_CSV_BYTES = int(os.environ.get("CSV_IMPORT_MAX_BYTES", 1_048_576))
MAX_DATABASE_BYTES = int(os.environ.get("DATABASE_IMPORT_MAX_BYTES", 524_288_000))


def _sync_params_from_options(
    sync_options: str | None,
) -> SyncJobParams:
    if not sync_options or not sync_options.strip():
        return SyncJobParams()
    try:
        payload = json.loads(sync_options)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="sync_options must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="sync_options must be a JSON object")
    request = RebrickableSyncRequest.model_validate(payload)
    part_image_mode = request.part_image_download_mode
    catalog_gap_part_keys = None
    if request.catalog_gap_part_keys:
        catalog_gap_part_keys = tuple(
            (key.part_id, key.color_id) for key in request.catalog_gap_part_keys
        )
    return SyncJobParams(
        owned_set_ids=request.owned_set_ids,
        download_set_images=request.download_set_images,
        download_missing_part_images=(
            part_image_mode == "missing"
            or (
                part_image_mode == "none"
                and request.download_missing_part_images
            )
        ),
        download_all_part_images=part_image_mode == "all",
        download_no_element_id_part_images=part_image_mode == "no_element_id",
        catalog_gap_part_keys=catalog_gap_part_keys,
    )


@router.post("/jobs", status_code=202, response_model=ImportJobStartResponse)
async def start_import_job(
    kind: ImportJobKind = Form(...),
    file: UploadFile | None = File(None),
    existing_set_mode: ExistingSetImportMode = Form("skip"),
    mode: DatabaseImportMode = Form("add_only_new"),
    sync_options: str | None = Form(None),
) -> ImportJobStartResponse:
    try:
        if kind == "csv":
            if file is None:
                raise HTTPException(status_code=400, detail="file is required for csv jobs")
            raw = await file.read()
            if len(raw) > MAX_CSV_BYTES:
                raise HTTPException(status_code=413, detail="CSV file too large")
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="File must be UTF-8") from exc
            try:
                ensure_api_key_configured()
            except RebrickableConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            job_id = start_csv_job(
                CsvJobParams(content=content, existing_set_mode=existing_set_mode)
            )
        elif kind == "rebrickable_sync":
            try:
                ensure_api_key_configured()
            except RebrickableConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            job_id = start_sync_job(_sync_params_from_options(sync_options))
        elif kind == "database":
            if file is None:
                raise HTTPException(
                    status_code=400, detail="file is required for database jobs"
                )
            raw = await file.read()
            if len(raw) > MAX_DATABASE_BYTES:
                raise HTTPException(status_code=413, detail="Database file too large")
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            try:
                tmp.write(raw)
                tmp.flush()
                validate_source_database(tmp.name)
                job_id = start_database_job(
                    DatabaseJobParams(source_db_path=tmp.name, mode=mode)
                )
            except ValueError as exc:
                tmp.close()
                os.unlink(tmp.name)
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            finally:
                tmp.close()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown job kind: {kind}")
    except ImportJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ImportJobStartResponse(job_id=job_id, status="queued")


@router.get("/jobs/active", response_model=ImportJobStatusResponse)
def get_active_import_job() -> ImportJobStatusResponse:
    """Return the queued or running import job for this server process, if any."""
    job = get_active_job()
    if job is None:
        raise HTTPException(status_code=404, detail="No active import job")
    return job_to_status_response(
        job,
        failed_sets_csv_path=failed_sets_download_path(),
    )


@router.get("/jobs/{job_id}", response_model=ImportJobStatusResponse)
def get_import_job(job_id: str) -> ImportJobStatusResponse:
    try:
        job = get_job(job_id)
    except ImportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return job_to_status_response(
        job,
        failed_sets_csv_path=failed_sets_download_path(),
    )


@router.delete("/jobs/{job_id}", response_model=ImportJobStatusResponse)
def delete_import_job(job_id: str) -> ImportJobStatusResponse:
    try:
        job = cancel_job(job_id)
    except ImportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return job_to_status_response(
        job,
        failed_sets_csv_path=failed_sets_download_path(),
    )


@router.get("/failed-sets.csv")
def download_failed_sets_csv() -> FileResponse:
    """Download comma-separated Rebrickable keys that failed on the last CSV import or sync."""
    path = failed_sets_csv_path()
    if not path.is_file() or path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="No failed sets from the last import")
    return FileResponse(
        path,
        media_type="text/plain; charset=utf-8",
        filename="failedSets.csv",
    )


@router.post("/csv", response_model=CsvImportResponse)
async def import_csv(
    file: UploadFile = File(...),
    existing_set_mode: ExistingSetImportMode = Form("skip"),
    db: Session = Depends(get_db, scope="function"),
) -> CsvImportResponse:
    raw = await file.read()
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file too large")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8") from exc

    try:
        ensure_api_key_configured()
    except RebrickableConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = import_set_list(db, content, existing_set_mode=existing_set_mode)
    return CsvImportResponse(**_csv_result_payload(result))


@router.post("/rebrickable/sync", response_model=RebrickableSyncResponse)
def import_rebrickable_sync(
    body: RebrickableSyncRequest | None = None,
    db: Session = Depends(get_db, scope="function"),
) -> RebrickableSyncResponse:
    try:
        ensure_api_key_configured()
    except RebrickableConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    owned_set_ids = body.owned_set_ids if body is not None else None
    part_image_mode = body.part_image_download_mode if body is not None else "none"
    catalog_gap_part_keys = None
    if body is not None and body.catalog_gap_part_keys:
        catalog_gap_part_keys = tuple(
            (key.part_id, key.color_id) for key in body.catalog_gap_part_keys
        )
    result = sync_rebrickable(
        db,
        owned_set_ids=owned_set_ids,
        download_set_images=body.download_set_images if body is not None else False,
        download_missing_part_images=(
            part_image_mode == "missing"
            or (
                part_image_mode == "none"
                and (body.download_missing_part_images if body is not None else False)
            )
        ),
        download_all_part_images=part_image_mode == "all",
        download_no_element_id_part_images=part_image_mode == "no_element_id",
        catalog_gap_part_keys=catalog_gap_part_keys,
    )
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
    )


@router.post("/database", response_model=DatabaseImportResponse)
async def import_database(
    file: UploadFile = File(...),
    mode: DatabaseImportMode = Form("add_only_new"),
    db: Session = Depends(get_db, scope="function"),
) -> DatabaseImportResponse:
    raw = await file.read()
    if len(raw) > MAX_DATABASE_BYTES:
        raise HTTPException(status_code=413, detail="Database file too large")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
        tmp.write(raw)
        tmp.flush()
        try:
            validate_source_database(tmp.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = import_from_database(db, tmp.name, mode=mode)

    return DatabaseImportResponse(
        sets_added=result.sets_added,
        sets_updated=result.sets_updated,
        sets_skipped=result.sets_skipped,
        skipped_set_nums=result.skipped_set_nums,
        instances_created=result.instances_created,
        parts_upserted=result.parts_upserted,
        inventory_lines_written=result.inventory_lines_written,
    )


@router.post("/local-metadata", response_model=LocalMetadataUpdateResponse)
def update_local_metadata(db: Session = Depends(get_db, scope="function")) -> LocalMetadataUpdateResponse:
    result = update_missing_local_metadata(db)
    return LocalMetadataUpdateResponse(
        owned_set_ages_updated=result.owned_set_ages_updated,
        catalog_themes_updated=result.catalog_themes_updated,
        age_values_available=result.age_values_available,
        theme_values_available=result.theme_values_available,
    )
