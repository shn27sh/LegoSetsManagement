from tests.factories import (
    add_catalog_set,
    add_owned_set,
    add_part,
    add_part_alias,
    add_set_part_inventory_line,
    add_color,
    add_element_id_for_set_part_line,
)


def test_search_empty_query_returns_400(api_client) -> None:
    response = api_client.get("/api/search", params={"q": "  "})
    assert response.status_code == 400


def test_search_sets_by_prefix(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog, label="A")
    db_session.commit()

    response = api_client.get("/api/search", params={"q": "6024", "type": "set"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["sets"]) == 1
    assert body["sets"][0]["owned_set_id"] == owned.id
    assert body["parts"] == []


def test_search_multiple_instances_same_set_num(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog, label="A")
    add_owned_set(db_session, catalog, label="B")
    db_session.commit()

    response = api_client.get("/api/search", params={"q": "6024", "type": "set"})
    assert len(response.json()["sets"]) == 2


def test_search_parts_by_part_num_and_alias(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session, set_number=1000)
    add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    add_part_alias(db_session, part, "alias-3024")
    color = add_color(db_session)
    line = add_set_part_inventory_line(db_session, catalog_set=catalog, part=part, color=color)
    add_element_id_for_set_part_line(db_session, line=line, element_id="302400")
    db_session.commit()

    by_num = api_client.get("/api/search", params={"q": "3024", "type": "part"})
    assert len(by_num.json()["parts"]) == 1
    p0 = by_num.json()["parts"][0]
    assert p0["lines"][0]["display_part_num"] == "3024"
    assert len(p0["lines"][0]["sets"]) == 1
    assert p0["lines"][0]["sets"][0]["colors"] == [
        {"color_id": 0, "color_name": "Black", "quantity": 4}
    ]

    by_alias = api_client.get("/api/search", params={"q": "alias", "type": "part"})
    assert len(by_alias.json()["parts"]) == 1

    by_element = api_client.get("/api/search", params={"q": "3024", "type": "element"})
    assert by_element.status_code == 200
    assert by_element.json()["elements"][0]["element_ids"] == ["302400"]
    assert by_element.json()["elements"][0]["part_num"] == "3024"


def test_search_parts_groups_aliases_by_original_part_number(api_client, db_session) -> None:
    cat_main = add_catalog_set(db_session, set_number=1111)
    cat_alias_a = add_catalog_set(db_session, set_number=2222)
    cat_alias_a_2 = add_catalog_set(db_session, set_number=77777)
    cat_alias_b = add_catalog_set(db_session, set_number=3333)
    add_owned_set(db_session, cat_main)
    add_owned_set(db_session, cat_alias_a)
    add_owned_set(db_session, cat_alias_a_2)
    add_owned_set(db_session, cat_alias_b)
    part = add_part(db_session, part_num="123456")
    alias_a = add_part(db_session, part_num="9876a")
    alias_b = add_part(db_session, part_num="65432")
    add_part_alias(db_session, part, "9876a")
    add_part_alias(db_session, part, "65432")
    color = add_color(db_session)
    add_set_part_inventory_line(
        db_session, catalog_set=cat_main, part=part, color=color, quantity=3
    )
    add_set_part_inventory_line(
        db_session, catalog_set=cat_alias_a, part=alias_a, color=color, quantity=4
    )
    add_set_part_inventory_line(
        db_session, catalog_set=cat_alias_a_2, part=alias_a, color=color, quantity=1
    )
    add_set_part_inventory_line(
        db_session, catalog_set=cat_alias_b, part=alias_b, color=color, quantity=1
    )
    db_session.commit()

    response = api_client.get("/api/search", params={"q": "123456", "type": "part"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["parts"]) == 1
    hit = body["parts"][0]
    assert hit["part_num"] == "123456"
    by_line = {
        line["display_part_num"]: {
            (s["set_num"], s["quantity"]) for s in line["sets"]
        }
        for line in hit["lines"]
    }
    assert by_line == {
        "123456": {(1111, 3)},
        "65432": {(3333, 1)},
        "9876a": {(2222, 4), (77777, 1)},
    }


def test_search_type_all_returns_both_buckets(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="6024plate")
    color = add_color(db_session, external_id=2, name="Blue")
    add_set_part_inventory_line(db_session, catalog_set=catalog, part=part, color=color)
    db_session.commit()

    response = api_client.get("/api/search", params={"q": "602", "type": "all"})
    body = response.json()
    assert len(body["sets"]) == 1
    assert len(body["parts"]) == 1
