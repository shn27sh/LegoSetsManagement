import { failedSetsCsvDownloadUrl } from "../api/importJobs";
import type { ImportJobStatusResponse } from "../api/types";

interface ImportJobProgressProps {
  job: ImportJobStatusResponse | null;
  onCancel?: () => void;
  cancelling?: boolean;
}

export function ImportJobProgress({
  job,
  onCancel,
  cancelling = false,
}: ImportJobProgressProps) {
  if (!job || (job.status !== "queued" && job.status !== "running")) {
    return null;
  }

  const { progress } = job;
  const percent =
    progress && progress.total > 0
      ? Math.min(100, Math.round((progress.current / progress.total) * 100))
      : null;

  return (
    <div className="import-job-progress" aria-live="polite">
      <p className="import-job-progress__label">
        {progress?.label ?? "Starting import…"}
        {progress && progress.total > 0 && (
          <>
            {" "}
            ({progress.current} / {progress.total})
          </>
        )}
      </p>
      {percent != null && (
        <div
          className="import-job-progress__bar"
          role="progressbar"
          aria-valuenow={progress?.current ?? 0}
          aria-valuemin={0}
          aria-valuemax={progress?.total ?? 0}
        >
          <div
            className="import-job-progress__bar-fill"
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
      {onCancel && (
        <button
          type="button"
          className="btn btn--secondary import-job-progress__cancel"
          disabled={cancelling}
          onClick={onCancel}
        >
          {cancelling ? "Cancelling…" : "Cancel import"}
        </button>
      )}
    </div>
  );
}

interface FailedSetsDownloadLinkProps {
  failedSetsCsvPath: string | null | undefined;
}

export function FailedSetsDownloadLink({
  failedSetsCsvPath,
}: FailedSetsDownloadLinkProps) {
  if (!failedSetsCsvPath) {
    return null;
  }
  return (
    <p className="import-failed-sets-link">
      <a href={failedSetsCsvDownloadUrl()} download="failedSets.csv">
        Download failed sets (CSV)
      </a>{" "}
      and re-import via CSV import to retry Rebrickable catalog fetch failures.
    </p>
  );
}
