"""Expose Rebrickable `set_num` string key from `CatalogSet` rows."""

from __future__ import annotations

from app.db.models import CatalogSet
from app.domain.lego_set_number import LegoSetId, to_rebrickable_set_num


def catalog_rebrickable_key(catalog: CatalogSet) -> str:
    return to_rebrickable_set_num(
        LegoSetId(number=catalog.set_number, variant=catalog.set_variant)
    )
