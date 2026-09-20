from app.db.models import MissingItem, OwnedSetInventoryLine, Part
from tests.factories import (
    TINY_PNG,
    add_catalog_set,
    add_color,
    add_missing_item_for_set_line,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def _seed_line(db_session, *, quantity: int = 4):
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=quantity
    )
    owned = add_owned_set(db_session, catalog)
    db_session.commit()
    return owned, line, part


def test_patch_missing_creates(api_client, db_session) -> None:
    owned, line, _part = _seed_line(db_session)
    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["owned_set_id"] == owned.id
    assert body["missing_item_id"] > 0

    missing = db_session.get(MissingItem, body["missing_item_id"])
    assert missing is not None
    instance = db_session.get(OwnedSetInventoryLine, missing.owned_set_inventory_line_id)
    assert instance is not None
    assert instance.quantity_missing == 2


def test_patch_missing_quantity_exceeds_inventory(api_client, db_session) -> None:
    owned, line, _part = _seed_line(db_session, quantity=3)
    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 5},
    )
    assert response.status_code == 400


def test_patch_missing_clear_removes_row(api_client, db_session) -> None:
    owned, line, _part = _seed_line(db_session)
    missing = add_missing_item_for_set_line(
        db_session, owned_set=owned, line=line
    )
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 0},
    )
    assert response.status_code == 200
    assert db_session.get(MissingItem, missing.id) is None


def test_patch_missing_requires_exactly_one_line_ref(api_client, db_session) -> None:
    owned, line, _part = _seed_line(db_session)
    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={
            "set_part_inventory_line_id": line.id,
            "minifig_part_inventory_line_id": 99,
            "quantity_missing": 1,
        },
    )
    assert response.status_code == 422


def test_put_and_get_missing_image(api_client, db_session) -> None:
    owned, line, part = _seed_line(db_session)
    create = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 1},
    )
    missing_id = create.json()["missing_item_id"]

    put = api_client.put(
        f"/api/owned-sets/{owned.id}/missing/{missing_id}/image",
        files={"file": ("part.png", TINY_PNG, "image/png")},
    )
    assert put.status_code == 200
    assert put.json()["part_image_url"] == f"/api/parts/{part.id}/image"

    get = api_client.get(f"/api/media/missing/{missing_id}")
    assert get.status_code == 200
    assert get.headers["content-type"].startswith("image/png")

    stored = db_session.get(Part, part.id)
    assert stored is not None
    assert stored.image_blob is not None


def test_delete_image_keeps_missing_row(api_client, db_session) -> None:
    owned, line, part = _seed_line(db_session)
    create = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 2},
    )
    missing_id = create.json()["missing_item_id"]
    api_client.put(
        f"/api/owned-sets/{owned.id}/missing/{missing_id}/image",
        files={"file": ("part.png", TINY_PNG, "image/png")},
    )

    delete = api_client.delete(
        f"/api/owned-sets/{owned.id}/missing/{missing_id}/image"
    )
    assert delete.status_code == 200
    assert delete.json()["part_image_url"] is None

    missing = db_session.get(MissingItem, missing_id)
    assert missing is not None
    instance = db_session.get(OwnedSetInventoryLine, missing.owned_set_inventory_line_id)
    assert instance is not None
    assert instance.quantity_missing == 2
    assert db_session.get(Part, part.id).image_blob is None


def test_put_image_wrong_owned_set_returns_404(api_client, db_session) -> None:
    owned_a, line_a, _part = _seed_line(db_session)
    catalog_b = add_catalog_set(db_session, set_number=9999)
    owned_b = add_owned_set(db_session, catalog_b)
    db_session.commit()

    create = api_client.patch(
        f"/api/owned-sets/{owned_a.id}/missing",
        json={"set_part_inventory_line_id": line_a.id, "quantity_missing": 1},
    )
    missing_id = create.json()["missing_item_id"]

    response = api_client.put(
        f"/api/owned-sets/{owned_b.id}/missing/{missing_id}/image",
        files={"file": ("part.png", TINY_PNG, "image/png")},
    )
    assert response.status_code == 404


def test_get_media_not_found(api_client) -> None:
    assert api_client.get("/api/media/missing/99999").status_code == 404
