from typing import Any, Literal

from pydantic import BaseModel, Field

ImportJobKind = Literal["csv", "rebrickable_sync", "database"]
ImportJobStatus = Literal[
    "queued", "running", "completed", "failed", "cancelled"
]

PartImageDownloadMode = Literal["none", "missing", "all", "no_element_id"]
ExistingSetImportMode = Literal["skip", "copy"]
DatabaseImportMode = Literal["add_only_new", "add_and_update"]


class CsvTokenError(BaseModel):
    token_index: int
    raw: str
    message: str


class CsvImportSetFailure(BaseModel):
    token_index: int
    set_num: int
    message: str


class CsvImportSkippedExistingSet(BaseModel):
    token_index: int
    set_num: str


class ImageDownloadFailure(BaseModel):
    target: str
    url: str
    message: str


class CsvImportResponse(BaseModel):
    instances_created: int
    catalog_stubs_created: int
    sets_fetched: int = 0
    existing_sets_skipped: int = 0
    skipped_existing_sets: list[CsvImportSkippedExistingSet] = Field(default_factory=list)
    sets_failed: list[CsvImportSetFailure] = Field(default_factory=list)
    errors: list[CsvTokenError]
    set_images_downloaded: int = 0
    minifig_images_downloaded: int = 0
    part_images_downloaded: int = 0
    image_downloads_failed: list[ImageDownloadFailure] = Field(default_factory=list)


class CatalogGapPartKey(BaseModel):
    part_id: int
    color_id: int


class RebrickableSyncRequest(BaseModel):
    owned_set_ids: list[int] | None = None
    download_set_images: bool = False
    download_missing_part_images: bool = False
    part_image_download_mode: PartImageDownloadMode = "none"
    catalog_gap_part_keys: list[CatalogGapPartKey] | None = None


class RebrickableSetSyncFailure(BaseModel):
    set_num: str
    message: str


class RebrickableSyncResponse(BaseModel):
    sets_synced: int
    sets_failed: list[RebrickableSetSyncFailure] = Field(default_factory=list)
    parts_upserted: int
    inventory_lines_written: int
    set_images_downloaded: int = 0
    minifig_images_downloaded: int = 0
    part_images_downloaded: int = 0
    image_downloads_failed: list[ImageDownloadFailure] = Field(default_factory=list)


class LocalMetadataUpdateResponse(BaseModel):
    owned_set_ages_updated: int
    catalog_themes_updated: int
    age_values_available: int
    theme_values_available: int


class DatabaseImportResponse(BaseModel):
    sets_added: int
    sets_updated: int
    sets_skipped: int
    skipped_set_nums: list[str] = Field(default_factory=list)
    instances_created: int
    parts_upserted: int
    inventory_lines_written: int


class ImportJobProgress(BaseModel):
    current: int
    total: int
    label: str


class ImportJobStartResponse(BaseModel):
    job_id: str
    status: ImportJobStatus


class ImportJobStatusResponse(BaseModel):
    job_id: str
    kind: ImportJobKind
    status: ImportJobStatus
    progress: ImportJobProgress | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    failed_sets_csv_path: str | None = None
