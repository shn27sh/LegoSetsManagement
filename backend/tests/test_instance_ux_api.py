from sqlalchemy import select

from app.db.models import CatalogSet, MissingItem, OwnedSet, Theme
from tests.factories import add_catalog_set, add_owned_set, add_theme


def test_duplicate_preview_and_create_with_label(api_client, db_session) -> None:
    theme = add_theme(db_session)
    catalog = add_catalog_set(db_session, theme=theme)
    owned = add_owned_set(db_session, catalog, label="copy A")
    db_session.commit()

    preview = api_client.get(f"/api/owned-sets/{owned.id}/duplicate-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["set_num"] == 6024
    assert body["existing_copy_count"] == 1
    assert body["suggested_label"] == "Copy #2"

    create = api_client.post(
        f"/api/owned-sets/{owned.id}/duplicate",
        json={"label": "Copy #2"},
    )
    assert create.status_code == 201
    created = create.json()
    assert created["label"] == "Copy #2"
    assert created["display_label"] == "Copy #2"
    assert created["copy_index"] == 2
    assert created["missing_count"] == 0


def test_duplicate_copies_age_from_source(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog, label="copy A")
    owned.age = 8
    db_session.commit()

    response = api_client.post(f"/api/owned-sets/{owned.id}/duplicate", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["age"] == 8

    db_session.expire_all()
    new_owned = db_session.get(OwnedSet, body["id"])
    assert new_owned is not None
    assert new_owned.age == 8


def test_delete_owned_set_removes_last_catalog(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session, set_number=9999)
    owned = add_owned_set(db_session, catalog)
    catalog_id = catalog.id
    db_session.commit()

    response = api_client.delete(f"/api/owned-sets/{owned.id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert db_session.get(OwnedSet, owned.id) is None
    assert db_session.get(CatalogSet, catalog_id) is None


def test_patch_catalog_theme_when_no_theme_linked(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    assert catalog.theme_id is None
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}",
        json={"catalog_theme_name": "Classic Town"},
    )
    assert response.status_code == 200
    assert response.json()["theme_name"] == "Classic Town"

    db_session.expire_all()
    refreshed = db_session.get(CatalogSet, catalog.id)
    assert refreshed is not None
    assert refreshed.theme_id is not None
    assert refreshed.theme is not None
    assert refreshed.theme.name == "Classic Town"
    assert refreshed.theme.source == "user"


def test_patch_catalog_theme_updates_existing_theme(api_client, db_session) -> None:
    theme = add_theme(db_session, name="Town")
    catalog = add_catalog_set(db_session, theme=theme)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned.id}",
        json={"catalog_theme_name": "Classic Town"},
    )
    assert response.status_code == 200
    assert response.json()["theme_name"] == "Classic Town"

    db_session.expire_all()
    assert db_session.get(Theme, theme.id).name == "Classic Town"


def test_patch_catalog_theme_this_set_only_relinks_without_renaming_shared_theme(
    api_client, db_session
) -> None:
    theme = add_theme(db_session, name="Town")
    catalog_a = add_catalog_set(db_session, set_number=6024, theme=theme)
    catalog_b = add_catalog_set(db_session, set_number=8888, theme=theme)
    owned_a = add_owned_set(db_session, catalog_a)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={
            "catalog_theme_name": "Classic Town",
            "catalog_theme_scope": "this_set",
        },
    )
    assert response.status_code == 200
    assert response.json()["theme_name"] == "Classic Town"

    db_session.expire_all()
    assert db_session.get(CatalogSet, catalog_a.id).theme.name == "Classic Town"
    assert db_session.get(CatalogSet, catalog_b.id).theme.name == "Town"
    assert db_session.get(Theme, theme.id).name == "Town"


def test_patch_catalog_theme_all_renames_shared_theme(api_client, db_session) -> None:
    theme = add_theme(db_session, name="Town")
    catalog_a = add_catalog_set(db_session, set_number=6024, theme=theme)
    catalog_b = add_catalog_set(db_session, set_number=8888, theme=theme)
    owned_a = add_owned_set(db_session, catalog_a)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={
            "catalog_theme_name": "Classic Town",
            "catalog_theme_scope": "all",
        },
    )
    assert response.status_code == 200
    assert response.json()["theme_name"] == "Classic Town"

    db_session.expire_all()
    assert db_session.get(CatalogSet, catalog_a.id).theme_id == theme.id
    assert db_session.get(CatalogSet, catalog_b.id).theme_id == theme.id
    assert db_session.get(Theme, theme.id).name == "Classic Town"


