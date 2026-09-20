from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.image_settings import get_max_image_bytes
from app.db.deps import get_db
from app.db.models import CatalogSet
from app.schemas.missing import (
    MissingImageResponse,
    MissingUpsertRequest,
    MissingUpsertResponse,
)
from app.schemas.instance_inventory import (
    AddSetPartLineRequest,
    InstanceInventoryLineResponse,
    InstanceInventoryLineUpdate,
    UpdateSetPartLineRequest,
)
from app.schemas.manual_add import (
    OwnedSetAddPreviewResponse,
    OwnedSetCreateRequest,
    OwnedSetCreateResponse,
    OwnedSetRebrickableDraftResponse,
)
from app.schemas.owned_sets import (
    DuplicatePreviewResponse,
    DuplicateRequest,
    OwnedSetDeleteResponse,
    OwnedSetDetailResponse,
    OwnedSetDuplicateResponse,
    OwnedSetListItem,
    OwnedSetListResponse,
    OwnedSetThemeOptionsResponse,
    OwnedSetUpdateRequest,
)
from app.importers.rebrickable_sync_service import ensure_api_key_configured
from app.rebrickable.client import RebrickableClient
from app.rebrickable.exceptions import RebrickableAPIError, RebrickableConfigError
from app.services.manual_add_rebrickable_draft import fetch_manual_add_rebrickable_draft
from app.services.manual_add_service import (
    create_owned_set_manual,
    get_add_preview,
    normalize_set_num,
)
from app.services.missing_items_service import (
    MissingItemError,
    delete_missing_image,
    upload_missing_image,
    upsert_missing,
)
from app.services.instance_inventory import (
    InstanceInventoryError,
    update_instance_inventory_line,
)
from app.services.inventory_parts_service import (
    InventoryPartsError,
    add_set_part_to_owned_set,
    delete_set_part_from_owned_set,
    instance_line_response,
    update_set_part_on_owned_set,
)
from app.services.owned_sets_service import (
    OwnedSetServiceError,
    delete_owned_set,
    duplicate_owned_set,
    get_duplicate_preview,
    get_owned_set_detail,
    list_owned_set_theme_options,
    list_owned_sets,
    update_owned_set,
)

router = APIRouter(prefix="/owned-sets", tags=["owned-sets"])


