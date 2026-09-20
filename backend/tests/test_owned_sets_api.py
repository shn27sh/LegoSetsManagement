from sqlalchemy import select

from app.db.models import MissingItem, OwnedSet
from tests.factories import (
    TINY_PNG,
    add_catalog_set,
    add_catalog_stub,
    add_missing_item_for_set_line,
    add_owned_set,
    add_set_part_inventory_line,
    add_theme,
    add_part,
    add_color,
    add_element_id_for_set_part_line,
    add_minifig_with_parts,
)


def _seed_collection(db_session):
    theme = add_theme(db_session, external_id=67, name="Town")
    catalog = add_catalog_set(db_session, theme=theme)
    owned_a = add_owned_set(db_session, catalog, investigated=False, label="copy A")
    owned_b = add_owned_set(db_session, catalog, investigated=True, label="copy B")
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session)
    line = add_set_part_inventory_line(db_session, catalog_set=catalog, part=part, color=color)
    add_missing_item_for_set_line(db_session, owned_set=owned_a, line=line)
    add_minifig_with_parts(db_session, catalog_set=catalog)
    db_session.commit()
    return owned_a, owned_b, catalog


def test_list_owned_sets(api_client, db_session) -> None:
    owned_a, owned_b, _ = _seed_collection(db_session)
    response = api_client.get("/api/owned-sets")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id[owned_a.id]["missing_count"] == 1
    assert by_id[owned_b.id]["missing_count"] == 0
    assert by_id[owned_a.id]["catalog_sync_state"] == "ok"
    assert by_id[owned_a.id]["theme_name"] == "Town"


def test_list_filter_investigated(api_client, db_session) -> None:
    _seed_collection(db_session)
    response = api_client.get("/api/owned-sets", params={"investigated": "false"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["investigated"] is False


def test_list_filter_theme_and_sort(api_client, db_session) -> None:
    town = add_theme(db_session, external_id=67, name="Town")
    space = add_theme(db_session, external_id=88, name="Space")
    catalog_b = add_catalog_set(db_session, set_number=2000, theme=space)
    catalog_b.name = "Beta"
    catalog_b.num_parts = 10
    catalog_a = add_catalog_set(db_session, set_number=1000, theme=town)
    catalog_a.name = "Alpha"
    catalog_a.num_parts = 20
    owned_b = add_owned_set(db_session, catalog_b)
    owned_a = add_owned_set(db_session, catalog_a)
    owned_b.age = 12
    owned_a.age = 6
    db_session.commit()

    by_name = api_client.get(
        "/api/owned-sets",
        params={"sort_by": "name", "sort_dir": "asc"},
    )
    assert by_name.status_code == 200
    assert [item["name"] for item in by_name.json()["items"]] == ["Alpha", "Beta"]

    town_only = api_client.get(
        "/api/owned-sets",
        params={"theme": "Town", "sort_by": "set_num", "sort_dir": "desc"},
    )
    assert town_only.status_code == 200
    body = town_only.json()
    assert body["total"] == 1
    assert body["items"][0]["theme_name"] == "Town"
    assert body["items"][0]["set_num"] == 1000


def test_list_filter_multiple_themes_and_missing_only(api_client, db_session) -> None:
    town = add_theme(db_session, external_id=67, name="Town")
    space = add_theme(db_session, external_id=88, name="Space")
    castle = add_theme(db_session, external_id=99, name="Castle")
    catalog_town = add_catalog_set(db_session, set_number=1000, theme=town)
    catalog_space = add_catalog_set(db_session, set_number=2000, theme=space)
    catalog_castle = add_catalog_set(db_session, set_number=3000, theme=castle)
    owned_town = add_owned_set(db_session, catalog_town)
    owned_space = add_owned_set(db_session, catalog_space)
    add_owned_set(db_session, catalog_castle)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog_space,
        part=part,
        color=color,
    )
    add_missing_item_for_set_line(db_session, owned_set=owned_space, line=line)
    db_session.commit()

    multi_theme = api_client.get(
        "/api/owned-sets",
        params=[("theme", "Town"), ("theme", "Space"), ("sort_by", "set_num")],
    )
    assert multi_theme.status_code == 200
    assert [item["id"] for item in multi_theme.json()["items"]] == [
        owned_town.id,
        owned_space.id,
    ]

    missing_only = api_client.get(
        "/api/owned-sets",
        params=[("theme", "Town"), ("theme", "Space"), ("missing_only", "true")],
    )
    assert missing_only.status_code == 200
    body = missing_only.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == owned_space.id


def test_list_theme_options_include_whole_collection(api_client, db_session) -> None:
    town = add_theme(db_session, external_id=67, name="Town")
    space = add_theme(db_session, external_id=88, name="Space")
    add_owned_set(db_session, add_catalog_set(db_session, set_number=1000, theme=town))
    add_owned_set(db_session, add_catalog_set(db_session, set_number=2000, theme=space))
    db_session.commit()

    response = api_client.get("/api/owned-sets/theme-options")

    assert response.status_code == 200
    assert response.json() == {"themes": ["Space", "Town"]}


def test_list_pending_catalog_sync_state(api_client, db_session) -> None:
    stub = add_catalog_stub(db_session)
    add_owned_set(db_session, stub)
    db_session.commit()

    response = api_client.get("/api/owned-sets")
    assert response.json()["items"][0]["catalog_sync_state"] == "pending"


def test_get_owned_set_detail(api_client, db_session) -> None:
    owned_a, _, _ = _seed_collection(db_session)
    response = api_client.get(f"/api/owned-sets/{owned_a.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["catalog"]["set_num"] == 6024
    assert len(body["inventory"]["set_parts"]) == 1
    assert body["inventory"]["set_parts"][0]["missing_quantity"] == 1
    assert body["inventory"]["set_parts"][0]["missing_item_id"] == 1
    assert len(body["inventory"]["minifigs"]) == 1
    assert len(body["inventory"]["minifigs"][0]["parts"]) == 1


def test_get_owned_set_detail_exposes_element_image_urls(
    api_client, db_session
) -> None:
    from app.services.image_blob import set_element_image

    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=4, name="Red")
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="302424")
    set_element_image(
        db_session,
        "302424",
        content=TINY_PNG,
        content_type="image/png",
    )
    _, _, minifig_line = add_minifig_with_parts(db_session, catalog_set=catalog)
    minifig_line.part.image_url = "https://cdn.example/generic-973.png"
    minifig_line.image_url = "https://cdn.example/elements/973-yellow.png"
    db_session.commit()

    response = api_client.get(f"/api/owned-sets/{owned.id}")

    assert response.status_code == 200
    body = response.json()
    set_part = body["inventory"]["set_parts"][0]
    assert set_part["image_url"] == "/api/elements/302424/image"
    assert set_part["part_image_url"] is None
    minifig_part = body["inventory"]["minifigs"][0]["parts"][0]
    assert minifig_part["image_url"] is None
    assert minifig_part["part_image_url"] is None


