"""Add set-part line to set copy `/owned-sets/{id}/set-parts`."""

from tests.factories import (
    add_catalog_set,
    add_color,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_add_set_part_to_instance(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.post(
        f"/api/owned-sets/{owned.id}/set-parts",
        json={
            "part_num": "3024",
            "part_name": "Plate 1 x 1",
            "color_id": 0,
            "color_name": "Black",
            "quantity": 2,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 2
    assert body["quantity_missing"] == 0
    assert "part_id" in body
    assert "catalog_line_id" in body

    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    assert len(detail["inventory"]["set_parts"]) == 1
    assert detail["inventory"]["set_parts"][0]["part_num"] == "3024"


def test_add_set_part_duplicate_returns_409(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
        quantity=1,
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    response = api_client.post(
        f"/api/owned-sets/{owned.id}/set-parts",
        json={
            "part_num": "3024",
            "color_id": 0,
            "quantity": 1,
        },
    )
    assert response.status_code == 409
