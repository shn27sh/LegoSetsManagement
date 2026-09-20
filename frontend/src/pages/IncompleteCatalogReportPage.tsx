import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getIncompleteCatalogReport, mediaUrl } from "../api/client";
import { startRebrickableSyncJob } from "../api/importJobs";
import type {
  IncompleteCatalogReportItem,
  RebrickableSyncResponse,
} from "../api/types";
import { AsyncMessage } from "../components/AsyncMessage";
import { ImportJobProgress } from "../components/ImportJobProgress";
import { useImportJobRunner } from "../hooks/useImportJobRunner";

const PAGE_SIZE = 50;

function formatElementIds(elementIds: string[]): string {
  return elementIds.length > 0 ? elementIds.join(", ") : "No Element ID";
}

function rowKey(item: IncompleteCatalogReportItem): string {
  return `${item.part_id}-${item.color_id}`;
}

function partColorFromKey(key: string): { part_id: number; color_id: number } | null {
  const separator = key.indexOf("-");
  if (separator <= 0) {
    return null;
  }
  const partId = Number.parseInt(key.slice(0, separator), 10);
  const colorId = Number.parseInt(key.slice(separator + 1), 10);
  if (!Number.isInteger(partId) || !Number.isInteger(colorId)) {
    return null;
  }
  return { part_id: partId, color_id: colorId };
}

export function IncompleteCatalogReportPage() {
  const [items, setItems] = useState<IncompleteCatalogReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set());
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<RebrickableSyncResponse | null>(
    null,
  );
  const [syncError, setSyncError] = useState<string | null>(null);
  const {
    job: syncJob,
    isRunning: syncJobRunning,
    cancelling: syncCancelling,
    runJob: runSyncJob,
    cancel: cancelSyncJob,
  } = useImportJobRunner();

  const load = useCallback(async (nextOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIncompleteCatalogReport({
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      setItems(data.items);
      setTotal(data.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageKeys = items.map(rowKey);
  const allPageSelected =
    pageKeys.length > 0 && pageKeys.every((key) => selectedKeys.has(key));

  function goToPage(nextPage: number) {
    void load((nextPage - 1) * PAGE_SIZE);
  }

  function toggleSelected(key: string, checked: boolean) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(key);
      } else {
        next.delete(key);
      }
      return next;
    });
  }

  function toggleSelectAllOnPage(checked: boolean) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      for (const key of pageKeys) {
        if (checked) {
          next.add(key);
        } else {
          next.delete(key);
        }
      }
      return next;
    });
  }

  const selectedCount = selectedKeys.size;

  async function onResyncSelected() {
    if (selectedKeys.size === 0) {
      return;
    }
    const catalogGapPartKeys = [...selectedKeys]
      .map(partColorFromKey)
      .filter((key): key is { part_id: number; color_id: number } => key !== null);
    if (catalogGapPartKeys.length === 0) {
      return;
    }
    setSyncing(true);
    setSyncError(null);
    setSyncResult(null);
    try {
      const final = await runSyncJob(
        () =>
          startRebrickableSyncJob({
            part_image_download_mode: "no_element_id",
            catalog_gap_part_keys: catalogGapPartKeys,
          }),
        "Re-sync failed",
      );
      setSyncResult(final.result as RebrickableSyncResponse);
      setSelectedKeys(new Set());
      await load(offset);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Re-sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <section className="page">
      <header className="page__header">
        <p className="page__breadcrumb">
          <Link to="/reports">Reports</Link>
        </p>
        <h1>Parts missing Element ID or image</h1>
        <p className="page__lede">
          Catalog inventory lines with no persisted Element ID and/or no local
          display image, grouped by part and color. Re-sync selected rows from
          Rebrickable to backfill Element IDs and download images for lines that
          lacked an Element ID before sync. Updates propagate to the same part
          and color across all sets in your collection.
        </p>
      </header>

      <ImportJobProgress
        job={syncJob}
        onCancel={syncJobRunning ? () => void cancelSyncJob() : undefined}
        cancelling={syncCancelling}
      />

      <div className="report-toolbar">
        <button
          type="button"
          className="btn btn--secondary"
          disabled={
            loading || syncing || syncJobRunning || selectedCount === 0
          }
          onClick={() => void onResyncSelected()}
        >
          {syncing || syncJobRunning
            ? "Re-syncing…"
            : `Re-sync selected (${selectedCount})`}
        </button>
      </div>

      <AsyncMessage
        error={error ?? syncError}
        loading={loading && items.length === 0}
      />

      {syncResult && (
        <div className="import-result" role="status">
          <p>
            Synced <strong>{syncResult.sets_synced}</strong> set
            {syncResult.sets_synced === 1 ? "" : "s"};{" "}
            {syncResult.part_images_downloaded} part image
            {syncResult.part_images_downloaded === 1 ? "" : "s"} downloaded.
          </p>
          {syncResult.sets_synced === 0 && (
            <p>No sets required catalog-gap sync for the current selection.</p>
          )}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <p className="empty-state">No catalog gaps to report.</p>
      )}

      {items.length > 0 && (
        <div className="table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th scope="col">
                  <input
                    type="checkbox"
                    aria-label="Select all on this page"
                    checked={allPageSelected}
                    onChange={(e) => toggleSelectAllOnPage(e.target.checked)}
                  />
                </th>
                <th scope="col">Image</th>
                <th scope="col">Part</th>
                <th scope="col">Color</th>
                <th scope="col">Element ID</th>
                <th scope="col">Gaps</th>
                <th scope="col">Sets</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const key = rowKey(item);
                const gaps = [
                  item.missing_element_id ? "Element ID" : null,
                  item.missing_image ? "Image" : null,
                ].filter(Boolean);
                return (
                  <tr key={key}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${item.part_num}`}
                        checked={selectedKeys.has(key)}
                        onChange={(e) => toggleSelected(key, e.target.checked)}
                      />
                    </td>
                    <td>
                      {item.part_image_url ? (
                        <img
                          className="inventory-table__thumb"
                          src={mediaUrl(item.part_image_url) ?? undefined}
                          alt=""
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <span className="inventory-table__part-num">
                        {item.part_num}
                      </span>
                      {item.part_name && (
                        <>
                          {" - "}
                          <span className="inventory-table__part-name">
                            {item.part_name}
                          </span>
                        </>
                      )}
                    </td>
                    <td>{item.color_name ?? item.color_id}</td>
                    <td>{formatElementIds(item.element_ids)}</td>
                    <td>{gaps.join(", ")}</td>
                    <td>
                      <ul className="missing-parts-sets">
                        {item.sets.map((setRow) => (
                          <li key={setRow.owned_set_id}>
                            <Link to={`/sets/${setRow.owned_set_id}`}>
                              {setRow.set_num}
                              {setRow.set_name ? ` — ${setRow.set_name}` : ""}
                              {setRow.display_label
                                ? ` (${setRow.display_label})`
                                : ""}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE_SIZE && (
        <nav className="pagination" aria-label="Report pages">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={page <= 1 || loading}
            onClick={() => goToPage(page - 1)}
          >
            Previous
          </button>
          <span>
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={page >= pageCount || loading}
            onClick={() => goToPage(page + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </section>
  );
}
