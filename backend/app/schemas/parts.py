from pydantic import BaseModel, ConfigDict, Field


class PartAliasesReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list)


class PartAliasesResponse(BaseModel):
    part_id: int
    part_num: str
    aliases: list[str]
