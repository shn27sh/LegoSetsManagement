from app.rebrickable.dto import ThemeDTO
from app.services.theme_catalog import clear_theme_catalog_cache, load_theme_catalog


def test_theme_catalog_resolves_parent_theme(tmp_path) -> None:
    path = tmp_path / "themes.csv"
    path.write_text(
        "id,name,parent_id\n"
        "52,City,\n"
        "57,Farm,52\n",
        encoding="utf-8",
    )
    clear_theme_catalog_cache()

    catalog = load_theme_catalog(str(path))

    assert catalog.display_theme_for(57) == ThemeDTO(external_id=52, name="City")
    assert catalog.display_theme_for(52) == ThemeDTO(external_id=52, name="City")
    assert catalog.display_theme_for(999) is None
    clear_theme_catalog_cache()


def test_theme_catalog_uses_child_when_parent_missing(tmp_path) -> None:
    path = tmp_path / "themes.csv"
    path.write_text(
        "id,name,parent_id\n"
        "57,Farm,52\n",
        encoding="utf-8",
    )
    clear_theme_catalog_cache()

    catalog = load_theme_catalog(str(path))

    assert catalog.display_theme_for(57) == ThemeDTO(external_id=57, name="Farm")
    clear_theme_catalog_cache()
