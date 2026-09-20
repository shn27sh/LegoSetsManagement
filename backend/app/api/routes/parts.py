"""Part catalog endpoints (aliases)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.parts import PartAliasesReplaceRequest, PartAliasesResponse
from app.services.part_alias_service import PartAliasError, replace_part_aliases

router = APIRouter(prefix="/parts", tags=["parts"])


@router.patch("/{part_id}/aliases", response_model=PartAliasesResponse)
def patch_part_aliases(
    part_id: int,
    body: PartAliasesReplaceRequest,
    db: Session = Depends(get_db, scope="function"),
) -> PartAliasesResponse:
    try:
        part, aliases = replace_part_aliases(db, part_id, body.aliases)
    except PartAliasError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return PartAliasesResponse(
        part_id=part.id,
        part_num=part.part_num,
        aliases=aliases,
    )
