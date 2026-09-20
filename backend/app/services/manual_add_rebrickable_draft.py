"""Build manual-add draft payloads from live Rebrickable (no DB writes)."""

from __future__ import annotations

from app.domain.lego_set_number import to_rebrickable_set_num
from app.importers.rebrickable_inventory_filters import include_set_part_line
from app.importers.rebrickable_sync_service import RebrickableReader
from app.schemas.manual_add import (
    ManualAddCatalogInput,
    ManualAddPartInput,
    OwnedSetRebrickableDraftResponse,
)
from app.services.manual_add_service import normalize_set_num
from app.services.theme_catalog import display_theme_for


def fetch_manual_add_rebrickable_draft(
    reader: RebrickableReader,
    set_num: str,
) -> OwnedSetRebrickableDraftResponse:
    lsid = normalize_set_num(set_num)
    rb_key = to_rebrickable_set_num(lsid)
    set_dto = reader.get_set(rb_key)
    theme_name: str | None = None
    if set_dto.theme_external_id is not None:
        theme_dto = display_theme_for(set_dto.theme_external_id)
        if theme_dto is None:
            theme_dto = reader.get_theme(set_dto.theme_external_id)
        theme_name = theme_dto.name

    catalog = ManualAddCatalogInput(
        name=set_dto.name,
        theme_name=theme_name,
        year=set_dto.year,
        num_parts=set_dto.num_parts,
    )

    parts: list[ManualAddPartInput] = []
    for line in reader.iter_set_parts(rb_key):
        if not include_set_part_line(line):
            continue
        parts.append(
            ManualAddPartInput(
                part_num=line.part.part_num,
                part_name=line.part.name,
                color_id=line.color.external_id,
                color_name=line.color.name,
                quantity=line.quantity,
            )
        )

    return OwnedSetRebrickableDraftResponse(
        set_num=lsid.number,
        catalog=catalog,
        age=set_dto.age,
        parts=parts,
    )
