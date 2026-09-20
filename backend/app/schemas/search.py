from __future__ import annotations

from pydantic import BaseModel, Field


class SearchSetResult(BaseModel):
    owned_set_id: int
    set_num: int
    name: str | None
    investigated: bool
    label: str | None


class SearchPartSetOccurrence(BaseModel):
    """One catalog set in the user’s collection that includes this part (template BOM)."""

    set_num: int
    quantity: int
    owned_set_id: int
    colors: list["SearchPartColorOccurrence"] = Field(default_factory=list)


class SearchPartColorOccurrence(BaseModel):
    color_id: int
    color_name: str
    quantity: int


class SearchPartDisplayLine(BaseModel):
    """Part number or alias label with where it appears in the user’s sets."""

    display_part_num: str
    sets: list[SearchPartSetOccurrence] = Field(default_factory=list)


class SearchPartResult(BaseModel):
    part_num: str
    name: str | None
    image_url: str | None
    lines: list[SearchPartDisplayLine] = Field(default_factory=list)


class SearchElementSetOccurrence(BaseModel):
    set_num: int
    quantity: int
    owned_set_id: int


class SearchElementResult(BaseModel):
    element_ids: list[str] = Field(default_factory=list)
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str
    sets: list[SearchElementSetOccurrence] = Field(default_factory=list)


class SearchResponse(BaseModel):
    sets: list[SearchSetResult] = []
    parts: list[SearchPartResult] = []
    elements: list[SearchElementResult] = []
