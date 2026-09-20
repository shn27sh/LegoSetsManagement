"""Remove catalog set data when no owned instances remain."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    MinifigPartInventoryLine,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
)


def delete_catalog_set_data(session: Session, catalog_set_id: int) -> None:
    minifig_ids = session.scalars(
        select(SetMinifigInventoryLine.catalog_minifig_id).where(
            SetMinifigInventoryLine.catalog_set_id == catalog_set_id
        )
    ).all()
    if minifig_ids:
        session.execute(
            delete(MinifigPartInventoryLine).where(
                MinifigPartInventoryLine.catalog_minifig_id.in_(minifig_ids)
            )
        )
        session.execute(
            delete(CatalogMinifig).where(CatalogMinifig.id.in_(minifig_ids))
        )

    session.execute(
        delete(SetMinifigInventoryLine).where(
            SetMinifigInventoryLine.catalog_set_id == catalog_set_id
        )
    )
    session.execute(
        delete(SetPartInventoryLine).where(
            SetPartInventoryLine.catalog_set_id == catalog_set_id
        )
    )

    catalog = session.get(CatalogSet, catalog_set_id)
    if catalog is not None:
        session.delete(catalog)
