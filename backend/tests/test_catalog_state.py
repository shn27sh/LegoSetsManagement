from tests.factories import TINY_PNG, add_catalog_set, add_owned_set, add_part


def test_resolve_part_image_url_returns_local_path_when_blob_exists(
    db_session,
) -> None:
    from app.services.catalog_state import resolve_part_image_url
    from app.services.image_blob import set_part_image

    part = add_part(db_session, part_num="3024")
    part.image_url = "https://cdn.example/remote-only.png"
    set_part_image(db_session, part.id, content=TINY_PNG, content_type="image/png")
    db_session.commit()

    assert resolve_part_image_url(part) == f"/api/parts/{part.id}/image"


def test_resolve_part_image_url_ignores_remote_url_without_blob(db_session) -> None:
    from app.services.catalog_state import resolve_part_image_url

    part = add_part(db_session, part_num="3024")
    part.image_url = "https://cdn.example/remote-only.png"
    db_session.commit()

    assert resolve_part_image_url(part) is None


def test_resolve_catalog_image_url_ignores_remote_url_without_blob(db_session) -> None:
    from app.services.catalog_state import resolve_catalog_image_url

    catalog = add_catalog_set(db_session)
    catalog.image_url = "https://cdn.example/set.jpg"
    db_session.commit()

    assert resolve_catalog_image_url(catalog) is None


def test_resolve_line_image_url_prefers_element_blob(db_session) -> None:
    from app.services.catalog_state import resolve_line_image_url
    from app.services.image_blob import set_element_image

    part = add_part(db_session, part_num="3024")
    set_element_image(
        db_session,
        "302424",
        content=TINY_PNG,
        content_type="image/png",
    )
    db_session.commit()

    url = resolve_line_image_url(
        element_ids=["302424"],
        part=part,
        element_url_by_id={"302424": "/api/elements/302424/image"},
    )
    assert url == "/api/elements/302424/image"


def test_resolve_line_image_url_falls_back_to_part_blob(db_session) -> None:
    from app.services.catalog_state import resolve_line_image_url
    from app.services.image_blob import set_part_image

    part = add_part(db_session, part_num="3024")
    set_part_image(db_session, part.id, content=TINY_PNG, content_type="image/png")
    db_session.commit()

    url = resolve_line_image_url(
        element_ids=["999999"],
        part=part,
        element_url_by_id={},
    )
    assert url == f"/api/parts/{part.id}/image"


def test_load_element_image_urls_returns_only_blobbed_elements(db_session) -> None:
    from app.services.catalog_state import load_element_image_urls
    from app.services.image_blob import set_element_image

    set_element_image(
        db_session,
        "302424",
        content=TINY_PNG,
        content_type="image/png",
    )
    db_session.commit()

    urls = load_element_image_urls(db_session, ["302424", "missing-element"])
    assert urls == {"302424": "/api/elements/302424/image"}
