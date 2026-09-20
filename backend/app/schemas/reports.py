from pydantic import BaseModel


class ReportsSummaryResponse(BaseModel):
    total_sets: int
    investigated_sets: int
    complete_sets: int
    total_parts: int
    missing_parts: int


class IncompleteSetMissingLine(BaseModel):
    part_id: int
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str | None
    quantity_missing: int
    element_ids: list[str]
    part_image_url: str | None


class IncompleteSetReportItem(BaseModel):
    id: int
    set_num: int
    name: str | None
    display_label: str
    investigated: bool
    missing_line_count: int
    missing_parts_total: int
    missing_lines: list[IncompleteSetMissingLine]


class IncompleteSetsReportResponse(BaseModel):
    items: list[IncompleteSetReportItem]
    total: int


class MissingPartNeededSet(BaseModel):
    owned_set_id: int
    set_num: int
    set_name: str | None
    display_label: str
    quantity_missing: int


class MissingPartReportItem(BaseModel):
    part_id: int
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str | None
    quantity_missing_total: int
    element_ids: list[str]
    part_image_url: str | None
    needed_sets: list[MissingPartNeededSet]


class MissingPartsReportResponse(BaseModel):
    items: list[MissingPartReportItem]
    total: int


class CatalogGapSetOccurrence(BaseModel):
    owned_set_id: int
    set_num: int
    set_name: str | None
    display_label: str


class IncompleteCatalogReportItem(BaseModel):
    part_id: int
    part_num: str
    part_name: str | None
    color_id: int
    color_name: str | None
    element_ids: list[str]
    part_image_url: str | None
    missing_element_id: bool
    missing_image: bool
    sets: list[CatalogGapSetOccurrence]


class IncompleteCatalogReportResponse(BaseModel):
    items: list[IncompleteCatalogReportItem]
    total: int
