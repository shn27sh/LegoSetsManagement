/**
 * Types for `GET/POST /owned-sets` (etc.). JSON still uses `owned_set_*` where noted;
 * each list/detail row is a **set copy** in the user's collection — the app does not store
 * LEGO sets the user does not own (`catalog_sets` is shared metadata and is removed when the
 * last copy is deleted).
 */
export interface SetCopyListItem {
  id: number;
  set_num: number;
  name: string | null;
  year: number | null;
  theme_name: string | null;
  image_url: string | null;
  catalog_sync_state: string;
  investigated: boolean;
  label: string | null;
  display_label: string;
  copy_index: number;
  age: number | null;
  num_parts: number | null;
  missing_count: number;
}

export interface DuplicatePreviewResponse {
  source_owned_set_id: number;
  set_num: number;
  set_name: string | null;
  existing_copy_count: number;
  suggested_label: string;
}

export type CatalogThemeScope = "all" | "this_set";

export interface SetCopyUpdateBody {
  investigated?: boolean;
  label?: string | null;
  notes?: string | null;
  age?: number | null;
  set_num?: string;
  catalog_name?: string | null;
  catalog_num_parts?: number | null;
  catalog_year?: number | null;
  catalog_theme_name?: string | null;
  catalog_theme_scope?: CatalogThemeScope;
}

export interface SetCopyListResponse {
  items: SetCopyListItem[];
  total: number;
}

export interface SetCopyThemeOptionsResponse {
  themes: string[];
}

export interface SetCopyDuplicateResponse extends SetCopyListItem {
  duplicated_from_owned_set_id: number;
}

export interface CatalogBlock {
  catalog_set_id: number;
  set_num: number;
  name: string | null;
  year: number | null;
  theme_name: string | null;
  theme_shared_catalog_set_count: number;
  image_url: string | null;
  num_parts: number | null;
}

export interface AddSetPartLineBody {
  part_num: string;
  part_name?: string | null;
  color_id?: number;
  color_name?: string | null;
  quantity: number;
}

export interface InstanceInventoryLineUpdate {
  quantity?: number;
  quantity_missing?: number;
}

export interface UpdateSetPartLineBody {
  part_name?: string | null;
  color_id?: number;
  color_name?: string | null;
  quantity?: number;
}

export interface InstanceInventoryLineResponse {
  instance_line_id: number;
  part_id: number;
  catalog_line_id: number;
  quantity: number;
  quantity_missing: number;
}

export interface SetPartLineDetail {
  instance_line_id: number;
  catalog_line_id: number;
  part_id: number;
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string;
  quantity: number;
  element_ids: string[];
  aliases: string[];
  image_url: string | null;
  part_image_url: string | null;
  part_image_user_removed?: boolean;
  missing_quantity: number;
  missing_item_id: number | null;
  missing_image_url: string | null;
}

export interface MinifigPartLineDetail {
  instance_line_id: number;
  catalog_line_id: number;
  part_id: number;
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string;
  quantity: number;
  element_ids: string[];
  image_url: string | null;
  part_image_url: string | null;
  part_image_user_removed?: boolean;
  missing_quantity: number;
  missing_item_id: number | null;
  missing_image_url: string | null;
}

export interface MinifigInventoryBlock {
  line_id: number;
  catalog_minifig_id: number;
  minifig_num: string;
  name: string | null;
  image_url: string | null;
  quantity: number;
  parts: MinifigPartLineDetail[];
}

export interface InventoryBlock {
  set_parts: SetPartLineDetail[];
  minifigs: MinifigInventoryBlock[];
}

export interface SetCopyDetailResponse {
  id: number;
  investigated: boolean;
  label: string | null;
  display_label: string;
  copy_index: number;
  age: number | null;
  notes: string | null;
  catalog: CatalogBlock;
  inventory: InventoryBlock;
}

export interface SearchSetResult {
  /** Collection row id (same as `/sets/:id`). */
  owned_set_id: number;
  set_num: number;
  name: string | null;
  investigated: boolean;
  label: string | null;
}

export interface SearchPartSetOccurrence {
  set_num: number;
  quantity: number;
  owned_set_id: number;
  colors: SearchPartColorOccurrence[];
}

export interface SearchPartColorOccurrence {
  color_id: number;
  color_name: string;
  quantity: number;
}

export interface SearchPartDisplayLine {
  display_part_num: string;
  sets: SearchPartSetOccurrence[];
}

export interface SearchPartResult {
  part_num: string;
  name: string | null;
  image_url: string | null;
  lines: SearchPartDisplayLine[];
}

export interface SearchElementSetOccurrence {
  set_num: number;
  quantity: number;
  owned_set_id: number;
}

export interface SearchElementResult {
  element_ids: string[];
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string;
  sets: SearchElementSetOccurrence[];
}

export interface SearchResponse {
  sets: SearchSetResult[];
  parts: SearchPartResult[];
  elements: SearchElementResult[];
}

export interface AddPreviewPartLine {
  part_num: string;
  part_name: string | null;
  color_name: string;
  quantity: number;
}

export interface AddSetPreviewResponse {
  set_num: number;
  catalog_exists: boolean;
  set_name: string | null;
  existing_copy_count: number;
  suggested_label: string;
  theme_name: string | null;
  year: number | null;
  num_parts: number | null;
  age: number | null;
  image_url: string | null;
  set_parts: AddPreviewPartLine[];
}

