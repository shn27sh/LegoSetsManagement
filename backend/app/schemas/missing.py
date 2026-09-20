from pydantic import BaseModel, ConfigDict, Field, model_validator


class MissingUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_part_inventory_line_id: int | None = None
    minifig_part_inventory_line_id: int | None = None
    quantity_missing: int = Field(ge=0)

    @model_validator(mode="after")
    def exactly_one_line_reference(self):
        has_set = self.set_part_inventory_line_id is not None
        has_minifig = self.minifig_part_inventory_line_id is not None
        if has_set == has_minifig:
            raise ValueError(
                "Provide exactly one of set_part_inventory_line_id or "
                "minifig_part_inventory_line_id"
            )
        return self


class MissingUpsertResponse(BaseModel):
    owned_set_id: int
    missing_item_id: int
    updated_lines: int = 1


class MissingImageResponse(BaseModel):
    missing_item_id: int
    missing_image_url: str | None
    part_image_url: str | None = None
