from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.search import SearchResponse
from app.services.search_service import search

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def get_search(
    q: str = Query(...),
    search_type: str = Query("all", alias="type", pattern="^(set|part|element|all)$"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db, scope="function"),
) -> SearchResponse:
    trimmed = q.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Search query must not be empty")
    return search(db, q=trimmed, search_type=search_type, limit=limit, offset=offset)