def test_rename_4_juniors_to_4_juniors_two_all_then_get_and_list(
    api_client, db_session
) -> None:
    theme = add_theme(db_session, name="4 Juniors", external_id=100)
    catalog_a = add_catalog_set(db_session, set_number=6024, theme=theme)
    add_catalog_set(db_session, set_number=8888, theme=theme)
    owned_a = add_owned_set(db_session, catalog_a)
    db_session.commit()

    patch = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={
            "catalog_theme_name": "4 Juniors Two",
            "catalog_theme_scope": "all",
        },
    )
    assert patch.status_code == 200
    assert patch.json()["theme_name"] == "4 Juniors Two"

    detail = api_client.get(f"/api/owned-sets/{owned_a.id}")
    assert detail.status_code == 200
    assert detail.json()["catalog"]["theme_name"] == "4 Juniors Two"

    listed = api_client.get("/api/owned-sets", params={"theme": ["4 Juniors Two"]})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == owned_a.id


def test_shorten_theme_name_to_existing_canonical_name(api_client, db_session) -> None:
    add_theme(db_session, name="4 Juniors", external_id=100)
    renamed = add_theme(db_session, name="4 Juniors New", external_id=101)
    catalog = add_catalog_set(db_session, set_number=4666, theme=renamed)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    patch = api_client.patch(
        f"/api/owned-sets/{owned.id}",
        json={"catalog_theme_name": "4 Juniors"},
    )
    assert patch.status_code == 200
    assert patch.json()["theme_name"] == "4 Juniors"

    detail = api_client.get(f"/api/owned-sets/{owned.id}")
    assert detail.json()["catalog"]["theme_name"] == "4 Juniors"

    db_session.expire_all()
    refreshed = db_session.get(CatalogSet, catalog.id)
    canonical = db_session.scalar(select(Theme).where(Theme.name == "4 Juniors"))
    assert refreshed is not None
    assert canonical is not None
    assert refreshed.theme_id == canonical.id


def test_get_owned_set_detail_includes_theme_shared_count(api_client, db_session) -> None:
    theme = add_theme(db_session, name="Town")
    catalog_a = add_catalog_set(db_session, set_number=6024, theme=theme)
    add_catalog_set(db_session, set_number=8888, theme=theme)
    owned_a = add_owned_set(db_session, catalog_a)
    db_session.commit()

    response = api_client.get(f"/api/owned-sets/{owned_a.id}")
    assert response.status_code == 200
    assert response.json()["catalog"]["theme_shared_catalog_set_count"] == 2


def test_theme_shared_count_matches_by_name_not_only_theme_id(
    api_client, db_session
) -> None:
    theme_a = add_theme(db_session, name="Town", external_id=1)
    theme_b = add_theme(db_session, name="town", external_id=2)
    catalog_a = add_catalog_set(db_session, set_number=6024, theme=theme_a)
    add_catalog_set(db_session, set_number=8888, theme=theme_b)
    owned_a = add_owned_set(db_session, catalog_a)
    db_session.commit()

    response = api_client.get(f"/api/owned-sets/{owned_a.id}")
    assert response.status_code == 200
    assert response.json()["catalog"]["theme_shared_catalog_set_count"] == 2


def test_patch_age_updates_all_instances(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned_a = add_owned_set(db_session, catalog, label="a")
    owned_b = add_owned_set(db_session, catalog, label="b")
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={"age": 6},
    )
    assert response.status_code == 200
    assert response.json()["age"] == 6

    db_session.expire_all()
    assert db_session.get(OwnedSet, owned_a.id).age == 6
    assert db_session.get(OwnedSet, owned_b.id).age == 6


def test_patch_set_num_relinks_single_instance(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    owned_a = add_owned_set(db_session, catalog)
    owned_b = add_owned_set(db_session, catalog)
    db_session.commit()

    response = api_client.patch(
        f"/api/owned-sets/{owned_a.id}",
        json={"set_num": "8888-1"},
    )
    assert response.status_code == 200
    assert response.json()["set_num"] == 8888

    db_session.expire_all()
    assert db_session.get(OwnedSet, owned_b.id).catalog_set_id == catalog.id
    new_catalog = db_session.scalar(
        select(CatalogSet).where(CatalogSet.set_number == 8888)
    )
    assert new_catalog is not None
    assert db_session.get(OwnedSet, owned_a.id).catalog_set_id == new_catalog.id
