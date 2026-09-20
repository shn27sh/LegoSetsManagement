from tests.factories import (
    add_catalog_set,
    add_color,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_incomplete_catalog_empty_collection(api_client) -> None:
    response = api_client.get("/api/reports/incomplete-catalog")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_incomplete_catalog_lists_part_without_element_id(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="4079b")
    color = add_color(db_session, external_id=70, name="Reddish Brown")
    add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
        quantity=2,
    )
    add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["part_num"] == "4079b"
    assert item["color_id"] == 70
    assert item["element_ids"] == []
    assert item["missing_element_id"] is True
    assert len(item["sets"]) == 1
    assert item["sets"][0]["set_num"] == 6024


def test_incomplete_catalog_aggregates_same_part_color(api_client, db_session) -> None:
    catalog_a = add_catalog_set(db_session, set_number=1001)
    catalog_b = add_catalog_set(db_session, set_number=1002)
    part = add_part(db_session, part_num="30237a")
    color = add_color(db_session, external_id=72, name="Dark Bluish Gray")
    add_set_part_inventory_line(
        db_session, catalog_set=catalog_a, part=part, color=color
    )
    add_set_part_inventory_line(
        db_session, catalog_set=catalog_b, part=part, color=color
    )
    add_owned_set(db_session, catalog_a, with_inventory=True)
    add_owned_set(db_session, catalog_b, with_inventory=True)
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"][0]["sets"]) == 2
