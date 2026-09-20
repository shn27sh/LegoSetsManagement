"""Decide which Rebrickable inventory rows are stored in the local catalog."""

from app.rebrickable.dto import MinifigPartLineDTO, SetPartLineDTO


def include_set_part_line(line: SetPartLineDTO) -> bool:
    """Spare and alternate Rebrickable lines are not persisted."""
    return not line.is_spare and not line.is_alternate


def include_minifig_part_line(line: MinifigPartLineDTO) -> bool:
    """Spare minifig BOM lines are not persisted."""
    return not line.is_spare
