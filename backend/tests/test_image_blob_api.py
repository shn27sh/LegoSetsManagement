"""SQLite BLOB image storage for parts and catalog sets."""

from sqlalchemy import select

from app.db.models import CatalogMinifig, CatalogSet, Part
from tests.factories import (
    TINY_PNG,
    add_catalog_set,
    add_color,
    add_minifig_with_parts,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_part_image_round_trip(api_client, db_session) -> None:
    part = add_part(db_session, part_num="3024")
    db_session.commit()

    put = api_client.put(
        f"/api/parts/{part.id}/image",
        files={"file": ("p.png", TINY_PNG, "image/png")},
    )
    assert put.status_code == 200
    assert put.json()["image_url"] == f"/api/parts/{part.id}/image"

    get = api_client.get(f"/api/parts/{part.id}/image")
    assert get.status_code == 200
    assert get.content == TINY_PNG

    row = db_session.get(Part, part.id)
    assert row is not None
    assert row.image_byte_size == len(TINY_PNG)
    assert row.part_image_user_removed is False


def test_delete_part_image_sets_user_removed_flag(api_client, db_session) -> None:
    part = add_part(db_session, part_num="3024")
    db_session.commit()

    api_client.put(
        f"/api/parts/{part.id}/image",
        files={"file": ("p.png", TINY_PNG, "image/png")},
    )
    delete = api_client.delete(f"/api/parts/{part.id}/image")
    assert delete.status_code == 200
    assert delete.json()["image_url"] is None

    row = db_session.get(Part, part.id)
    assert row is not None
    assert row.image_blob is None
    assert row.part_image_user_removed is True


def test_part_image_visible_across_two_sets(api_client, db_session) -> None:
    part = add_part(db_session, part_num="shared")
    color = add_color(db_session)
    catalog_a = add_catalog_set(db_session)
    catalog_b = add_catalog_set(db_session, set_number=9999)
    add_set_part_inventory_line(
        db_session, catalog_set=catalog_a, part=part, color=color
    )
    add_set_part_inventory_line(
        db_session, catalog_set=catalog_b, part=part, color=color
    )
    owned_a = add_owned_set(db_session, catalog_a)
    owned_b = add_owned_set(db_session, catalog_b)
    db_session.commit()

    api_client.put(
        f"/api/parts/{part.id}/image",
        files={"file": ("p.png", TINY_PNG, "image/png")},
    )

    detail_a = api_client.get(f"/api/owned-sets/{owned_a.id}").json()
    detail_b = api_client.get(f"/api/owned-sets/{owned_b.id}").json()
    url = f"/api/parts/{part.id}/image"
    assert detail_a["inventory"]["set_parts"][0]["part_image_url"] == url
    assert detail_b["inventory"]["set_parts"][0]["part_image_url"] == url


def test_catalog_set_image_round_trip(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    db_session.commit()

    put = api_client.put(
        f"/api/catalog-sets/{catalog.id}/image",
        files={"file": ("box.png", TINY_PNG, "image/png")},
    )
    assert put.status_code == 200

    get = api_client.get(f"/api/catalog-sets/{catalog.id}/image")
    assert get.status_code == 200
    assert get.content == TINY_PNG

    row = db_session.get(CatalogSet, catalog.id)
    assert row is not None
    assert row.image_content_type == "image/png"


def test_catalog_minifig_image_round_trip(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    minifig, _, _ = add_minifig_with_parts(db_session, catalog_set=catalog)
    db_session.commit()

    put = api_client.put(
        f"/api/catalog-minifigs/{minifig.id}/image",
        files={"file": ("fig.png", TINY_PNG, "image/png")},
    )
    assert put.status_code == 200
    assert put.json()["image_url"] == f"/api/catalog-minifigs/{minifig.id}/image"

    get = api_client.get(f"/api/catalog-minifigs/{minifig.id}/image")
    assert get.status_code == 200
    assert get.content == TINY_PNG

    row = db_session.get(CatalogMinifig, minifig.id)
    assert row is not None
    assert row.image_content_type == "image/png"


def test_missing_image_stored_on_part(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session)
    color = add_color(db_session)
    line = add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color
    )
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    create = api_client.patch(
        f"/api/owned-sets/{owned.id}/missing",
        json={"set_part_inventory_line_id": line.id, "quantity_missing": 1},
    )
    missing_id = create.json()["missing_item_id"]

    put = api_client.put(
        f"/api/owned-sets/{owned.id}/missing/{missing_id}/image",
        files={"file": ("p.png", TINY_PNG, "image/png")},
    )
    assert put.status_code == 200
    assert put.json()["part_image_url"] == f"/api/parts/{part.id}/image"

    get = api_client.get(f"/api/media/missing/{missing_id}")
    assert get.status_code == 200
    assert get.content == TINY_PNG

    stored = db_session.scalar(select(Part).where(Part.id == part.id))
    assert stored is not None
    assert stored.image_blob is not None
