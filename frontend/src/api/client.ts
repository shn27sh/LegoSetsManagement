import type {
  AddSetPartLineBody,
  AddSetPreviewResponse,
  CsvImportResponse,
  DatabaseImportMode,
  DatabaseImportResponse,
  DuplicatePreviewResponse,
  ImageDeleteResponse,
  ImageUploadResponse,
  InstanceInventoryLineResponse,
  InstanceInventoryLineUpdate,
  LocalMetadataUpdateResponse,
  MissingImageResponse,
  MissingUpsertResponse,
  PartAliasesReplaceBody,
  PartAliasesResponse,
  RebrickableSetDraftResponse,
  RebrickableSyncResponse,
  IncompleteSetsReportResponse,
  IncompleteCatalogReportResponse,
  MissingPartReportItem,
  MissingPartsReportResponse,
  ReportsSummaryResponse,
  SearchResponse,
  SetCopyCreateBody,
  SetCopyCreateResponse,
  SetCopyDetailResponse,
  SetCopyDuplicateResponse,
  SetCopyListItem,
  SetCopyListResponse,
  SetCopyThemeOptionsResponse,
  SetCopyUpdateBody,
  UpdateSetPartLineBody,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const { detail } = body;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            const validationItem = item as { loc?: unknown; msg: string };
            const loc = Array.isArray(validationItem.loc)
              ? validationItem.loc
                  .filter((part) => part !== "body" && part !== "query")
                  .map(String)
                  .join(".")
              : "";
            return loc ? `${loc}: ${validationItem.msg}` : validationItem.msg;
          }
          return String(item);
        })
        .join("; ");
    }
  } catch {
    /* ignore */
  }
  return response.statusText || `HTTP ${response.status}`;
}

