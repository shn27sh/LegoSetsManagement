import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  startCsvImportJob,
  startDatabaseImportJob,
  startRebrickableSyncJob,
} from "../api/importJobs";
import { updateLocalMetadata } from "../api/client";
import type {
  CsvImportResponse,
  DatabaseImportMode,
  DatabaseImportResponse,
  LocalMetadataUpdateResponse,
  RebrickableSyncResponse,
} from "../api/types";
import { AsyncMessage } from "../components/AsyncMessage";
import {
  FailedSetsDownloadLink,
  ImportJobProgress,
} from "../components/ImportJobProgress";
import { useCapabilities } from "../appMode/AppModeContext";
import { useImportJobRunner } from "../hooks/useImportJobRunner";

type PartImageDownloadMode = "none" | "missing" | "all";

export function ImportPage() {
  const { canImport } = useCapabilities();
  const fileRef = useRef<HTMLInputElement>(null);
  const databaseFileRef = useRef<HTMLInputElement>(null);
  const [csvResult, setCsvResult] = useState<CsvImportResponse | null>(null);
  const [databaseResult, setDatabaseResult] =
    useState<DatabaseImportResponse | null>(null);
  const [databaseImportMode, setDatabaseImportMode] =
    useState<DatabaseImportMode>("add_only_new");
  const [syncResult, setSyncResult] = useState<RebrickableSyncResponse | null>(null);
  const [metadataResult, setMetadataResult] =
    useState<LocalMetadataUpdateResponse | null>(null);
  const [loading, setLoading] = useState<
    "csv" | "database" | "sync" | "metadata" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadSetImages, setDownloadSetImages] = useState(false);
  const [partImageDownloadMode, setPartImageDownloadMode] =
    useState<PartImageDownloadMode>("none");

  const { job, isRunning, cancelling, runJob, cancel } = useImportJobRunner();

  useEffect(() => {
    if (!job || job.status !== "completed" || !job.result) {
      return;
    }
    if (job.kind === "csv" && !csvResult) {
      setCsvResult(job.result as CsvImportResponse);
    } else if (job.kind === "database" && !databaseResult) {
      setDatabaseResult(job.result as DatabaseImportResponse);
    } else if (job.kind === "rebrickable_sync" && !syncResult) {
      setSyncResult(job.result as RebrickableSyncResponse);
    }
  }, [job, csvResult, databaseResult, syncResult]);

  function onCsvSubmit(event: FormEvent) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a CSV or text file first");
      return;
    }
    setLoading("csv");
    setError(null);
    setCsvResult(null);
    void runJob(() => startCsvImportJob(file, "skip"), "CSV import failed")
      .then((final) => {
        setCsvResult(final.result as CsvImportResponse);
        if (fileRef.current) {
          fileRef.current.value = "";
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Import failed");
      })
      .finally(() => {
        setLoading(null);
      });
  }

  function onSync() {
    setLoading("sync");
    setError(null);
    setSyncResult(null);
    void runJob(
      () =>
        startRebrickableSyncJob({
          download_set_images: downloadSetImages,
          part_image_download_mode: partImageDownloadMode,
        }),
      "Sync failed",
    )
      .then((final) => {
        setSyncResult(final.result as RebrickableSyncResponse);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Sync failed");
      })
      .finally(() => {
        setLoading(null);
      });
  }

  function onDatabaseSubmit(event: FormEvent) {
    event.preventDefault();
    const file = databaseFileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a database file first");
      return;
    }
    setLoading("database");
    setError(null);
    setDatabaseResult(null);
    void runJob(
      () => startDatabaseImportJob(file, databaseImportMode),
      "Database import failed",
    )
      .then((final) => {
        setDatabaseResult(final.result as DatabaseImportResponse);
        if (databaseFileRef.current) {
          databaseFileRef.current.value = "";
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Database import failed");
      })
      .finally(() => {
        setLoading(null);
      });
  }

  async function onLocalMetadataUpdate() {
    setLoading("metadata");
    setError(null);
    setMetadataResult(null);
    try {
      setMetadataResult(await updateLocalMetadata());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Metadata update failed");
    } finally {
      setLoading(null);
    }
  }

  const importBusy = isRunning || loading !== null;
  const failedSetsCsvPath = job?.failed_sets_csv_path;

  return (
    <section className="page">
      <header className="page__header">
        <h1>Import</h1>
        <p className="page__lede">
          Add LEGO sets from a comma-separated list or{" "}
          <Link to="/" state={{ openAddSet: true }}>
            add one set manually
          </Link>
          . CSV import fetches catalog, inventory, and images from Rebrickable.
        </p>
      </header>

      <AsyncMessage
        error={error}
        loading={
          (loading === "metadata") ||
          (loading === "sync" && !syncResult && !isRunning)
        }
      />

      <ImportJobProgress
        job={job}
        onCancel={isRunning ? () => void cancel() : undefined}
        cancelling={cancelling}
      />

      {!canImport ? (
        <article className="import-card">
          <p>
            CSV import, Rebrickable sync, and local metadata updates require{" "}
            <strong>Edit mode</strong>. Switch mode in{" "}
            <Link to="/settings">Settings</Link>.
          </p>
        </article>
      ) : (
        <>
      <article className="import-card">
        <h2>CSV import</h2>
        <p>
          Upload a plain text file with comma-separated LEGO set numbers (no
          header). Each new set number creates a <strong>new physical copy</strong>{" "}
          in your collection and loads set metadata and parts from Rebrickable when
          the API key is configured. Set numbers that already exist in your
          collection are skipped. Set, minifigure, and part images are downloaded
          from Rebrickable when available. Recommended{" "}
          <strong>age</strong> is often missing from Rebrickable — use the local
          metadata update below or set it on the set detail page. To add another
          copy of a set you already own, use <strong>Make a copy</strong> on the
          collection list.
        </p>
        <form onSubmit={(e) => void onCsvSubmit(e)}>
          <input ref={fileRef} type="file" accept=".csv,.txt,text/plain" />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={importBusy}
          >
            {loading === "csv" ? "Importing…" : "Import CSV"}
          </button>
        </form>
        {csvResult && (
          <div className="import-result" role="status">
            <p>
              Created <strong>{csvResult.instances_created}</strong> instance
              {csvResult.instances_created === 1 ? "" : "s"}; fetched{" "}
              <strong>{csvResult.sets_fetched}</strong> from Rebrickable
              {csvResult.catalog_stubs_created > 0 && (
                <>
                  {" "}
                  ({csvResult.catalog_stubs_created} catalog stub
                  {csvResult.catalog_stubs_created === 1 ? "" : "s"} when fetch
                  failed)
                </>
              )}
              .
              {csvResult.set_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {csvResult.set_images_downloaded} set image
                  {csvResult.set_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
              {csvResult.minifig_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {csvResult.minifig_images_downloaded} minifigure image
                  {csvResult.minifig_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
              {csvResult.part_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {csvResult.part_images_downloaded} part image
                  {csvResult.part_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
            </p>
            {(csvResult.image_downloads_failed?.length ?? 0) > 0 && (
              <ul className="import-errors">
                {csvResult.image_downloads_failed?.map((fail) => (
                  <li key={`${fail.target}-${fail.url}`}>
                    {fail.target}: {fail.message}
                  </li>
                ))}
              </ul>
            )}
            {csvResult.skipped_existing_sets.length > 0 && (
              <div className="import-skipped">
                <p>
                  The following set
                  {csvResult.skipped_existing_sets.length === 1 ? "" : "s"} were
                  not imported because{" "}
                  {csvResult.skipped_existing_sets.length === 1 ? "it" : "they"}{" "}
                  already exist in your collection:
                </p>
                <ul className="import-errors">
                  {csvResult.skipped_existing_sets.map((skipped) => (
                    <li key={`${skipped.token_index}-${skipped.set_num}`}>
                      Token {skipped.token_index} ({skipped.set_num})
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {csvResult.sets_failed.length > 0 && (
              <ul className="import-errors">
                {csvResult.sets_failed.map((fail) => (
                  <li key={`${fail.token_index}-${fail.set_num}`}>
                    Token {fail.token_index} ({fail.set_num}): {fail.message}
                  </li>
                ))}
              </ul>
            )}
            {csvResult.errors.length > 0 && (
              <ul className="import-errors">
                {csvResult.errors.map((err) => (
                  <li key={err.token_index}>
                    Token {err.token_index}: {err.message}
                  </li>
                ))}
              </ul>
            )}
            <FailedSetsDownloadLink failedSetsCsvPath={failedSetsCsvPath} />
            <Link to="/">View collection</Link>
          </div>
        )}
      </article>

      <article className="import-card import-card--secondary">
        <h2>Import from another database</h2>
        <p>
          Upload a SQLite <code>.db</code> file from another LEGO Collection
          Manager install. Sets are matched by catalog set number and variant.
        </p>
        <fieldset className="sync-panel__radio-group">
          <legend>Import mode</legend>
          <label className="checkbox">
            <input
              type="radio"
              name="database-import-mode"
              value="add_only_new"
              checked={databaseImportMode === "add_only_new"}
              disabled={importBusy}
              onChange={() => setDatabaseImportMode("add_only_new")}
            />
            Add only new sets (skip sets already in this database)
          </label>
          <label className="checkbox">
            <input
              type="radio"
              name="database-import-mode"
              value="add_and_update"
              checked={databaseImportMode === "add_and_update"}
              disabled={importBusy}
              onChange={() => setDatabaseImportMode("add_and_update")}
            />
            Add new sets and update existing (refresh catalog, images, and
            inventory; preserve age, theme, copy labels, and missing quantities)
          </label>
        </fieldset>
        <form onSubmit={(e) => void onDatabaseSubmit(e)}>
          <input
            ref={databaseFileRef}
            type="file"
            accept=".db,application/octet-stream"
          />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={importBusy}
          >
            {loading === "database" ? "Importing…" : "Import database"}
          </button>
        </form>
        {databaseResult && (
          <div className="import-result" role="status">
            <p>
              Added <strong>{databaseResult.sets_added}</strong> set
              {databaseResult.sets_added === 1 ? "" : "s"}
              {databaseResult.sets_updated > 0 && (
                <>
                  ; updated <strong>{databaseResult.sets_updated}</strong>
                </>
              )}
              {databaseResult.sets_skipped > 0 && (
                <>
                  ; skipped <strong>{databaseResult.sets_skipped}</strong>{" "}
                  existing set
                  {databaseResult.sets_skipped === 1 ? "" : "s"}
                </>
              )}
              . Created <strong>{databaseResult.instances_created}</strong>{" "}
              instance
              {databaseResult.instances_created === 1 ? "" : "s"};{" "}
              {databaseResult.parts_upserted} parts;{" "}
              {databaseResult.inventory_lines_written} inventory lines.
            </p>
            {databaseResult.skipped_set_nums.length > 0 && (
              <ul className="import-errors">
                {databaseResult.skipped_set_nums.map((setNum) => (
                  <li key={setNum}>{setNum}</li>
                ))}
              </ul>
            )}
            <Link to="/">View collection</Link>
          </div>
        )}
      </article>

      <article className="import-card import-card--secondary">
        <h2>Rebrickable sync (optional)</h2>
        <p>
          Re-fetch catalog data for sets you already own. Useful after manual
          edits or if a CSV token failed. Requires{" "}
          <code>REBRICKABLE_API_KEY</code> on the server. Runs in the background
          so you can browse the collection while sync progresses.
        </p>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={downloadSetImages}
            disabled={importBusy}
            onChange={(e) => setDownloadSetImages(e.target.checked)}
          />
          Download set images into the local database
        </label>
        <fieldset className="sync-panel__radio-group">
          <legend>Part image downloads</legend>
          <label className="checkbox">
            <input
              type="radio"
              name="part-image-download-mode"
              value="none"
              checked={partImageDownloadMode === "none"}
              disabled={importBusy}
              onChange={() => setPartImageDownloadMode("none")}
            />
            Do not download images for parts
          </label>
          <label className="checkbox">
            <input
              type="radio"
              name="part-image-download-mode"
              value="missing"
              checked={partImageDownloadMode === "missing"}
              disabled={importBusy}
              onChange={() => setPartImageDownloadMode("missing")}
            />
            Download part images only for missing parts
          </label>
          <label className="checkbox">
            <input
              type="radio"
              name="part-image-download-mode"
              value="all"
              checked={partImageDownloadMode === "all"}
              disabled={importBusy}
              onChange={() => setPartImageDownloadMode("all")}
            />
            Download part images for all sets
          </label>
        </fieldset>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={importBusy}
          onClick={() => void onSync()}
        >
          {loading === "sync" ? "Syncing…" : "Sync entire collection"}
        </button>
        {syncResult && (
          <div className="import-result" role="status">
            <p>
              Synced <strong>{syncResult.sets_synced}</strong> set
              {syncResult.sets_synced === 1 ? "" : "s"};{" "}
              {syncResult.inventory_lines_written} inventory lines;{" "}
              {syncResult.parts_upserted} parts upserted.
              {syncResult.set_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {syncResult.set_images_downloaded} set image
                  {syncResult.set_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
              {syncResult.minifig_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {syncResult.minifig_images_downloaded} minifigure image
                  {syncResult.minifig_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
              {syncResult.part_images_downloaded > 0 && (
                <>
                  {" "}
                  Downloaded {syncResult.part_images_downloaded} part image
                  {syncResult.part_images_downloaded === 1 ? "" : "s"}.
                </>
              )}
            </p>
            {syncResult.sets_failed.length > 0 && (
              <ul className="import-errors">
                {syncResult.sets_failed.map((fail) => (
                  <li key={fail.set_num}>
                    {fail.set_num}: {fail.message}
                  </li>
                ))}
              </ul>
            )}
            {syncResult.image_downloads_failed.length > 0 && (
              <ul className="import-errors">
                {syncResult.image_downloads_failed.map((fail) => (
                  <li key={`${fail.target}-${fail.url}`}>
                    {fail.target}: {fail.message}
                  </li>
                ))}
              </ul>
            )}
            <FailedSetsDownloadLink failedSetsCsvPath={failedSetsCsvPath} />
          </div>
        )}
      </article>

      <article className="import-card import-card--secondary">
        <h2>Local metadata update</h2>
        <p>
          Fill missing ages and unknown themes from local CSV files. Ages come
          from <code>data/age.csv</code> and are stored as numbers without{" "}
          <code>+</code>. Themes use <code>data/sets.csv</code> and{" "}
          <code>data/themes.csv</code>, resolving subthemes to parent themes.
          Existing age and theme values are preserved.
        </p>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={importBusy}
          onClick={() => void onLocalMetadataUpdate()}
        >
          {loading === "metadata" ? "Updating…" : "Update missing ages and themes"}
        </button>
        {metadataResult && (
          <div className="import-result" role="status">
            <p>
              Updated <strong>{metadataResult.owned_set_ages_updated}</strong>{" "}
              age value
              {metadataResult.owned_set_ages_updated === 1 ? "" : "s"} and{" "}
              <strong>{metadataResult.catalog_themes_updated}</strong> theme
              {metadataResult.catalog_themes_updated === 1 ? "" : "s"}.
            </p>
          </div>
        )}
      </article>
        </>
      )}
    </section>
  );
}
