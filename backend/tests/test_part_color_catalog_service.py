from sqlalchemy import func, select

from app.db.models import PartColorKey
from app.services.part_color_catalog_service import (
    backfill_part_color_element_ids_from_csv,
    element_ids_for_part_color,
    enrich_element_ids_for_part_color,
    find_part_color_keys_by_element_prefix,
    load_element_ids_for_part_colors,
    set_element_ids_for_part_color,
)
from app.services.element_catalog import clear_element_catalog_cache
from tests.factories import (
    add_catalog_set,
    add_color,
    add_owned_set,
    add_part,
    add_part_alias,
    add_set_part_inventory_line,
)


def test_element_ids_shared_across_alias_class_and_sets(db_session) -> None:
    color = add_color(db_session, external_id=70, name="Reddish Brown")
    part_plain = add_part(db_session, part_num="4079")
    part_b = add_part(db_session, part_num="4079b")
    add_part_alias(db_session, part_b, "4079")

    catalog_a = add_catalog_set(db_session, set_number=6864)
    catalog_b = add_catalog_set(db_session, set_number=1002)
    line_a = add_set_part_inventory_line(
        db_session, catalog_set=catalog_a, part=part_b, color=color
    )
    line_b = add_set_part_inventory_line(
        db_session, catalog_set=catalog_b, part=part_plain, color=color
    )
    set_element_ids_for_part_color(db_session, part_b.id, color.id, ("4211206",))
    add_owned_set(db_session, catalog_a, with_inventory=True)
    add_owned_set(db_session, catalog_b, with_inventory=True)
    db_session.commit()

    assert element_ids_for_part_color(db_session, line_a.part_id, color.id) == [
        "4211206"
    ]
    assert element_ids_for_part_color(db_session, line_b.part_id, color.id) == [
        "4211206"
    ]


def test_set_element_ids_for_part_color_replaces_canonical(db_session) -> None:
    color = add_color(db_session, external_id=0, name="Black")
    part = add_part(db_session, part_num="3024")
    add_set_part_inventory_line(
        db_session,
        catalog_set=add_catalog_set(db_session),
        part=part,
        color=color,
    )
    set_element_ids_for_part_color(db_session, part.id, color.id, ("302400", "6252045"))
    db_session.commit()

    assert element_ids_for_part_color(db_session, part.id, color.id) == [
        "302400",
        "6252045",
    ]

    set_element_ids_for_part_color(db_session, part.id, color.id, ("999999",))
    db_session.commit()
    assert element_ids_for_part_color(db_session, part.id, color.id) == ["999999"]


def test_set_element_ids_for_part_color_merges_when_requested(db_session) -> None:
    color = add_color(db_session, external_id=1, name="Blue")
    part = add_part(db_session, part_num="3001")

    set_element_ids_for_part_color(db_session, part.id, color.id, ("300101",))
    set_element_ids_for_part_color(
        db_session,
        part.id,
        color.id,
        ("300102",),
        merge=True,
    )
    db_session.commit()

    assert element_ids_for_part_color(db_session, part.id, color.id) == [
        "300101",
        "300102",
    ]


def test_load_element_ids_for_part_colors_uses_anchor_sharing(db_session) -> None:
    color = add_color(db_session, external_id=72, name="Dark Bluish Gray")
    part_base = add_part(db_session, part_num="30237")
    part_variant = add_part(db_session, part_num="30237b")
    add_part_alias(db_session, part_variant, "30237")

    set_element_ids_for_part_color(
        db_session,
        part_base.id,
        color.id,
        ("4265794", "6127738"),
    )
    db_session.commit()

    loaded = load_element_ids_for_part_colors(
        db_session,
        {
            (part_base.id, color.id),
            (part_variant.id, color.id),
            (part_base.id, color.id + 999),
        },
    )

    assert loaded[(part_base.id, color.id)] == ["4265794", "6127738"]
    assert loaded[(part_variant.id, color.id)] == ["4265794", "6127738"]
    assert loaded[(part_base.id, color.id + 999)] == []


def test_find_part_color_keys_by_element_prefix_returns_distinct_pairs(db_session) -> None:
    color = add_color(db_session, external_id=86, name="Light Bluish Gray")
    part = add_part(db_session, part_num="4070")

    set_element_ids_for_part_color(
        db_session,
        part.id,
        color.id,
        ("4211", "4211206", "6252045"),
    )
    db_session.commit()

    pairs = find_part_color_keys_by_element_prefix(db_session, "4211")
    assert pairs == [(part.id, color.id)]

    key_count = db_session.scalar(select(func.count()).select_from(PartColorKey))
    assert key_count == 1


def test_enrich_element_ids_for_part_color_persists_from_csv(
    db_session, tmp_path, monkeypatch
) -> None:
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "4211206,4079,70,4079\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEMENTS_CSV_PATH", str(path))
    clear_element_catalog_cache()

    color = add_color(db_session, external_id=70, name="Reddish Brown")
    part = add_part(db_session, part_num="4079b")
    add_part_alias(db_session, part, "4079")

    enrich_element_ids_for_part_color(
        db_session,
        part.id,
        color.id,
        part_num=part.part_num,
        color_external_id=color.external_id,
        aliases=("4079",),
    )
    db_session.commit()
    clear_element_catalog_cache()

    assert element_ids_for_part_color(db_session, part.id, color.id) == ["4211206"]


def test_backfill_part_color_element_ids_from_csv_enriches_inventory(
    db_session, tmp_path, monkeypatch
) -> None:
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "6347310,44861,0,44861\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEMENTS_CSV_PATH", str(path))
    clear_element_catalog_cache()

    color = add_color(db_session, external_id=0, name="Black")
    part = add_part(db_session, part_num="44861")
    add_set_part_inventory_line(
        db_session,
        catalog_set=add_catalog_set(db_session, set_number=71720),
        part=part,
        color=color,
    )
    db_session.commit()

    assert element_ids_for_part_color(db_session, part.id, color.id) == []

    enriched = backfill_part_color_element_ids_from_csv(db_session)
    db_session.commit()
    clear_element_catalog_cache()

    assert enriched == 1
    assert element_ids_for_part_color(db_session, part.id, color.id) == ["6347310"]
