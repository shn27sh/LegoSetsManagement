from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CatalogThemeScope = Literal["all", "this_set"]


class OwnedSetListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_num: int
    name: str | None
    year: int | None
    theme_name: str | None
    image_url: str | None
    catalog_sync_state: str
    investigated: bool
    label: str | None
    display_label: str
    copy_index: int
    age: int | None
    num_parts: int | None
    missing_count: int


class OwnedSetListResponse(BaseModel):
    items: list[OwnedSetListItem]
    total: int


class OwnedSetThemeOptionsResponse(BaseModel):
    themes: list[str]


class OwnedSetUpdateRequest(BaseModel):
    investigated: bool | None = None
    label: str | None = None
    notes: str | None = None
    age: int | None = None
    set_num: str | None = None
    catalog_name: str | None = None
    catalog_num_parts: int | None = None
    catalog_year: int | None = None
    catalog_theme_name: str | None = None
    catalog_theme_scope: CatalogThemeScope = "all"


class DuplicatePreviewResponse(BaseModel):
    source_owned_set_id: int
    set_num: int
    set_name: str | None
    existing_copy_count: int
    suggested_label: str


class DuplicateRequest(BaseModel):
    label: str | None = None


class OwnedSetDuplicateResponse(OwnedSetListItem):
    duplicated_from_owned_set_id: int


class OwnedSetDeleteResponse(BaseModel):
    deleted: bool
    id: int


class CatalogBlock(BaseModel):
    catalog_set_id: int
    set_num: int
    name: str | None
    year: int | None
    theme_name: str | None
    theme_shared_catalog_set_count: int = 0
    image_url: str | None
    num_parts: int | None


class SetPartLineDetail(BaseModel):
    instance_line_id: int
    catalog_line_id: int
    part_id: int
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str
    quantity: int
    element_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    image_url: str | None
    part_image_url: str | None
    part_image_user_removed: bool = False
    missing_quantity: int
    missing_item_id: int | None
    missing_image_url: str | None


class MinifigPartLineDetail(BaseModel):
    instance_line_id: int
    catalog_line_id: int
    part_id: int
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str
    quantity: int
    element_ids: list[str] = Field(default_factory=list)
    image_url: str | None
    part_image_url: str | None
    part_image_user_removed: bool = False
    missing_quantity: int
    missing_item_id: int | None
    missing_image_url: str | None


class MinifigInventoryBlock(BaseModel):
    line_id: int
    catalog_minifig_id: int
    minifig_num: str
    name: str | None
    image_url: str | None
    quantity: int
    parts: list[MinifigPartLineDetail]


class InventoryBlock(BaseModel):
    set_parts: list[SetPartLineDetail]
    minifigs: list[MinifigInventoryBlock]


class OwnedSetDetailResponse(BaseModel):
    id: int
    investigated: bool
    label: str | None
    display_label: str
    copy_index: int
    age: int | None
    notes: str | None
    catalog: CatalogBlock
    inventory: InventoryBlock