def test_get_owned_set_detail_part_image_url_is_part_blob_only(
    api_client, db_session
) -> None:
    from app.services.image_blob import set_element_image, set_part_image

    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=4, name="Red")
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="302424")
    set_element_image(
        db_session,
        "302424",
        content=TINY_PNG,
        content_type="image/png",
    )
    set_part_image(
        db_session,
        part.id,
        content=TINY_PNG,
        content_type="image/png",
    )
    db_session.commit()

    body = api_client.get(f"/api/owned-sets/{owned.id}").json()
    set_part = body["inventory"]["set_parts"][0]
    assert set_part["image_url"] == "/api/elements/302424/image"
    assert set_part["part_image_url"] == f"/api/parts/{part.id}/image"


def test_get_owned_set_detail_part_image_user_removed_after_delete(
    api_client, db_session
) -> None:
    from app.services.image_blob import clear_part_image, set_element_image

    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=4, name="Red")
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="302424")
    set_element_image(
        db_session,
        "302424",
        content=TINY_PNG,
        content_type="image/png",
    )
    db_session.commit()

    clear_part_image(db_session, part.id)
    db_session.commit()

    set_part = api_client.get(f"/api/owned-sets/{owned.id}").json()["inventory"][
        "set_parts"
    ][0]
    assert set_part["image_url"] == "/api/elements/302424/image"
    assert set_part["part_image_url"] is None
    assert set_part["part_image_user_removed"] is True


def test_get_owned_set_not_found(api_client) -> None:
    assert api_client.get("/api/owned-sets/9999").status_code == 404


def test_patch_owned_set(api_client, db_session) -> None:
    owned_a, _, _ = _seed_collection(db_session)
    response = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={"investigated": True, "label": "checked"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["investigated"] is True
    assert body["label"] == "checked"


def test_duplicate_owned_set(api_client, db_session) -> None:
    owned_a, _, _ = _seed_collection(db_session)
    response = api_client.post(f"/api/owned-sets/{owned_a.id}/duplicate")
    assert response.status_code == 201
    body = response.json()
    assert body["duplicated_from_owned_set_id"] == owned_a.id
    assert body["investigated"] is False
    assert body["label"] == "Copy #3"
    assert body["display_label"] == "Copy #3"
    assert body["missing_count"] == 0

    source_missing = db_session.scalars(
        select(MissingItem).where(MissingItem.owned_set_id == owned_a.id)
    ).all()
    assert len(source_missing) == 1

    new_id = body["id"]
    new_missing = db_session.scalars(
        select(MissingItem).where(MissingItem.owned_set_id == new_id)
    ).all()
    assert new_missing == []

    assert db_session.scalar(select(OwnedSet).where(OwnedSet.id == new_id)) is not None


def test_duplicate_not_found(api_client) -> None:
    assert api_client.post("/api/owned-sets/9999/duplicate").status_code == 404
