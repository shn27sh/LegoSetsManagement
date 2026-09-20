"""Map Rebrickable API JSON objects to DTOs."""

from __future__ import annotations

from typing import Any

from app.utils.age import parse_age_value

from app.rebrickable.dto import (
    CatalogSetDTO,
    ColorDTO,
    MinifigPartLineDTO,
    PartDTO,
    SetMinifigLineDTO,
    SetPartLineDTO,
    ThemeDTO,
)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _part_aliases(part: dict[str, Any]) -> tuple[str, ...]:
    external_ids = part.get("external_ids")
    if not isinstance(external_ids, dict):
        return ()
    aliases: list[str] = []
    for values in external_ids.values():
        if isinstance(values, list):
            aliases.extend(str(v) for v in values if v)
    return tuple(dict.fromkeys(aliases))


def map_theme(data: dict[str, Any]) -> ThemeDTO:
    return ThemeDTO(
        external_id=int(data["id"]),
        name=str(data["name"]),
    )


def map_set(data: dict[str, Any]) -> CatalogSetDTO:
    return CatalogSetDTO(
        set_num=str(data["set_num"]),
        name=_optional_str(data.get("name")),
        year=int(data["year"]) if data.get("year") is not None else None,
        theme_external_id=int(data["theme_id"])
        if data.get("theme_id") is not None
        else None,
        num_parts=int(data["num_parts"]) if data.get("num_parts") is not None else None,
        image_url=_optional_str(data.get("set_img_url")),
        age=parse_age_value(data.get("age_range") or data.get("age")),
    )


def map_color(data: dict[str, Any]) -> ColorDTO:
    return ColorDTO(
        external_id=int(data["id"]),
        name=str(data["name"]),
        rgb=_optional_str(data.get("rgb")),
    )


def map_part(data: dict[str, Any]) -> PartDTO:
    return PartDTO(
        part_num=str(data["part_num"]),
        name=_optional_str(data.get("name")),
        image_url=_optional_str(data.get("part_img_url")),
        aliases=_part_aliases(data),
    )


def map_set_part_result(item: dict[str, Any]) -> SetPartLineDTO:
    part_data = item.get("part")
    color_data = item.get("color")
    if not isinstance(part_data, dict) or not isinstance(color_data, dict):
        raise ValueError("set part result missing part or color object")

    image_url = _optional_str(item.get("element_img_url")) or _optional_str(
        part_data.get("part_img_url")
    )
    inventory_id = item.get("inventory_id")
    if inventory_id is None:
        inventory_id = item.get("id")

    return SetPartLineDTO(
        part=map_part(part_data),
        color=map_color(color_data),
        quantity=int(item["quantity"]),
        is_spare=bool(item.get("is_spare", False)),
        is_alternate=bool(item.get("is_alternate", False)),
        image_url=image_url,
        inventory_id=int(inventory_id) if inventory_id is not None else None,
    )


def map_set_minifig_result(item: dict[str, Any]) -> SetMinifigLineDTO:
    minifig = item.get("set")
    if isinstance(minifig, dict):
        minifig_num = str(minifig.get("set_num", item.get("set_num", "")))
        name = _optional_str(minifig.get("name"))
        image_url = _optional_str(minifig.get("set_img_url"))
    else:
        minifig_num = str(item["set_num"])
        name = _optional_str(item.get("name"))
        image_url = _optional_str(item.get("set_img_url"))

    return SetMinifigLineDTO(
        minifig_num=minifig_num,
        name=name,
        image_url=image_url,
        quantity=int(item.get("quantity", 1)),
    )


def map_minifig_part_result(item: dict[str, Any]) -> MinifigPartLineDTO:
    part_data = item.get("part")
    color_data = item.get("color")
    if not isinstance(part_data, dict) or not isinstance(color_data, dict):
        raise ValueError("minifig part result missing part or color object")

    image_url = _optional_str(item.get("element_img_url")) or _optional_str(
        part_data.get("part_img_url")
    )

    return MinifigPartLineDTO(
        part=map_part(part_data),
        color=map_color(color_data),
        quantity=int(item["quantity"]),
        is_spare=bool(item.get("is_spare", False)),
        image_url=image_url,
    )