export async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, init);
  if (!response.ok) {
    const errorMessage = await parseErrorMessage(response);
    throw new ApiError(errorMessage, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function mediaUrl(path: string | null): string | null {
  if (!path) {
    return null;
  }
  return path;
}

export function fetchAddSetPreview(
  setNum: string | number,
): Promise<AddSetPreviewResponse> {
  const params = new URLSearchParams({ set_num: String(setNum).trim() });
  return request(`/owned-sets/add-preview?${params}`);
}

export function fetchManualAddRebrickableDraft(
  setNum: string | number,
): Promise<RebrickableSetDraftResponse> {
  const params = new URLSearchParams({ set_num: String(setNum).trim() });
  return request(`/owned-sets/add-rebrickable-draft?${params}`);
}

export function createSetCopy(
  body: SetCopyCreateBody,
): Promise<SetCopyCreateResponse> {
  return request("/owned-sets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const SET_COPY_LIST_MAX_PAGE = 200;

export type SetCopyListFilters = {
  investigated?: boolean;
  themes?: string[];
  missing_only?: boolean;
};

export function listSetCopies(params: {
  limit?: number;
  offset?: number;
  investigated?: boolean;
  themes?: string[];
  missing_only?: boolean;
  sort_by?: "created" | "set_num" | "name" | "theme" | "num_parts" | "age";
  sort_dir?: "asc" | "desc";
}): Promise<SetCopyListResponse> {
  const search = new URLSearchParams();
  if (params.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params.offset != null) {
    search.set("offset", String(params.offset));
  }
  if (params.investigated != null) {
    search.set("investigated", String(params.investigated));
  }
  for (const theme of params.themes ?? []) {
    if (theme) {
      search.append("theme", theme);
    }
  }
  if (params.missing_only) {
    search.set("missing_only", "true");
  }
  if (params.sort_by) {
    search.set("sort_by", params.sort_by);
  }
  if (params.sort_dir) {
    search.set("sort_dir", params.sort_dir);
  }
  const qs = search.toString();
  return request(`/owned-sets${qs ? `?${qs}` : ""}`);
}

/** Loads every set copy matching filters (paginated API requests). */
export async function listAllFilteredSetCopies(
  filters: SetCopyListFilters,
): Promise<SetCopyListResponse> {
  const first = await listSetCopies({
    ...filters,
    limit: SET_COPY_LIST_MAX_PAGE,
    offset: 0,
    sort_by: "created",
    sort_dir: "asc",
  });
  const items: SetCopyListItem[] = [...first.items];
  if (first.total <= items.length) {
    return { items, total: first.total };
  }
  let offset = items.length;
  while (offset < first.total) {
    const page = await listSetCopies({
      ...filters,
      limit: SET_COPY_LIST_MAX_PAGE,
      offset,
      sort_by: "created",
      sort_dir: "asc",
    });
    if (page.items.length === 0) {
      break;
    }
    items.push(...page.items);
    offset += page.items.length;
  }
  return { items, total: first.total };
}

export function listSetCopyThemeOptions(): Promise<SetCopyThemeOptionsResponse> {
  return request("/owned-sets/theme-options");
}

export function getSetCopy(id: number): Promise<SetCopyDetailResponse> {
  return request(`/owned-sets/${id}`);
}

export function updateSetCopy(
  id: number,
  body: SetCopyUpdateBody,
): Promise<SetCopyListItem> {
  return request(`/owned-sets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchDuplicatePreview(
  id: number,
): Promise<DuplicatePreviewResponse> {
  return request(`/owned-sets/${id}/duplicate-preview`);
}

export function duplicateSetCopy(
  id: number,
  label: string,
): Promise<SetCopyDuplicateResponse> {
  return request(`/owned-sets/${id}/duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
}

export function deleteSetCopy(
  id: number,
): Promise<{ deleted: boolean; id: number }> {
  return request(`/owned-sets/${id}`, { method: "DELETE" });
}

export function searchCatalog(params: {
  q: string;
  type?: "set" | "part" | "element" | "all";
  limit?: number;
}): Promise<SearchResponse> {
  const search = new URLSearchParams({ q: params.q });
  if (params.type) {
    search.set("type", params.type);
  }
  if (params.limit != null) {
    search.set("limit", String(params.limit));
  }
  return request(`/search?${search}`);
}

export function importCsv(file: File): Promise<CsvImportResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("existing_set_mode", "skip");
  return request("/imports/csv", { method: "POST", body: form });
}

/** Legacy synchronous sync; the Import UI uses `importJobs.startRebrickableSyncJob` instead. */
export function syncRebrickable(
  setCopyIds?: number[],
  options?: {
    download_set_images?: boolean;
    download_missing_part_images?: boolean;
    part_image_download_mode?: "none" | "missing" | "all" | "no_element_id";
    catalog_gap_part_keys?: Array<{ part_id: number; color_id: number }>;
  },
): Promise<RebrickableSyncResponse> {
  const body = {
    ...(setCopyIds?.length ? { owned_set_ids: setCopyIds } : {}),
    ...(options?.download_set_images
      ? { download_set_images: options.download_set_images }
      : {}),
    ...(options?.download_missing_part_images
      ? { download_missing_part_images: options.download_missing_part_images }
      : {}),
    ...(options?.part_image_download_mode
      ? { part_image_download_mode: options.part_image_download_mode }
      : {}),
  };
  return request("/imports/rebrickable/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function updateLocalMetadata(): Promise<LocalMetadataUpdateResponse> {
  return request("/imports/local-metadata", { method: "POST" });
}

export function importDatabase(
  file: File,
  mode: DatabaseImportMode,
): Promise<DatabaseImportResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  return request("/imports/database", { method: "POST", body: form });
}

export function addSetPartLine(
  setCopyId: number,
  body: AddSetPartLineBody,
): Promise<InstanceInventoryLineResponse> {
  return request(`/owned-sets/${setCopyId}/set-parts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function updateSetPartLine(
  setCopyId: number,
  instanceLineId: number,
  body: UpdateSetPartLineBody,
): Promise<InstanceInventoryLineResponse> {
  return request(`/owned-sets/${setCopyId}/set-parts/${instanceLineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteSetPartLine(
  setCopyId: number,
  instanceLineId: number,
): Promise<void> {
  return request(`/owned-sets/${setCopyId}/set-parts/${instanceLineId}`, {
    method: "DELETE",
  });
}

export function patchInstanceInventoryLine(
  setCopyId: number,
  instanceLineId: number,
  body: InstanceInventoryLineUpdate,
): Promise<InstanceInventoryLineResponse> {
  return request(
    `/owned-sets/${setCopyId}/inventory-lines/${instanceLineId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function patchMissing(
  setCopyId: number,
  body:
    | { set_part_inventory_line_id: number; quantity_missing: number }
    | { minifig_part_inventory_line_id: number; quantity_missing: number },
): Promise<MissingUpsertResponse> {
  return request(`/owned-sets/${setCopyId}/missing`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function uploadMissingImage(
  setCopyId: number,
  missingItemId: number,
  file: File,
): Promise<MissingImageResponse> {
  const form = new FormData();
  form.append("file", file);
  return request(`/owned-sets/${setCopyId}/missing/${missingItemId}/image`, {
    method: "PUT",
    body: form,
  });
}

export function deleteMissingImage(
  setCopyId: number,
  missingItemId: number,
): Promise<MissingImageResponse> {
  return request(`/owned-sets/${setCopyId}/missing/${missingItemId}/image`, {
    method: "DELETE",
  });
}

function uploadImageBlob(
  path: string,
  file: File,
): Promise<ImageUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request(path, { method: "PUT", body: form });
}

export function uploadCatalogSetImage(
  catalogSetId: number,
  file: File,
): Promise<ImageUploadResponse> {
  return uploadImageBlob(`/catalog-sets/${catalogSetId}/image`, file);
}

export function deleteCatalogSetImage(
  catalogSetId: number,
): Promise<ImageDeleteResponse> {
  return request(`/catalog-sets/${catalogSetId}/image`, { method: "DELETE" });
}

export function uploadCatalogMinifigImage(
  catalogMinifigId: number,
  file: File,
): Promise<ImageUploadResponse> {
  return uploadImageBlob(`/catalog-minifigs/${catalogMinifigId}/image`, file);
}

export function deleteCatalogMinifigImage(
  catalogMinifigId: number,
): Promise<ImageDeleteResponse> {
  return request(`/catalog-minifigs/${catalogMinifigId}/image`, {
    method: "DELETE",
  });
}

export function uploadPartImage(
  partId: number,
  file: File,
): Promise<ImageUploadResponse> {
  return uploadImageBlob(`/parts/${partId}/image`, file);
}

export function deletePartImage(partId: number): Promise<ImageDeleteResponse> {
  return request(`/parts/${partId}/image`, { method: "DELETE" });
}

export function patchPartAliases(
  partId: number,
  body: PartAliasesReplaceBody,
): Promise<PartAliasesResponse> {
  return request(`/parts/${partId}/aliases`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getReportsSummary(): Promise<ReportsSummaryResponse> {
  return request("/reports/summary");
}

export function getIncompleteSetsReport(params?: {
  limit?: number;
  offset?: number;
}): Promise<IncompleteSetsReportResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params?.offset != null) {
    search.set("offset", String(params.offset));
  }
  const query = search.toString();
  return request(`/reports/incomplete-sets${query ? `?${query}` : ""}`);
}

export function getMissingPartsReport(params?: {
  owned_set_ids?: number[];
  limit?: number;
  offset?: number;
}): Promise<MissingPartsReportResponse> {
  const search = new URLSearchParams();
  for (const id of params?.owned_set_ids ?? []) {
    search.append("owned_set_ids", String(id));
  }
  if (params?.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params?.offset != null) {
    search.set("offset", String(params.offset));
  }
  const query = search.toString();
  return request(`/reports/missing-parts${query ? `?${query}` : ""}`);
}

export function getIncompleteCatalogReport(params?: {
  limit?: number;
  offset?: number;
}): Promise<IncompleteCatalogReportResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) {
    search.set("limit", String(params.limit));
  }
  if (params?.offset != null) {
    search.set("offset", String(params.offset));
  }
  const query = search.toString();
  return request(`/reports/incomplete-catalog${query ? `?${query}` : ""}`);
}

const MISSING_PARTS_REPORT_PAGE_SIZE = 200;

export async function fetchAllMissingPartsReport(params?: {
  owned_set_ids?: number[];
}): Promise<MissingPartReportItem[]> {
  const items: MissingPartReportItem[] = [];
  let offset = 0;
  let total = 0;

  do {
    const page = await getMissingPartsReport({
      ...params,
      limit: MISSING_PARTS_REPORT_PAGE_SIZE,
      offset,
    });
    total = page.total;
    items.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0) {
      break;
    }
  } while (items.length < total);

  return items;
}
