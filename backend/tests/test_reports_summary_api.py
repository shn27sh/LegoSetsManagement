from tests.factories import (
    add_catalog_set,
    add_color,
    add_missing_item_for_set_line,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
)


def test_reports_summary_empty_collection(api_client) -> None:
    response = api_client.get("/api/reports/summary")
    assert response.status_code == 200
    assert response.json() == {
        "total_sets": 0,
        "investigated_sets": 0,
        "complete_sets": 0,
        "total_parts": 0,
        "missing_parts": 0,
    }


def test_reports_summary_counts(api_client, db_session) -> None:
    catalog = add_catalog_set(db_session)
    part_a = add_part(db_session, part_num="3001")
    part_b = add_part(db_session, part_num="3002")
    color = add_color(db_session)
    line_a = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part_a,
        color=color,
        quantity=4,
    )
    line_b = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part_b,
        color=color,
        quantity=2,
    )

    uninvestigated_incomplete = add_owned_set(
        db_session, catalog, investigated=False, label="copy A"
    )
    complete = add_owned_set(db_session, catalog, investigated=True, label="copy B")
    investigated_incomplete = add_owned_set(
        db_session, catalog, investigated=True, label="copy C"
    )

    add_missing_item_for_set_line(
        db_session,
        owned_set=uninvestigated_incomplete,
        line=line_a,
        quantity_missing=2,
    )
    add_missing_item_for_set_line(
        db_session,
        owned_set=investigated_incomplete,
        line=line_b,
        quantity_missing=1,
    )
    db_session.commit()

    response = api_client.get("/api/reports/summary")
    assert response.status_code == 200
    assert response.json() == {
        "total_sets": 3,
        "investigated_sets": 2,
        "complete_sets": 1,
        "total_parts": 18,
        "missing_parts": 3,
    }
