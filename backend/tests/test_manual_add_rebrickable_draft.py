"""Manual-add Rebrickable draft builder (DTO-only)."""

from app.rebrickable.dto import (
    CatalogSetDTO,
    ColorDTO,
    PartDTO,
    SetPartLineDTO,
    ThemeDTO,
)
from app.services.manual_add_rebrickable_draft import fetch_manual_add_rebrickable_draft
from app.services.theme_catalog import clear_theme_catalog_cache


class FakeReader:
    """Minimal Rebrickable client stub."""

    def get_set(self, set_num: str) -> CatalogSetDTO:
        return CatalogSetDTO(
            set_num=set_num,
            name="Test Set",
            year=1999,
            theme_external_id=42,
            num_parts=2,
            image_url=None,
            age=7,
        )

    def get_theme(self, theme_id: int) -> ThemeDTO:
        assert theme_id == 42
        return ThemeDTO(external_id=42, name="Classic")

    def iter_set_parts(self, set_num: str):
        part = PartDTO(part_num="3024", name="Plate", image_url=None)
        black = ColorDTO(external_id=0, name="Black", rgb=None)
        yield SetPartLineDTO(
            part=part,
            color=black,
            quantity=2,
            is_spare=False,
            is_alternate=False,
            image_url=None,
            inventory_id=1,
        )
        yield SetPartLineDTO(
            part=part,
            color=black,
            quantity=9,
            is_spare=True,
            is_alternate=False,
            image_url=None,
            inventory_id=2,
        )

    def iter_set_minifigs(self, set_num: str):
        yield from ()

    def iter_minifig_parts(self, minifig_num: str):
        yield from ()


def test_draft_includes_theme_and_filters_spares() -> None:
    draft = fetch_manual_add_rebrickable_draft(FakeReader(), "  6024-1 ")
    assert draft.set_num == 6024
    assert draft.catalog.name == "Test Set"
    assert draft.catalog.theme_name == "Classic"
    assert draft.catalog.year == 1999
    assert draft.catalog.num_parts == 2
    assert draft.age == 7
    assert len(draft.parts) == 1
    assert draft.parts[0].part_num == "3024"
    assert draft.parts[0].quantity == 2
    assert "minifig" in draft.note.casefold()


def test_draft_uses_parent_theme_from_csv(tmp_path, monkeypatch) -> None:
    themes_csv = tmp_path / "themes.csv"
    themes_csv.write_text(
        "id,name,parent_id\n"
        "52,City,\n"
        "57,Farm,52\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THEMES_CSV_PATH", str(themes_csv))
    clear_theme_catalog_cache()

    class SubthemeReader(FakeReader):
        def get_set(self, set_num: str) -> CatalogSetDTO:
            return CatalogSetDTO(
                set_num=set_num,
                name="Forest Tractor",
                year=2018,
                theme_external_id=57,
                num_parts=174,
                image_url=None,
                age=5,
            )

        def get_theme(self, theme_id: int) -> ThemeDTO:
            raise AssertionError("theme should be resolved from themes.csv")

    draft = fetch_manual_add_rebrickable_draft(SubthemeReader(), "60181-1")

    assert draft.catalog.theme_name == "City"
    clear_theme_catalog_cache()