export interface ManualAddCatalogInput {
  name?: string | null;
  theme_name?: string | null;
  year?: number | null;
  num_parts?: number | null;
}

export interface ManualAddPartInput {
  part_num: string;
  part_name?: string | null;
  color_id?: number;
  color_name?: string | null;
  quantity: number;
}

export interface SetCopyCreateBody {
  set_num: number;
  label?: string | null;
  age?: number | null;
  catalog?: ManualAddCatalogInput;
  parts?: ManualAddPartInput[];
}

/** Live Rebrickable draft for wizard prefill (`GET /owned-sets/add-rebrickable-draft`). */
export interface RebrickableSetDraftResponse {
  set_num: number;
  catalog: ManualAddCatalogInput;
  age: number | null;
  parts: ManualAddPartInput[];
  note: string;
}

export interface SetCopyCreateResponse extends SetCopyListItem {
  catalog_created: boolean;
}

export interface CsvImportSetFailure {
  token_index: number;
  set_num: number;
  message: string;
}

export interface CsvImportSkippedExistingSet {
  token_index: number;
  set_num: string;
}

export interface CsvImportResponse {
  instances_created: number;
  catalog_stubs_created: number;
  sets_fetched: number;
  existing_sets_skipped: number;
  skipped_existing_sets: CsvImportSkippedExistingSet[];
  sets_failed: CsvImportSetFailure[];
  errors: { token_index: number; raw: string; message: string }[];
  set_images_downloaded: number;
  minifig_images_downloaded: number;
  part_images_downloaded: number;
  image_downloads_failed: { target: string; url: string; message: string }[];
}

export interface RebrickableSyncResponse {
  sets_synced: number;
  sets_failed: { set_num: string; message: string }[];
  parts_upserted: number;
  inventory_lines_written: number;
  set_images_downloaded: number;
  minifig_images_downloaded: number;
  part_images_downloaded: number;
  image_downloads_failed: { target: string; url: string; message: string }[];
}

export interface LocalMetadataUpdateResponse {
  owned_set_ages_updated: number;
  catalog_themes_updated: number;
  age_values_available: number;
  theme_values_available: number;
}

export type DatabaseImportMode = "add_only_new" | "add_and_update";

export interface DatabaseImportResponse {
  sets_added: number;
  sets_updated: number;
  sets_skipped: number;
  skipped_set_nums: string[];
  instances_created: number;
  parts_upserted: number;
  inventory_lines_written: number;
}

export type ImportJobKind = "csv" | "rebrickable_sync" | "database";

export type ImportJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ImportJobProgress {
  current: number;
  total: number;
  label: string;
}

export interface ImportJobStartResponse {
  job_id: string;
  status: ImportJobStatus;
}

export interface ImportJobStatusResponse {
  job_id: string;
  kind: ImportJobKind;
  status: ImportJobStatus;
  progress: ImportJobProgress | null;
  result:
    | CsvImportResponse
    | RebrickableSyncResponse
    | DatabaseImportResponse
    | null;
  error: string | null;
  failed_sets_csv_path: string | null;
}

export interface MissingUpsertResponse {
  /** Set copy this missing row belongs to (`owned_sets.id`). */
  owned_set_id: number;
  missing_item_id: number;
  updated_lines: number;
}

export interface ImageUploadResponse {
  image_url: string;
}

export interface ImageDeleteResponse {
  image_url: string | null;
}

export interface PartAliasesReplaceBody {
  aliases: string[];
}

export interface PartAliasesResponse {
  part_id: number;
  part_num: string;
  aliases: string[];
}

export interface MissingImageResponse {
  missing_item_id: number;
  missing_image_url: string | null;
  part_image_url: string | null;
}

export interface ReportsSummaryResponse {
  total_sets: number;
  investigated_sets: number;
  complete_sets: number;
  total_parts: number;
  missing_parts: number;
}

export interface IncompleteSetMissingLine {
  part_id: number;
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string | null;
  quantity_missing: number;
  element_ids: string[];
  part_image_url: string | null;
}

export interface IncompleteSetReportItem {
  id: number;
  set_num: number;
  name: string | null;
  display_label: string;
  investigated: boolean;
  missing_line_count: number;
  missing_parts_total: number;
  missing_lines: IncompleteSetMissingLine[];
}

export interface IncompleteSetsReportResponse {
  items: IncompleteSetReportItem[];
  total: number;
}

export interface MissingPartNeededSet {
  owned_set_id: number;
  set_num: number;
  set_name: string | null;
  display_label: string;
  quantity_missing: number;
}

export interface MissingPartReportItem {
  part_id: number;
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string | null;
  quantity_missing_total: number;
  element_ids: string[];
  part_image_url: string | null;
  needed_sets: MissingPartNeededSet[];
}

export interface MissingPartsReportResponse {
  items: MissingPartReportItem[];
  total: number;
}

export interface CatalogGapSetOccurrence {
  owned_set_id: number;
  set_num: number;
  set_name: string | null;
  display_label: string;
}

export interface IncompleteCatalogReportItem {
  part_id: number;
  part_num: string;
  part_name: string | null;
  color_id: number;
  color_name: string | null;
  element_ids: string[];
  part_image_url: string | null;
  missing_element_id: boolean;
  missing_image: boolean;
  sets: CatalogGapSetOccurrence[];
}

export interface IncompleteCatalogReportResponse {
  items: IncompleteCatalogReportItem[];
  total: number;
}
