from app.services.element_catalog import (
    clear_element_catalog_cache,
    element_ids_for,
    element_ids_for_import,
    load_element_catalog,
)


def test_element_catalog_maps_part_and_color_to_multiple_element_ids(tmp_path) -> None:
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "302400,3024,0,3024\n"
        "6252045,3024,0,3024\n"
        "300121,3001,4,3001\n",
        encoding="utf-8",
    )
    clear_element_catalog_cache()

    catalog = load_element_catalog(str(path))

    assert catalog.element_ids_for("3024", 0) == ("302400", "6252045")
    assert catalog.element_ids_for("3024", 4) == ()
    clear_element_catalog_cache()


def test_element_ids_for_import_resolves_alias_part_num(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "4211206,4079,70,4079\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEMENTS_CSV_PATH", str(path))
    clear_element_catalog_cache()

    assert element_ids_for("4079b", 70) == ()
    assert element_ids_for_import("4079b", 70, ("4079",)) == ("4211206",)
    clear_element_catalog_cache()


def test_element_ids_for_import_resolves_sibling_mold_variant(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "6127738,30237b,72,95820\n"
        "4265794,30237b,72,30237\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEMENTS_CSV_PATH", str(path))
    clear_element_catalog_cache()

    assert element_ids_for("30237a", 72) == ()
    assert element_ids_for_import("30237a", 72, ("30237",)) == (
        "6127738",
        "4265794",
    )
    clear_element_catalog_cache()