@router.get("", response_model=OwnedSetListResponse)
def get_owned_sets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    investigated: bool | None = None,
    theme: list[str] = Query(default_factory=list),
    missing_only: bool = False,
    sort_by: str = Query(
        "created",
        pattern="^(created|set_num|name|theme|num_parts|age)$",
    ),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetListResponse:
    return list_owned_sets(
        db,
        limit=limit,
        offset=offset,
        investigated=investigated,
        themes=theme,
        missing_only=missing_only,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/theme-options", response_model=OwnedSetThemeOptionsResponse)
def get_owned_set_theme_options(
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetThemeOptionsResponse:
    return OwnedSetThemeOptionsResponse(themes=list_owned_set_theme_options(db))


@router.get("/add-preview", response_model=OwnedSetAddPreviewResponse)
def get_owned_set_add_preview(
    set_num: str = Query(..., min_length=1),
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetAddPreviewResponse:
    try:
        return get_add_preview(db, set_num)
    except OwnedSetServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/add-rebrickable-draft", response_model=OwnedSetRebrickableDraftResponse)
def get_manual_add_rebrickable_draft(
    set_num: str = Query(..., min_length=1),
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetRebrickableDraftResponse:
    """Return catalog metadata + non-spare/non-alternate set part lines for wizard prefill."""
    try:
        lsid = normalize_set_num(set_num)
    except OwnedSetServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    existing = db.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == lsid.number,
            CatalogSet.set_variant == lsid.variant,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="This set number is already in your catalog; use Add set preview to add another copy.",
        )

    try:
        ensure_api_key_configured()
    except RebrickableConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with RebrickableClient() as client:
            return fetch_manual_add_rebrickable_draft(client, set_num)
    except RebrickableAPIError as exc:
        message = str(exc)
        if exc.status_code == 404:
            message = "Set not found in Rebrickable"
        raise HTTPException(status_code=502, detail=message) from exc


@router.post("", response_model=OwnedSetCreateResponse, status_code=201)
def post_owned_set(
    body: OwnedSetCreateRequest,
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetCreateResponse:
    try:
        return create_owned_set_manual(db, body)
    except OwnedSetServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{owned_set_id}", response_model=OwnedSetDetailResponse)
def get_owned_set(
    owned_set_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetDetailResponse:
    detail = get_owned_set_detail(db, owned_set_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Set copy not found")
    return detail


@router.post(
    "/{owned_set_id}/set-parts",
    response_model=InstanceInventoryLineResponse,
    status_code=201,
)
def post_set_part_line(
    owned_set_id: int,
    body: AddSetPartLineRequest,
    db: Session = Depends(get_db, scope="function"),
) -> InstanceInventoryLineResponse:
    from app.schemas.manual_add import ManualAddPartInput

    try:
        line = add_set_part_to_owned_set(
            db,
            owned_set_id,
            ManualAddPartInput.model_validate(body.model_dump()),
        )
    except InventoryPartsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return instance_line_response(db, line)


@router.patch(
    "/{owned_set_id}/set-parts/{instance_line_id}",
    response_model=InstanceInventoryLineResponse,
)
def patch_set_part_line(
    owned_set_id: int,
    instance_line_id: int,
    body: UpdateSetPartLineRequest,
    db: Session = Depends(get_db, scope="function"),
) -> InstanceInventoryLineResponse:
    try:
        line = update_set_part_on_owned_set(db, owned_set_id, instance_line_id, body)
    except InventoryPartsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return instance_line_response(db, line)


@router.delete(
    "/{owned_set_id}/set-parts/{instance_line_id}",
    status_code=204,
)
def delete_set_part_line(
    owned_set_id: int,
    instance_line_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> None:
    try:
        delete_set_part_from_owned_set(db, owned_set_id, instance_line_id)
    except InventoryPartsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch(
    "/{owned_set_id}/inventory-lines/{instance_line_id}",
    response_model=InstanceInventoryLineResponse,
)
def patch_instance_inventory_line(
    owned_set_id: int,
    instance_line_id: int,
    body: InstanceInventoryLineUpdate,
    db: Session = Depends(get_db, scope="function"),
) -> InstanceInventoryLineResponse:
    if body.quantity is None and body.quantity_missing is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of quantity or quantity_missing is required",
        )
    try:
        line = update_instance_inventory_line(
            db,
            owned_set_id,
            instance_line_id,
            quantity=body.quantity,
            quantity_missing=body.quantity_missing,
        )
    except InstanceInventoryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    from app.db.models import MinifigPartInventoryLine, SetPartInventoryLine

    if line.set_part_inventory_line_id is not None:
        catalog_line = db.get(SetPartInventoryLine, line.set_part_inventory_line_id)
        if catalog_line is not None:
            return InstanceInventoryLineResponse(
                instance_line_id=line.id,
                part_id=catalog_line.part_id,
                catalog_line_id=catalog_line.id,
                quantity=line.quantity,
                quantity_missing=line.quantity_missing,
            )
    if line.minifig_part_inventory_line_id is not None:
        mf_line = db.get(
            MinifigPartInventoryLine, line.minifig_part_inventory_line_id
        )
        if mf_line is not None:
            return InstanceInventoryLineResponse(
                instance_line_id=line.id,
                part_id=mf_line.part_id,
                catalog_line_id=mf_line.id,
                quantity=line.quantity,
                quantity_missing=line.quantity_missing,
            )
    raise HTTPException(status_code=500, detail="Inventory line has no catalog reference")


@router.patch("/{owned_set_id}", response_model=OwnedSetListItem)
def patch_owned_set(
    owned_set_id: int,
    body: OwnedSetUpdateRequest,
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetListItem:
    try:
        updated = update_owned_set(db, owned_set_id, body)
    except OwnedSetServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Set copy not found")
    return updated


@router.delete("/{owned_set_id}", response_model=OwnedSetDeleteResponse)
def delete_owned_set_route(
    owned_set_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetDeleteResponse:
    deleted = delete_owned_set(db, owned_set_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Set copy not found")
    return deleted


@router.get(
    "/{owned_set_id}/duplicate-preview",
    response_model=DuplicatePreviewResponse,
)
def get_duplicate_preview_route(
    owned_set_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> DuplicatePreviewResponse:
    preview = get_duplicate_preview(db, owned_set_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Set copy not found")
    return preview


@router.post("/{owned_set_id}/duplicate", response_model=OwnedSetDuplicateResponse, status_code=201)
def post_duplicate_owned_set(
    owned_set_id: int,
    body: DuplicateRequest | None = None,
    db: Session = Depends(get_db, scope="function"),
) -> OwnedSetDuplicateResponse:
    label = body.label if body is not None else None
    duplicated = duplicate_owned_set(db, owned_set_id, label=label)
    if duplicated is None:
        raise HTTPException(status_code=404, detail="Set copy not found")
    return duplicated


def _raise_missing_error(exc: MissingItemError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch("/{owned_set_id}/missing", response_model=MissingUpsertResponse)
def patch_missing_item(
    owned_set_id: int,
    body: MissingUpsertRequest,
    db: Session = Depends(get_db, scope="function"),
) -> MissingUpsertResponse:
    try:
        return upsert_missing(db, owned_set_id, body)
    except MissingItemError as exc:
        _raise_missing_error(exc)
    raise AssertionError("unreachable")


@router.put(
    "/{owned_set_id}/missing/{missing_item_id}/image",
    response_model=MissingImageResponse,
)
async def put_missing_image(
    owned_set_id: int,
    missing_item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db, scope="function"),
) -> MissingImageResponse:
    raw = await file.read()
    max_bytes = get_max_image_bytes()
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="Image file too large")
    content_type = file.content_type or ""
    try:
        return upload_missing_image(
            db,
            owned_set_id,
            missing_item_id,
            content=raw,
            content_type=content_type,
        )
    except MissingItemError as exc:
        _raise_missing_error(exc)
    raise AssertionError("unreachable")


@router.delete(
    "/{owned_set_id}/missing/{missing_item_id}/image",
    response_model=MissingImageResponse,
)
def delete_missing_image_route(
    owned_set_id: int,
    missing_item_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> MissingImageResponse:
    try:
        return delete_missing_image(db, owned_set_id, missing_item_id)
    except MissingItemError as exc:
        _raise_missing_error(exc)
    raise AssertionError("unreachable")
