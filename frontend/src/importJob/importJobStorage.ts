export const ACTIVE_IMPORT_JOB_STORAGE_KEY = "lcm-active-import-job-id";

export function readStoredImportJobId(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_IMPORT_JOB_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredImportJobId(jobId: string): void {
  try {
    sessionStorage.setItem(ACTIVE_IMPORT_JOB_STORAGE_KEY, jobId);
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearStoredImportJobId(): void {
  try {
    sessionStorage.removeItem(ACTIVE_IMPORT_JOB_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
