"""Per-instance inventory quantity and missing count."""

from tests.factories import (
    add_catalog_set,
    add_color,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def _seed_two_instances(db_session):
    catalog = add_catalog_set(db_session)
    part = add_part(db_session)
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=4
    )
    copy_a = add_owned_set(db_session, catalog, label="Copy A")
    copy_b = add_owned_set(db_session, catalog, label="Copy B")
    db_session.commit()
    return copy_a, copy_b, line


def test_patch_instance_quantity_isolated_between_copies(api_client, db_session) -> None:
    copy_a, copy_b, line = _seed_two_instances(db_session)

    detail_a = api_client.get(f"/api/owned-sets/{copy_a.id}").json()
    instance_line_id = detail_a["inventory"]["set_parts"][0]["instance_line_id"]

    patch = api_client.patch(
        f"/api/owned-sets/{copy_a.id}/inventory-lines/{instance_line_id}",
        json={"quantity": 2, "quantity_missing": 1},
    )
    assert patch.status_code == 200
    assert patch.json()["quantity"] == 2
    assert patch.json()["quantity_missing"] == 1

    detail_b = api_client.get(f"/api/owned-sets/{copy_b.id}").json()
    assert detail_b["inventory"]["set_parts"][0]["quantity"] == 4
    assert detail_b["inventory"]["set_parts"][0]["missing_quantity"] == 0


def test_patch_instance_quantity_missing_validation(api_client, db_session) -> None:
    copy_a, _, _ = _seed_two_instances(db_session)
    detail = api_client.get(f"/api/owned-sets/{copy_a.id}").json()
    instance_line_id = detail["inventory"]["set_parts"][0]["instance_line_id"]

    bad = api_client.patch(
        f"/api/owned-sets/{copy_a.id}/inventory-lines/{instance_line_id}",
        json={"quantity_missing": 10},
    )
    assert bad.status_code == 400


def test_duplicate_creates_fresh_instance_inventory(api_client, db_session) -> None:
    copy_a, _, line = _seed_two_instances(db_session)
    detail_a = api_client.get(f"/api/owned-sets/{copy_a.id}").json()
    instance_line_id = detail_a["inventory"]["set_parts"][0]["instance_line_id"]
    api_client.patch(
        f"/api/owned-sets/{copy_a.id}/inventory-lines/{instance_line_id}",
        json={"quantity": 1, "quantity_missing": 1},
    )

    dup = api_client.post(f"/api/owned-sets/{copy_a.id}/duplicate", json={})
    assert dup.status_code == 201
    new_id = dup.json()["id"]

    detail_new = api_client.get(f"/api/owned-sets/{new_id}").json()
    part = detail_new["inventory"]["set_parts"][0]
    assert part["quantity"] == line.quantity
    assert part["missing_quantity"] == 0
    assert part["missing_item_id"] is None
