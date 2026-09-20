from app.rebrickable.mappers import (
    map_color,
    map_minifig_part_result,
    map_set,
    map_set_minifig_result,
    map_set_part_result,
    map_theme,
)
from tests.rebrickable_helpers import load_fixture


def test_map_set() -> None:
    dto = map_set(load_fixture("set_6024.json"))
    assert dto.set_num == "6024-1"
    assert dto.name == "Police Car"
    assert dto.year == 1980
    assert dto.theme_external_id == 67
    assert dto.num_parts == 24
    assert dto.image_url.endswith("6024-1.jpg")
    assert dto.age == 6


def test_map_set_part_result() -> None:
    item = load_fixture("parts_page1.json")["results"][0]
    line = map_set_part_result(item)
    assert line.part.part_num == "3024"
    assert line.part.aliases == ("3024",)
    assert line.color.external_id == 0
    assert line.quantity == 4
    assert line.is_spare is False
    assert line.inventory_id == 1001


def test_map_set_minifig_result() -> None:
    item = load_fixture("minifigs.json")["results"][0]
    line = map_set_minifig_result(item)
    assert line.minifig_num == "cop01"
    assert line.name == "Police Officer"
    assert line.quantity == 1


def test_map_minifig_part_result() -> None:
    item = load_fixture("minifig_parts.json")["results"][0]
    line = map_minifig_part_result(item)
    assert line.part.part_num == "973c27h01pr0126"
    assert line.image_url == "https://cdn.rebrickable.com/media/parts/elements/973.jpg"
    assert line.quantity == 1


def test_map_theme_and_color() -> None:
    theme = map_theme(load_fixture("theme_67.json"))
    assert theme.external_id == 67
    assert theme.name == "Town"

    color = map_color(load_fixture("colors_page1.json")["results"][0])
    assert color.external_id == 0
    assert color.rgb == "05131D"
