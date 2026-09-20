"""Serve and upload image BLOBs for parts and catalog sets."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config.image_settings import get_max_image_bytes
from app.db.deps import get_db
from app.schemas.images import ImageDeleteResponse, ImageUploadResponse
from app.services.image_blob import (
    ImageBlobError,
    clear_element_image,
    clear_catalog_set_image,
    clear_catalog_minifig_image,
    clear_part_image,
    get_catalog_minifig_image,
    get_catalog_set_image,
    get_element_image,
    get_part_image,
    set_catalog_minifig_image,
    set_catalog_set_image,
    set_part_image,
)
from app.services.image_urls import (
    catalog_minifig_image_url,
    catalog_set_image_url,
    element_image_url,
    part_image_url,
)

router = APIRouter(tags=["images"])


def _image_response(stored) -> Response:
    return Response(content=stored.content, media_type=stored.content_type)


def _raise_image_error(exc: ImageBlobError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/parts/{part_id}/image")
def get_part_image_route(part_id: int, db: Session = Depends(get_db, scope="function")) -> Response:
    stored = get_part_image(db, part_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return _image_response(stored)


@router.put("/parts/{part_id}/image", response_model=ImageUploadResponse)
async def put_part_image_route(
    part_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db, scope="function"),
) -> ImageUploadResponse:
    raw = await file.read()
    if len(raw) > get_max_image_bytes():
        raise HTTPException(status_code=413, detail="Image file too large")
    try:
        set_part_image(db, part_id, content=raw, content_type=file.content_type or "")
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageUploadResponse(image_url=part_image_url(part_id))


@router.delete("/parts/{part_id}/image", response_model=ImageDeleteResponse)
def delete_part_image_route(
    part_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> ImageDeleteResponse:
    try:
        clear_part_image(db, part_id)
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageDeleteResponse(image_url=None)


@router.get("/catalog-sets/{catalog_set_id}/image")
def get_catalog_set_image_route(
    catalog_set_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> Response:
    stored = get_catalog_set_image(db, catalog_set_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return _image_response(stored)


@router.put("/catalog-sets/{catalog_set_id}/image", response_model=ImageUploadResponse)
async def put_catalog_set_image_route(
    catalog_set_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db, scope="function"),
) -> ImageUploadResponse:
    raw = await file.read()
    if len(raw) > get_max_image_bytes():
        raise HTTPException(status_code=413, detail="Image file too large")
    try:
        set_catalog_set_image(
            db,
            catalog_set_id,
            content=raw,
            content_type=file.content_type or "",
        )
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageUploadResponse(image_url=catalog_set_image_url(catalog_set_id))


@router.delete("/catalog-sets/{catalog_set_id}/image", response_model=ImageDeleteResponse)
def delete_catalog_set_image_route(
    catalog_set_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> ImageDeleteResponse:
    try:
        clear_catalog_set_image(db, catalog_set_id)
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageDeleteResponse(image_url=None)


@router.get("/catalog-minifigs/{catalog_minifig_id}/image")
def get_catalog_minifig_image_route(
    catalog_minifig_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> Response:
    stored = get_catalog_minifig_image(db, catalog_minifig_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return _image_response(stored)


@router.put("/catalog-minifigs/{catalog_minifig_id}/image", response_model=ImageUploadResponse)
async def put_catalog_minifig_image_route(
    catalog_minifig_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db, scope="function"),
) -> ImageUploadResponse:
    raw = await file.read()
    if len(raw) > get_max_image_bytes():
        raise HTTPException(status_code=413, detail="Image file too large")
    try:
        set_catalog_minifig_image(
            db,
            catalog_minifig_id,
            content=raw,
            content_type=file.content_type or "",
        )
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageUploadResponse(image_url=catalog_minifig_image_url(catalog_minifig_id))


@router.delete(
    "/catalog-minifigs/{catalog_minifig_id}/image",
    response_model=ImageDeleteResponse,
)
def delete_catalog_minifig_image_route(
    catalog_minifig_id: int,
    db: Session = Depends(get_db, scope="function"),
) -> ImageDeleteResponse:
    try:
        clear_catalog_minifig_image(db, catalog_minifig_id)
    except ImageBlobError as exc:
        _raise_image_error(exc)
    return ImageDeleteResponse(image_url=None)


@router.get("/elements/{element_id}/image")
def get_element_image_route(element_id: str, db: Session = Depends(get_db, scope="function")) -> Response:
    stored = get_element_image(db, element_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return _image_response(stored)
