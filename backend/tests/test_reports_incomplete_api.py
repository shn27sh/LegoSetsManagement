from sqlalchemy import select

from app.db.models import OwnedSetInventoryLine
from tests.factories import (
    add_catalog_set,
    add_color,
    add_element_id_for_set_part_line,
    add_missing_item_for_set_line,
    add_minifig_with_parts,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_incomplete_sets_empty_collection(api_client) -> None:
    response = api_client.get("/api/reports/incomplete-sets")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_incomplete_sets_excludes_complete_copies(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3001")
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
    )
    incomplete = add_owned_set(db_session, catalog, investigated=False, label="copy A")
    add_owned_set(db_session, catalog, investigated=True, label="copy B")
    add_missing_item_for_set_line(
        db_session,
        owned_set=incomplete,
        line=line,
        quantity_missing=2,
    )
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-sets")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == incomplete.id
    assert item["missing_line_count"] == 1
    assert item["missing_parts_total"] == 2
    assert len(item["missing_lines"]) == 1
    missing_line = item["missing_lines"][0]
    assert missing_line["part_num"] == "3001"
    assert missing_line["color_name"] == "Black"
    assert missing_line["quantity_missing"] == 2


def test_incomplete_sets_includes_minifig_bom_line(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    _minifig, _mf_line, bom_line = add_minifig_with_parts(db_session, catalog_set=catalog)
    owned = add_owned_set(db_session, catalog, investigated=True)
    instance = db_session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == owned.id,
            OwnedSetInventoryLine.minifig_part_inventory_line_id == bom_line.id,
        )
    )
    assert instance is not None
    instance.quantity_missing = 1
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-sets")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["missing_lines"][0]["part_num"] == "973"


def test_incomplete_sets_pagination(api_client, db_session) -> None:
    catalog_a = add_catalog_set(db_session, set_number=1001)
    catalog_b = add_catalog_set(db_session, set_number=1002)
    part = add_part(db_session, part_num="3001")
    color = add_color(db_session)
    line_a = add_set_part_inventory_line(
        db_session, catalog_set=catalog_a, part=part, color=color
    )
    line_b = add_set_part_inventory_line(
        db_session, catalog_set=catalog_b, part=part, color=color
    )
    owned_a = add_owned_set(db_session, catalog_a)
    owned_b = add_owned_set(db_session, catalog_b)
    add_missing_item_for_set_line(db_session, owned_set=owned_a, line=line_a)
    add_missing_item_for_set_line(db_session, owned_set=owned_b, line=line_b)
    db_session.commit()

    page_one = api_client.get("/api/reports/incomplete-sets", params={"limit": 1, "offset": 0})
    page_two = api_client.get("/api/reports/incomplete-sets", params={"limit": 1, "offset": 1})

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert page_one.json()["total"] == 2
    assert len(page_one.json()["items"]) == 1
    assert len(page_two.json()["items"]) == 1
    assert page_one.json()["items"][0]["id"] != page_two.json()["items"][0]["id"]


def test_incomplete_sets_includes_element_ids(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="302400")
    owned = add_owned_set(db_session, catalog)
    add_missing_item_for_set_line(db_session, owned_set=owned, line=line)
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-sets")
    assert response.status_code == 200
    missing_line = response.json()["items"][0]["missing_lines"][0]
    assert missing_line["element_ids"] == ["302400"]


def test_incomplete_sets_sorts_missing_lines_by_color_then_element_id(
    api_client, db_session
) -> None:
    catalog = add_catalog_set(db_session)
    part_a = add_part(db_session, part_num="3001")
    part_b = add_part(db_session, part_num="3002")
    color_black = add_color(db_session, external_id=0, name="Black")
    color_red = add_color(db_session, external_id=4, name="Red")
    line_black = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part_a,
        color=color_black,
    )
    line_red = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part_b,
        color=color_red,
    )
    add_element_id_for_set_part_line(db_session, line=line_black, element_id="302400")
    add_element_id_for_set_part_line(db_session, line=line_red, element_id="300121")
    owned = add_owned_set(db_session, catalog)
    add_missing_item_for_set_line(db_session, owned_set=owned, line=line_red)
    add_missing_item_for_set_line(db_session, owned_set=owned, line=line_black)
    db_session.commit()

    response = api_client.get("/api/reports/incomplete-sets")
    assert response.status_code == 200
    lines = response.json()["items"][0]["missing_lines"]
    assert [line["color_name"] for line in lines] == ["Black", "Red"]
    assert [line["element_ids"][0] for line in lines] == ["302400", "300121"]
