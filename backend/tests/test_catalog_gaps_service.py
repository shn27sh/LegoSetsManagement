from app.services.part_color_catalog_service import element_ids_for_part_color
from tests.factories import (
    add_catalog_set,
    add_color,
    add_element_id_for_set_part_line,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_catalog_gaps_use_shared_part_color_element_ids(db_session) -> None:
    """Gap detection reads canonical part-color Element IDs, not per-set copies."""
    color = add_color(db_session, external_id=70, name="Reddish Brown")
    part = add_part(db_session, part_num="4079b")
    catalog = add_catalog_set(db_session, set_number=10734)
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="4211206")
    add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    assert element_ids_for_part_color(db_session, part.id, color.id) == ["4211206"]
