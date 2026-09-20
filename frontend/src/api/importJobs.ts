import { ApiError, request } from "./client";
import type {
  DatabaseImportMode,
  ImportJobStartResponse,
  ImportJobStatus,
  ImportJobStatusResponse,
} from "./types";

type ExistingSetImportMode = "skip" | "copy";
type PartImageDownloadMode = "none" | "missing" | "all" | "no_element_id";

type CatalogGapPartKey = {
  part_id: number;
  color_id: number;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const TERMINAL_STATUSES: ReadonlySet<ImportJobStatus> = new Set([
  "completed",
  "failed",
  "cancelled",
]);

const DEFAULT_POLL_MS = 1500;

export function failedSetsCsvDownloadUrl(): string {
  return `${API_BASE}/imports/failed-sets.csv`;
}

export function startImportJob(form: FormData): Promise<ImportJobStartResponse> {
  return request("/imports/jobs", { method: "POST", body: form });
}

export function getImportJob(jobId: string): Promise<ImportJobStatusResponse> {
  return request(`/imports/jobs/${jobId}`);
}

export async function getActiveImportJob(): Promise<ImportJobStatusResponse | null> {
  try {
    return await request<ImportJobStatusResponse>("/imports/jobs/active");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null;
    }
    throw err;
  }
}

export function cancelImportJob(
  jobId: string,
): Promise<ImportJobStatusResponse> {
  return request(`/imports/jobs/${jobId}`, { method: "DELETE" });
}

export function buildSyncJobOptions(options: {
  owned_set_ids?: number[];
  download_set_images?: boolean;
  part_image_download_mode?: PartImageDownloadMode;
  catalog_gap_part_keys?: CatalogGapPartKey[];
}): string {
  return JSON.stringify({
    ...(options.owned_set_ids?.length
      ? { owned_set_ids: options.owned_set_ids }
      : {}),
    download_set_images: options.download_set_images ?? false,
    part_image_download_mode: options.part_image_download_mode ?? "none",
    ...(options.catalog_gap_part_keys?.length
      ? { catalog_gap_part_keys: options.catalog_gap_part_keys }
      : {}),
  });
}

export function startCsvImportJob(
  file: File,
  existingSetMode: ExistingSetImportMode = "skip",
): Promise<ImportJobStartResponse> {
  const form = new FormData();
  form.append("kind", "csv");
  form.append("file", file);
  form.append("existing_set_mode", existingSetMode);
  return startImportJob(form);
}

export function startDatabaseImportJob(
  file: File,
  mode: DatabaseImportMode,
): Promise<ImportJobStartResponse> {
  const form = new FormData();
  form.append("kind", "database");
  form.append("file", file);
  form.append("mode", mode);
  return startImportJob(form);
}

export function startRebrickableSyncJob(options?: {
  owned_set_ids?: number[];
  download_set_images?: boolean;
  part_image_download_mode?: PartImageDownloadMode;
  catalog_gap_part_keys?: CatalogGapPartKey[];
}): Promise<ImportJobStartResponse> {
  const form = new FormData();
  form.append("kind", "rebrickable_sync");
  form.append("sync_options", buildSyncJobOptions(options ?? {}));
  return startImportJob(form);
}

export async function pollImportJobUntilTerminal(
  jobId: string,
  options?: {
    onStatus?: (status: ImportJobStatusResponse) => void;
    signal?: AbortSignal;
    pollIntervalMs?: number;
  },
): Promise<ImportJobStatusResponse> {
  const intervalMs = options?.pollIntervalMs ?? DEFAULT_POLL_MS;

  while (true) {
    if (options?.signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }

    const status = await getImportJob(jobId);
    options?.onStatus?.(status);

    if (TERMINAL_STATUSES.has(status.status)) {
      return status;
    }

    await sleep(intervalMs, options?.signal);
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  const delayMs = ms <= 0 ? 0 : ms;
  if (delayMs === 0) {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException("The operation was aborted.", "AbortError"));
        return;
      }
      const timer = setTimeout(resolve, 0);
      signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          reject(new DOMException("The operation was aborted.", "AbortError"));
        },
        { once: true },
      );
    });
  }
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("The operation was aborted.", "AbortError"));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("The operation was aborted.", "AbortError"));
      },
      { once: true },
    );
  });
}

export function importJobErrorMessage(
  status: ImportJobStatusResponse,
  fallback: string,
): string {
  if (status.status === "cancelled") {
    return "Import cancelled";
  }
  if (status.status === "failed") {
    return status.error ?? fallback;
  }
  return fallback;
}

export { ApiError };
