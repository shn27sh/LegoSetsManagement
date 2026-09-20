import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getMissingPartsReport, fetchAllMissingPartsReport, mediaUrl } from "../api/client";
import type { MissingPartReportItem } from "../api/types";
import { AsyncMessage } from "../components/AsyncMessage";
import { formatSetCopyTitle } from "../utils/setCopyTitle";
import { downloadMissingPartsPdf } from "../utils/missingPartsReportPdf";

const PAGE_SIZE = 50;

function parseOwnedSetIds(searchParams: URLSearchParams): number[] {
  return searchParams
    .getAll("owned_set_ids")
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function formatElementIds(elementIds: string[]): string {
  return elementIds.length > 0 ? elementIds.join(", ") : "No Element ID";
}

export function MissingPartsReportPage() {
  const [searchParams] = useSearchParams();
  const ownedSetIds = useMemo(
    () => parseOwnedSetIds(searchParams),
    [searchParams],
  );
  const filtered = ownedSetIds.length > 0;

  const [items, setItems] = useState<MissingPartReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(
    async (nextOffset: number) => {
      setLoading(true);
      setError(null);
      try {
        const data = await getMissingPartsReport({
          owned_set_ids: filtered ? ownedSetIds : undefined,
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
    },
    [filtered, ownedSetIds],
  );

  useEffect(() => {
    void load(0);
  }, [load]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function goToPage(nextPage: number) {
    void load((nextPage - 1) * PAGE_SIZE);
  }

  const filterLabel = filtered
    ? `Showing ${ownedSetIds.length} selected set ${ownedSetIds.length === 1 ? "copy" : "copies"}.`
    : "Showing all incomplete sets.";

  async function onExportPdf() {
    setExporting(true);
    setExportError(null);
    try {
      const allItems = await fetchAllMissingPartsReport({
        owned_set_ids: filtered ? ownedSetIds : undefined,
      });
      if (allItems.length === 0) {
        setExportError("No missing parts to export.");
        return;
      }
      await downloadMissingPartsPdf(allItems, { filterLabel });
    } catch (err) {
      setExportError(
        err instanceof Error ? err.message : "Could not export PDF",
      );
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="page">
      <header className="page__header">
        <p className="page__breadcrumb">
          <Link to="/reports">Reports</Link>
          {" · "}
          <Link to="/reports/incomplete">Incomplete sets</Link>
        </p>
        <h1>Missing parts</h1>
        <p className="page__lede">
          All missing parts grouped by part and color, with the total quantity
          needed and which set copies require each part.
        </p>
      </header>

      <p className="report-filter-banner" role="status">
        {filterLabel}
      </p>

      <div className="report-toolbar">
        <button
          type="button"
          className="btn btn--secondary"
          disabled={loading || exporting || total === 0}
          onClick={() => void onExportPdf()}
        >
          {exporting ? "Exporting…" : "Export PDF"}
        </button>
      </div>

      <AsyncMessage error={error ?? exportError} loading={loading && items.length === 0} />

      {!loading && items.length === 0 && !error && (
        <p className="empty-state">No missing parts to report.</p>
      )}

      {items.length > 0 && (
        <div className="table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th scope="col">Image</th>
                <th scope="col">Part</th>
                <th scope="col">Color</th>
                <th scope="col">Element ID</th>
                <th scope="col">Needed</th>
                <th scope="col">Sets</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`${item.part_id}-${item.color_id}`}>
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
                    <span className="inventory-table__part-num">{item.part_num}</span>
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
                  <td>{item.quantity_missing_total}</td>
                  <td>
                    <ul className="missing-parts-sets">
                      {item.needed_sets.map((setRow) => (
                        <li key={setRow.owned_set_id}>
                          <Link to={`/sets/${setRow.owned_set_id}`}>
                            {formatSetCopyTitle(
                              setRow.set_num,
                              setRow.set_name,
                              setRow.display_label,
                            )}
                          </Link>
                          {setRow.quantity_missing > 1 && (
                            <span className="missing-parts-sets__qty">
                              {" "}
                              ×{setRow.quantity_missing}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="pagination">
          <div className="pagination__main">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={offset === 0 || loading}
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
              disabled={offset + PAGE_SIZE >= total || loading}
              onClick={() => goToPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
