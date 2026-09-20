from pydantic import BaseModel, ConfigDict, Field


class AddPreviewPartLine(BaseModel):
    part_num: str
    part_name: str | None
    color_name: str
    quantity: int


class OwnedSetAddPreviewResponse(BaseModel):
    set_num: int
    catalog_exists: bool
    set_name: str | None
    existing_copy_count: int
    suggested_label: str
    theme_name: str | None = None
    year: int | None = None
    num_parts: int | None = None
    age: int | None = None
    image_url: str | None = None
    set_parts: list[AddPreviewPartLine] = Field(default_factory=list)


class ManualAddCatalogInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    theme_name: str | None = None
    year: int | None = None
    num_parts: int | None = None


class ManualAddPartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_num: str
    part_name: str | None = None
    color_id: int = 0
    color_name: str | None = None
    quantity: int = Field(gt=0)


class OwnedSetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_num: int | str
    label: str | None = None
    age: int | None = None
    catalog: ManualAddCatalogInput | None = None
    parts: list[ManualAddPartInput] | None = None


class OwnedSetCreateResponse(BaseModel):
    catalog_created: bool
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


class OwnedSetRebrickableDraftResponse(BaseModel):
    """Draft catalog + set-part lines from Rebrickable for the manual-add wizard (no persistence)."""

    set_num: int
    catalog: ManualAddCatalogInput
    age: int | None
    parts: list[ManualAddPartInput]

    #: Minifig BOM rows are omitted; CSV import or sync still applies them to the catalog.
    note: str = (
        "Set-level parts only; minifig breakdown is added when you CSV-import or sync this set "
        "from Rebrickable later."
    )
