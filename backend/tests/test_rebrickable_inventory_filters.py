"""Rebrickable spare/alternate rows are filtered before catalog persistence."""

from app.importers.rebrickable_inventory_filters import (
    include_minifig_part_line,
    include_set_part_line,
)
from app.rebrickable.dto import ColorDTO, MinifigPartLineDTO, PartDTO, SetPartLineDTO


def _set_line(*, is_spare: bool = False, is_alternate: bool = False) -> SetPartLineDTO:
    return SetPartLineDTO(
        part=PartDTO(part_num="3024", name="Plate", image_url=None, aliases=()),
        color=ColorDTO(external_id=0, name="Black", rgb=None),
        quantity=1,
        is_spare=is_spare,
        is_alternate=is_alternate,
        image_url=None,
        inventory_id=1,
    )


def _minifig_line(*, is_spare: bool = False) -> MinifigPartLineDTO:
    return MinifigPartLineDTO(
        part=PartDTO(part_num="973", name="Torso", image_url=None, aliases=()),
        color=ColorDTO(external_id=0, name="Black", rgb=None),
        quantity=1,
        is_spare=is_spare,
        image_url=None,
    )


def test_include_set_part_line_keeps_regular_parts() -> None:
    assert include_set_part_line(_set_line()) is True


def test_include_set_part_line_skips_spare_and_alternate() -> None:
    assert include_set_part_line(_set_line(is_spare=True)) is False
    assert include_set_part_line(_set_line(is_alternate=True)) is False


def test_include_minifig_part_line_skips_spare() -> None:
    assert include_minifig_part_line(_minifig_line()) is True
    assert include_minifig_part_line(_minifig_line(is_spare=True)) is False
