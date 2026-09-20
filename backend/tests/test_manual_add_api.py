"""Manual add set (POST /owned-sets) API tests."""

from unittest.mock import MagicMock, patch

from tests.factories import add_catalog_set, add_color, add_owned_set, add_part, add_set_part_inventory_line


def test_add_preview_new_set_num(api_client) -> None:
    response = api_client.get("/api/owned-sets/add-preview", params={"set_num": "9999-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["catalog_exists"] is False
    assert body["set_num"] == 9999
    assert body["suggested_label"] == "Copy #1"


def test_add_preview_existing_set_num(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
        quantity=3,
    )
    add_owned_set(db_session, catalog, label="copy A")
    db_session.commit()

    response = api_client.get("/api/owned-sets/add-preview", params={"set_num": "6024-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["catalog_exists"] is True
    assert body["set_name"] == "Police Car"
    assert body["existing_copy_count"] == 1
    assert body["suggested_label"] == "Copy #2"
    assert len(body["set_parts"]) == 1
    assert body["set_parts"][0]["part_num"] == "3024"


def test_create_new_set_stub(api_client, db_session) -> None:
    response = api_client.post("/api/owned-sets", json={"set_num": 8888})
    assert response.status_code == 201
    body = response.json()
    assert body["catalog_created"] is True
    assert body["set_num"] == 8888
    assert body["investigated"] is False
    assert body["display_label"] == "Copy #1"

    detail = api_client.get(f"/api/owned-sets/{body['id']}")
    assert detail.status_code == 200


def test_create_new_set_with_catalog_and_parts(api_client, db_session) -> None:
    response = api_client.post(
        "/api/owned-sets",
        json={
            "set_num": "7777-1",
            "catalog": {
                "name": "Custom Set",
                "theme_name": "Town",
                "year": 1985,
                "num_parts": 2,
            },
            "parts": [
                {
                    "part_num": "3024",
                    "part_name": "Plate 1 x 1",
                    "color_id": 0,
                    "color_name": "Black",
                    "quantity": 2,
                }
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Custom Set"
    assert body["theme_name"] == "Town"

    detail = api_client.get(f"/api/owned-sets/{body['id']}").json()
    assert len(detail["inventory"]["set_parts"]) == 1
    assert detail["inventory"]["set_parts"][0]["part_num"] == "3024"
    assert detail["inventory"]["set_parts"][0]["quantity"] == 2


def test_create_additional_copy(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
        quantity=4,
    )
    existing = add_owned_set(db_session, catalog, investigated=True)
    db_session.commit()

    detail_existing = api_client.get(f"/api/owned-sets/{existing.id}").json()
    instance_line_id = detail_existing["inventory"]["set_parts"][0]["instance_line_id"]
    api_client.patch(
        f"/api/owned-sets/{existing.id}/inventory-lines/{instance_line_id}",
        json={"quantity_missing": 2},
    )

    response = api_client.post(
        "/api/owned-sets",
        json={"set_num": "6024-1", "label": "Copy #2"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["catalog_created"] is False
    assert body["label"] == "Copy #2"
    assert body["investigated"] is False
    assert body["missing_count"] == 0

    detail = api_client.get(f"/api/owned-sets/{body['id']}").json()
    assert len(detail["inventory"]["set_parts"]) == 1
    part_row = detail["inventory"]["set_parts"][0]
    assert part_row["quantity"] == line.quantity
    assert part_row["missing_quantity"] == 0
    assert part_row["missing_item_id"] is None


def test_create_copy_rejects_catalog_body(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.post(
        "/api/owned-sets",
        json={"set_num": "6024-1", "catalog": {"name": "Nope"}},
    )
    assert response.status_code == 400


def test_rebrickable_draft_409_when_catalog_exists(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.get(
        "/api/owned-sets/add-rebrickable-draft",
        params={"set_num": "6024-1"},
    )
    assert response.status_code == 409


def test_rebrickable_draft_requires_api_key(api_client, monkeypatch) -> None:
    monkeypatch.delenv("REBRICKABLE_API_KEY", raising=False)
    response = api_client.get(
        "/api/owned-sets/add-rebrickable-draft",
        params={"set_num": "8888-1"},
    )
    assert response.status_code == 400
    assert "REBRICKABLE_API_KEY" in response.json()["detail"]


def test_rebrickable_draft_ok(api_client, monkeypatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")

    from app.schemas.manual_add import (
        ManualAddCatalogInput,
        ManualAddPartInput,
        OwnedSetRebrickableDraftResponse,
    )

    fake_draft = OwnedSetRebrickableDraftResponse(
        set_num=8888,
        catalog=ManualAddCatalogInput(
            name="From API",
            theme_name=None,
            year=2000,
            num_parts=1,
        ),
        age=None,
        parts=[
            ManualAddPartInput(
                part_num="3001",
                part_name=None,
                color_id=15,
                color_name="Red",
                quantity=3,
            )
        ],
    )

    dummy_cm = MagicMock()
    dummy_cm.__enter__.return_value = MagicMock()

    with (
        patch("app.api.routes.owned_sets.RebrickableClient", return_value=dummy_cm),
        patch(
            "app.api.routes.owned_sets.fetch_manual_add_rebrickable_draft",
            return_value=fake_draft,
        ),
    ):
        response = api_client.get(
            "/api/owned-sets/add-rebrickable-draft",
            params={"set_num": "8888-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["set_num"] == 8888
    assert body["catalog"]["name"] == "From API"
    assert body["catalog"]["year"] == 2000
    assert len(body["parts"]) == 1
    assert body["parts"][0]["part_num"] == "3001"
    assert body["parts"][0]["quantity"] == 3
    assert body["parts"][0]["color_id"] == 15

