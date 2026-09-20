"""Regression: part images must be keyed by element id (color-specific), not part id."""

from app.services.image_blob import set_element_image, set_part_image
from tests.factories import (
    TINY_PNG,
    add_catalog_set,
    add_color,
    add_element_id_for_set_part_line,
    add_instance_line_for_set_part,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_same_part_num_uses_distinct_element_images_in_detail(
    api_client, db_session
) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    color_red = add_color(db_session, external_id=4, name="Red")
    color_black = add_color(db_session, external_id=0, name="Black")
    red_line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color_red,
    )
    red_line.image_url = "https://cdn.example/3024-red.png"
    black_line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color_black,
    )
    black_line.image_url = "https://cdn.example/3024-black.png"
    add_element_id_for_set_part_line(
        db_session, line=red_line, element_id="302424"
    )
    add_element_id_for_set_part_line(
        db_session, line=black_line, element_id="302401"
    )
    add_instance_line_for_set_part(db_session, owned_set=owned, catalog_line=red_line)
    add_instance_line_for_set_part(db_session, owned_set=owned, catalog_line=black_line)
    set_element_image(
        db_session,
        "302424",
        content=b"red-image",
        content_type="image/png",
    )
    set_element_image(
        db_session,
        "302401",
        content=b"black-image",
        content_type="image/png",
    )
    set_part_image(db_session, part.id, content=TINY_PNG, content_type="image/png")
    db_session.commit()

    response = api_client.get(f"/api/owned-sets/{owned.id}")
    assert response.status_code == 200
    by_color = {
        row["color_name"]: row for row in response.json()["inventory"]["set_parts"]
    }
    assert by_color["Red"]["image_url"] == "/api/elements/302424/image"
    assert by_color["Black"]["image_url"] == "/api/elements/302401/image"
    assert by_color["Red"]["image_url"] != by_color["Black"]["image_url"]
