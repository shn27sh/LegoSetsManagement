"""Phase 11A: set-parts CRUD and aliases on set copy detail."""

from sqlalchemy import select

from app.db.models import OwnedSetInventoryLine, SetPartInventoryLine
from tests.factories import (
    add_catalog_set,
    add_color,
    add_element_id_for_set_part_line,
    add_owned_set,
    add_part,
    add_part_alias,
    add_set_part_inventory_line,
)


def test_post_set_part_returns_part_and_catalog_ids(api_client, db_session) -> None:
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
    assert body["part_id"] > 0
    assert body["catalog_line_id"] > 0
    assert body["instance_line_id"] > 0


def test_detail_includes_part_aliases(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    add_part_alias(db_session, part, "3024b")
    add_part_alias(db_session, part, "3024")
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    add_element_id_for_set_part_line(db_session, line=line, element_id="302400")
    add_element_id_for_set_part_line(db_session, line=line, element_id="6252045")
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    row = detail["inventory"]["set_parts"][0]
    assert row["part_num"] == "3024"
    assert row["aliases"] == ["3024b"]
    assert row["element_ids"] == ["302400", "6252045"]


def test_patch_set_part_updates_name_and_quantity(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    part.name = "Old"
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    instance_line_id = api_client.get(f"/api/owned-sets/{owned.id}").json()["inventory"][
        "set_parts"
    ][0]["instance_line_id"]

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/set-parts/{instance_line_id}",
        json={"part_name": "Plate 1 x 1", "quantity": 4},
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 4

    db_session.refresh(part)
    assert part.name == "Plate 1 x 1"

    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    assert detail["inventory"]["set_parts"][0]["quantity"] == 4
    assert detail["inventory"]["set_parts"][0]["part_name"] == "Plate 1 x 1"


def test_patch_set_part_changes_color_repoints_catalog_line(
    api_client, db_session
) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    black = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=black, quantity=1
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    instance_line_id = api_client.get(f"/api/owned-sets/{owned.id}").json()["inventory"][
        "set_parts"
    ][0]["instance_line_id"]
    old_catalog_line_id = line.id

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/set-parts/{instance_line_id}",
        json={"color_id": 1, "color_name": "Blue", "quantity": 2},
    )
    assert response.status_code == 200
    new_catalog_line_id = response.json()["catalog_line_id"]
    assert new_catalog_line_id != old_catalog_line_id

    assert db_session.get(SetPartInventoryLine, old_catalog_line_id) is None
    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    assert detail["inventory"]["set_parts"][0]["color_name"] == "Blue"
    assert detail["inventory"]["set_parts"][0]["quantity"] == 2


def test_delete_set_part_removes_instance_and_orphan_catalog_line(
    api_client, db_session
) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    instance_line_id = api_client.get(f"/api/owned-sets/{owned.id}").json()["inventory"][
        "set_parts"
    ][0]["instance_line_id"]
    catalog_line_id = line.id

    response = api_client.delete(
        f"/api/owned-sets/{owned.id}/set-parts/{instance_line_id}"
    )
    assert response.status_code == 204

    assert db_session.get(SetPartInventoryLine, catalog_line_id) is None
    assert (
        db_session.scalar(
            select(OwnedSetInventoryLine).where(
                OwnedSetInventoryLine.id == instance_line_id
            )
        )
        is None
    )
    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    assert detail["inventory"]["set_parts"] == []


def test_delete_set_part_keeps_catalog_line_when_other_instance_uses_it(
    api_client, db_session
) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    owned_a = add_owned_set(db_session, catalog, with_inventory=True)
    owned_b = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    detail_a = api_client.get(f"/api/owned-sets/{owned_a.id}").json()
    instance_line_id = detail_a["inventory"]["set_parts"][0]["instance_line_id"]

    response = api_client.delete(
        f"/api/owned-sets/{owned_a.id}/set-parts/{instance_line_id}"
    )
    assert response.status_code == 204
    assert db_session.get(SetPartInventoryLine, line.id) is not None


def test_patch_set_part_not_found(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/set-parts/99999",
        json={"quantity": 1},
    )
    assert response.status_code == 404


def test_patch_set_part_rejects_missing_above_quantity(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=4
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    from tests.factories import add_missing_item_for_set_line

    add_missing_item_for_set_line(
        db_session, owned_set=owned, line=line, quantity_missing=3
    )
    db_session.commit()

    instance_line_id = api_client.get(f"/api/owned-sets/{owned.id}").json()["inventory"][
        "set_parts"
    ][0]["instance_line_id"]

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}/set-parts/{instance_line_id}",
        json={"quantity": 2},
    )
    assert response.status_code == 400
