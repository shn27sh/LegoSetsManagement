"""Create physical set copies (`owned_sets`) from parsed set numbers with Rebrickable fetch."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.import_progress import commit_import_progress
from app.db.models import CatalogSet, OwnedSet
from app.domain.lego_set_number import LegoSetId, parse_user_set_number, to_rebrickable_set_num
from app.importers.rebrickable_catalog import utc_now
from app.importers.rebrickable_sync_service import (
    ImageSyncFailure,
    RebrickableReader,
    RebrickableSyncResult,
    _format_api_error,
    _run_image_download_phase,
    sync_one_catalog_set,
)
from app.services.image_download import ImageDownloader, image_downloader_for_sync
from app.importers.import_job_types import ProgressCallback
from app.importers.import_progress_callback import check_import_cancelled
from app.importers.set_list_parser import ParseError, parse_set_list_entries
from app.rebrickable.client import RebrickableClient
from app.rebrickable.exceptions import RebrickableAPIError
from app.services.failed_sets_csv import failed_sets_import_run
from app.services.failure_log import record_import_failure
from app.services.instance_inventory import clone_instance_inventory
from app.services.owned_sets_service import _apply_shared_age

logger = logging.getLogger(__name__)

CSV_STUB_SOURCE = "csv_import"


@dataclass
class CsvImportSkippedExistingSet:
    token_index: int
    set_num: str


@dataclass
class CsvImportSetFailure:
    token_index: int
    set_num: int
    message: str


@dataclass
class CsvImportResult:
    instances_created: int
    catalog_stubs_created: int
    sets_fetched: int
    existing_sets_skipped: int
    skipped_existing_sets: list[CsvImportSkippedExistingSet]
    sets_failed: list[CsvImportSetFailure]
    errors: list[ParseError]
    set_images_downloaded: int = 0
    minifig_images_downloaded: int = 0
    part_images_downloaded: int = 0
    image_downloads_failed: list[ImageSyncFailure] = field(default_factory=list)


def _ensure_catalog_stub(session: Session, lsid: LegoSetId) -> tuple[CatalogSet, bool]:
    rb_key = to_rebrickable_set_num(lsid)
    catalog_set = session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
    )
    if catalog_set is not None:
        return catalog_set, False
    catalog_set = CatalogSet(
        set_number=lsid.number,
        set_variant=lsid.variant,
        source=CSV_STUB_SOURCE,
        source_ref=rb_key,
        fetched_at=utc_now(),
    )
    session.add(catalog_set)
    session.flush()
    return catalog_set, True


def _create_owned_instance(session: Session, catalog_set: CatalogSet) -> OwnedSet:
    existing_age = session.scalar(
        select(OwnedSet.age)
        .where(
            OwnedSet.catalog_set_id == catalog_set.id,
            OwnedSet.age.is_not(None),
        )
        .order_by(OwnedSet.id)
        .limit(1)
    )
    owned = OwnedSet(
        catalog_set_id=catalog_set.id,
        investigated=False,
        age=existing_age,
        created_at=utc_now(),
    )
    session.add(owned)
    session.flush()
    clone_instance_inventory(session, owned.id)
    return owned


def import_set_list(
    session: Session,
    content: str,
    *,
    client: RebrickableReader | None = None,
    existing_set_mode: str = "skip",
    cancel_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
    image_downloader: ImageDownloader | None = None,
) -> CsvImportResult:
    valid_entries, errors = parse_set_list_entries(content)
    total_tokens = len(valid_entries)
    instances_created = 0
    catalog_stubs_created = 0
    sets_fetched = 0
    existing_sets_skipped = 0
    skipped_existing_sets: list[CsvImportSkippedExistingSet] = []
    sets_failed: list[CsvImportSetFailure] = []

    logger.info(
        "CSV import started tokens=%s parse_errors=%s",
        len(valid_entries),
        len(errors),
    )

    image_stats = RebrickableSyncResult()

    with failed_sets_import_run() as record_failed_set:
        with image_downloader_for_sync(
            image_downloader, images_enabled=True
        ) as downloader:

            def process_token(
                token_index: int,
                raw_token: str,
                rb_client: RebrickableReader,
            ) -> None:
                nonlocal instances_created, catalog_stubs_created, sets_fetched
                nonlocal existing_sets_skipped, skipped_existing_sets

                lsid = parse_user_set_number(raw_token)
                rb_key = to_rebrickable_set_num(lsid)
                existing_catalog = session.scalar(
                    select(CatalogSet).where(
                        CatalogSet.set_number == lsid.number,
                        CatalogSet.set_variant == lsid.variant,
                    )
                )
                if existing_catalog is not None:
                    if existing_set_mode == "copy":
                        _create_owned_instance(session, existing_catalog)
                        instances_created += 1
                        logger.info("CSV import token_existing_copy rb_key=%s", rb_key)
                        commit_import_progress(session)
                    else:
                        existing_sets_skipped += 1
                        skipped_existing_sets.append(
                            CsvImportSkippedExistingSet(
                                token_index=token_index,
                                set_num=raw_token,
                            )
                        )
                        logger.info("CSV import token_existing_skipped rb_key=%s", rb_key)
                    return

                try:
                    recommended_age: int | None = None
                    with session.begin_nested():
                        _parts, _lines, recommended_age = sync_one_catalog_set(
                            session,
                            rb_client,
                            rb_key,
                            persist_image_urls=True,
                        )
                    catalog_set = session.scalar(
                        select(CatalogSet).where(
                            CatalogSet.set_number == lsid.number,
                            CatalogSet.set_variant == lsid.variant,
                        )
                    )
                    if catalog_set is None:
                        raise RuntimeError(f"catalog missing after sync for {rb_key}")
                    _create_owned_instance(session, catalog_set)
                    if recommended_age is not None:
                        _apply_shared_age(session, catalog_set.id, recommended_age)
                    instances_created += 1
                    sets_fetched += 1
                    if downloader is not None:
                        def image_progress(
                            _current: int, _total: int, label: str
                        ) -> None:
                            if on_progress is not None:
                                on_progress(token_index, total_tokens, label)

                        _run_image_download_phase(
                            session,
                            [rb_key],
                            downloader,
                            image_stats,
                            download_set_images=True,
                            download_missing_part_images=False,
                            download_all_part_images=True,
                            cancel_event=cancel_event,
                            on_progress=image_progress,
                        )
                    logger.info("CSV import token_ok rb_key=%s", rb_key)
                    commit_import_progress(session)
                except RebrickableAPIError as exc:
                    message = _format_api_error(exc)
                    logger.warning(
                        "CSV import token_failed token_index=%s rb_key=%s error=%s",
                        token_index,
                        rb_key,
                        message,
                    )
                    record_import_failure(
                        operation="csv_import",
                        token_index=token_index,
                        set_num=lsid.number,
                        rb_key=rb_key,
                        message=message,
                        error_type=type(exc).__name__,
                    )
                    record_failed_set(rb_key)
                    with session.begin_nested():
                        catalog_set, created_stub = _ensure_catalog_stub(session, lsid)
                        if created_stub:
                            catalog_stubs_created += 1
                        _create_owned_instance(session, catalog_set)
                    instances_created += 1
                    sets_failed.append(
                        CsvImportSetFailure(
                            token_index=token_index,
                            set_num=lsid.number,
                            message=message,
                        )
                    )
                    commit_import_progress(session)
                except Exception as exc:
                    logger.exception(
                        "CSV import token_failed token_index=%s rb_key=%s",
                        token_index,
                        rb_key,
                    )
                    record_import_failure(
                        operation="csv_import",
                        token_index=token_index,
                        set_num=lsid.number,
                        rb_key=rb_key,
                        message=str(exc),
                        error_type=type(exc).__name__,
                    )
                    with session.begin_nested():
                        catalog_set, created_stub = _ensure_catalog_stub(session, lsid)
                        if created_stub:
                            catalog_stubs_created += 1
                        _create_owned_instance(session, catalog_set)
                    instances_created += 1
                    sets_failed.append(
                        CsvImportSetFailure(
                            token_index=token_index,
                            set_num=lsid.number,
                            message=str(exc),
                        )
                    )
                    commit_import_progress(session)

            if client is not None:
                for step, (token_index, set_num) in enumerate(valid_entries):
                    check_import_cancelled(cancel_event)
                    if on_progress is not None:
                        on_progress(step, total_tokens, f"Importing {set_num}")
                    process_token(token_index, set_num, client)
            else:
                with RebrickableClient() as rb_client:
                    for step, (token_index, set_num) in enumerate(valid_entries):
                        check_import_cancelled(cancel_event)
                        if on_progress is not None:
                            on_progress(step, total_tokens, f"Importing {set_num}")
                        process_token(token_index, set_num, rb_client)

    session.flush()
    result = CsvImportResult(
        instances_created=instances_created,
        catalog_stubs_created=catalog_stubs_created,
        sets_fetched=sets_fetched,
        existing_sets_skipped=existing_sets_skipped,
        skipped_existing_sets=skipped_existing_sets,
        sets_failed=sets_failed,
        errors=errors,
        set_images_downloaded=image_stats.set_images_downloaded,
        minifig_images_downloaded=image_stats.minifig_images_downloaded,
        part_images_downloaded=image_stats.part_images_downloaded,
        image_downloads_failed=image_stats.image_downloads_failed,
    )
    logger.info(
        "CSV import finished instances_created=%s sets_fetched=%s "
        "catalog_stubs_created=%s existing_sets_skipped=%s sets_failed=%s token_errors=%s",
        result.instances_created,
        result.sets_fetched,
        result.catalog_stubs_created,
        result.existing_sets_skipped,
        len(result.sets_failed),
        len(result.errors),
    )
    return result
