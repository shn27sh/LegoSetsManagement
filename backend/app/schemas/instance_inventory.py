from pydantic import BaseModel, ConfigDict, Field


class AddSetPartLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_num: str
    part_name: str | None = None
    color_id: int = 0
    color_name: str | None = None
    quantity: int = Field(gt=0)


class InstanceInventoryLineUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    quantity_missing: int | None = Field(default=None, ge=0)


class UpdateSetPartLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_name: str | None = None
    color_id: int | None = None
    color_name: str | None = None
    quantity: int | None = Field(default=None, gt=0)


class InstanceInventoryLineResponse(BaseModel):
    instance_line_id: int
    part_id: int
    catalog_line_id: int
    quantity: int
    quantity_missing: int
