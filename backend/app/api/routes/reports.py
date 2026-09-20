from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.reports import (
    IncompleteCatalogReportResponse,
    IncompleteSetsReportResponse,
    MissingPartsReportResponse,
    ReportsSummaryResponse,
)
from app.services.reports_service import (
    get_summary,
    list_incomplete_catalog_parts,
    list_incomplete_sets,
    list_missing_parts,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=ReportsSummaryResponse)
def reports_summary(db: Session = Depends(get_db, scope="function")) -> ReportsSummaryResponse:
    return get_summary(db)


@router.get("/incomplete-sets", response_model=IncompleteSetsReportResponse)
def reports_incomplete_sets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db, scope="function"),
) -> IncompleteSetsReportResponse:
    return list_incomplete_sets(db, limit=limit, offset=offset)


@router.get("/missing-parts", response_model=MissingPartsReportResponse)
def reports_missing_parts(
    owned_set_ids: list[int] | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db, scope="function"),
) -> MissingPartsReportResponse:
    return list_missing_parts(
        db,
        owned_set_ids=owned_set_ids,
        limit=limit,
        offset=offset,
    )


@router.get("/incomplete-catalog", response_model=IncompleteCatalogReportResponse)
def reports_incomplete_catalog(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db, scope="function"),
) -> IncompleteCatalogReportResponse:
    return list_incomplete_catalog_parts(db, limit=limit, offset=offset)
