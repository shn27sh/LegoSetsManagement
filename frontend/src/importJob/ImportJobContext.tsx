import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  cancelImportJob,
  getActiveImportJob,
  getImportJob,
  importJobErrorMessage,
  pollImportJobUntilTerminal,
} from "../api/importJobs";
import type { ImportJobStartResponse, ImportJobStatusResponse } from "../api/types";
import {
  clearStoredImportJobId,
  readStoredImportJobId,
  writeStoredImportJobId,
} from "./importJobStorage";

type ImportJobContextValue = {
  job: ImportJobStatusResponse | null;
  isRunning: boolean;
  cancelling: boolean;
  runJob: (
    start: () => Promise<ImportJobStartResponse>,
    fallbackError: string,
  ) => Promise<ImportJobStatusResponse>;
  cancel: () => Promise<void>;
  clearJob: () => void;
};

const ImportJobContext = createContext<ImportJobContextValue | null>(null);

function isInProgress(status: ImportJobStatusResponse["status"]): boolean {
  return status === "queued" || status === "running";
}

export function ImportJobProvider({ children }: { children: ReactNode }) {
  const [job, setJob] = useState<ImportJobStatusResponse | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const pollAbortRef = useRef<AbortController | null>(null);
  const pollingJobIdRef = useRef<string | null>(null);

  const isRunning = job !== null && isInProgress(job.status);

  const stopPolling = useCallback(() => {
    pollAbortRef.current?.abort();
    pollAbortRef.current = null;
    pollingJobIdRef.current = null;
  }, []);

  const clearJob = useCallback(() => {
    stopPolling();
    clearStoredImportJobId();
    setJob(null);
  }, [stopPolling]);

  const followJob = useCallback(
    async (
      jobId: string,
      options?: { throwOnNonCompleted?: boolean; fallbackError?: string },
    ): Promise<ImportJobStatusResponse> => {
      stopPolling();
      pollingJobIdRef.current = jobId;
      writeStoredImportJobId(jobId);

      const controller = new AbortController();
      pollAbortRef.current = controller;

      try {
        const final = await pollImportJobUntilTerminal(jobId, {
          onStatus: setJob,
          signal: controller.signal,
          pollIntervalMs: import.meta.env.MODE === "test" ? 0 : undefined,
        });
        setJob(final);
        if (!isInProgress(final.status)) {
          clearStoredImportJobId();
        }
        if (
          options?.throwOnNonCompleted &&
          final.status !== "completed"
        ) {
          throw new ApiError(
            importJobErrorMessage(final, options.fallbackError ?? "Import failed"),
            final.status === "cancelled" ? 499 : 500,
          );
        }
        return final;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          throw new ApiError("Import cancelled", 499);
        }
        throw err;
      } finally {
        if (pollingJobIdRef.current === jobId) {
          pollingJobIdRef.current = null;
        }
        if (pollAbortRef.current === controller) {
          pollAbortRef.current = null;
        }
      }
    },
    [stopPolling],
  );

  const resumeJob = useCallback(
    async (jobId: string) => {
      try {
        const status = await getImportJob(jobId);
        if (
          !status.job_id ||
          !["csv", "rebrickable_sync", "database"].includes(status.kind)
        ) {
          clearStoredImportJobId();
          return;
        }
        setJob(status);
        if (isInProgress(status.status)) {
          void followJob(jobId).catch(() => {
            /* errors surface via job.status on next poll tick */
          });
        } else {
          clearStoredImportJobId();
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          clearStoredImportJobId();
          return;
        }
        throw err;
      }
    },
    [followJob],
  );

  useEffect(() => {
    if (import.meta.env.MODE === "test") {
      return;
    }

    let cancelled = false;

    async function resumeOnLoad() {
      try {
        const active = await getActiveImportJob();
        if (cancelled) {
          return;
        }
        if (active?.job_id && active.status) {
          setJob(active);
          if (isInProgress(active.status)) {
            void followJob(active.job_id).catch(() => undefined);
          } else {
            clearStoredImportJobId();
          }
          return;
        }

        const storedId = readStoredImportJobId();
        if (!storedId) {
          return;
        }
        await resumeJob(storedId);
      } catch {
        clearStoredImportJobId();
      }
    }

    void resumeOnLoad();

    return () => {
      cancelled = true;
    };
  }, [followJob, resumeJob]);

  const runJob = useCallback(
    async (
      start: () => Promise<ImportJobStartResponse>,
      fallbackError: string,
    ): Promise<ImportJobStatusResponse> => {
      stopPolling();
      setJob(null);
      const { job_id } = await start();
      return followJob(job_id, {
        throwOnNonCompleted: true,
        fallbackError,
      });
    },
    [followJob, stopPolling],
  );

  const cancel = useCallback(async () => {
    const jobId = job?.job_id;
    if (!jobId) {
      return;
    }
    setCancelling(true);
    stopPolling();
    try {
      const updated = await cancelImportJob(jobId);
      setJob(updated);
      if (!isInProgress(updated.status)) {
        clearStoredImportJobId();
      }
    } finally {
      setCancelling(false);
    }
  }, [job?.job_id, stopPolling]);

  return (
    <ImportJobContext.Provider
      value={{ job, isRunning, cancelling, runJob, cancel, clearJob }}
    >
      {children}
    </ImportJobContext.Provider>
  );
}

export function useImportJobRunner(): ImportJobContextValue {
  const value = useContext(ImportJobContext);
  if (value === null) {
    throw new Error("useImportJobRunner must be used within ImportJobProvider");
  }
  return value;
}
