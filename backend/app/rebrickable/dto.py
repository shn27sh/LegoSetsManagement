"""Domain DTOs parsed from Rebrickable JSON (no ORM)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThemeDTO:
    external_id: int
    name: str


@dataclass(frozen=True)
class CatalogSetDTO:
    set_num: str
    name: str | None
    year: int | None
    theme_external_id: int | None
    num_parts: int | None
    image_url: str | None
    age: int | None = None


@dataclass(frozen=True)
class ColorDTO:
    external_id: int
    name: str
    rgb: str | None


@dataclass(frozen=True)
class PartDTO:
    part_num: str
    name: str | None
    image_url: str | None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetPartLineDTO:
    part: PartDTO
    color: ColorDTO
    quantity: int
    is_spare: bool
    is_alternate: bool
    image_url: str | None
    inventory_id: int | None


@dataclass(frozen=True)
class SetMinifigLineDTO:
    minifig_num: str
    name: str | None
    image_url: str | None
    quantity: int


@dataclass(frozen=True)
class MinifigPartLineDTO:
    part: PartDTO
    color: ColorDTO
    quantity: int
    is_spare: bool
    image_url: str | None
