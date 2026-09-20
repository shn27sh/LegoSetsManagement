"""PATCH /api/parts/{part_id}/aliases (Phase 11B)."""

from sqlalchemy import select

from app.db.models import PartAlias
from tests.factories import (
    add_catalog_set,
    add_color,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_patch_part_aliases_returns_symmetric_lists(api_client, db_session) -> None:
    part_x = add_part(db_session, part_num="3024")
    part_b = add_part(db_session, part_num="3024b")
    db_session.commit()

    response = api_client.patch(
        f"/api/parts/{part_x.id}/aliases",
        json={"aliases": ["3024b", "3024pr"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["part_id"] == part_x.id
    assert body["part_num"] == "3024"
    assert body["aliases"] == ["3024b", "3024pr"]

    b_rows = db_session.scalars(
        select(PartAlias.alias).where(
            PartAlias.part_id == part_b.id,
            PartAlias.source == "user",
        )
    ).all()
    assert "3024" in b_rows
    assert "3024pr" in b_rows


def test_patch_aliases_visible_on_owned_set_detail(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    owned = add_owned_set(db_session, catalog, with_inventory=True)
    db_session.commit()

    api_client.patch(
        f"/api/parts/{part.id}/aliases",
        json={"aliases": ["3024b"]},
    )

    detail = api_client.get(f"/api/owned-sets/{owned.id}").json()
    row = detail["inventory"]["set_parts"][0]
    assert "3024b" in row["aliases"]


def test_search_finds_part_by_user_alias_after_patch(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session, set_number=1000)
    add_owned_set(db_session, catalog)
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session)
    add_set_part_inventory_line(
        db_session, catalog_set=catalog, part=part, color=color, quantity=1
    )
    db_session.commit()

    api_client.patch(
        f"/api/parts/{part.id}/aliases",
        json={"aliases": ["search-alias-99"]},
    )

    response = api_client.get(
        "/api/search",
        params={"q": "search-alias", "type": "part"},
    )
    assert response.status_code == 200
    assert len(response.json()["parts"]) == 1
    assert response.json()["parts"][0]["lines"][0]["display_part_num"] == "3024"


def test_patch_part_aliases_not_found(api_client) -> None:
    response = api_client.patch(
        "/api/parts/99999/aliases",
        json={"aliases": ["x"]},
    )
    assert response.status_code == 404


def test_patch_part_aliases_rejects_empty_string(api_client, db_session) -> None:
    part = add_part(db_session, part_num="3024")
    db_session.commit()

    response = api_client.patch(
        f"/api/parts/{part.id}/aliases",
        json={"aliases": ["  ", "ok"]},
    )
    assert response.status_code == 200
    assert response.json()["aliases"] == ["ok"]
