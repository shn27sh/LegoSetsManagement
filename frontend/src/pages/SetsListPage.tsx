import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { listAllFilteredSetCopies, listSetCopyThemeOptions } from "../api/client";
import type { SetCopyListItem } from "../api/types";
import { useCapabilities } from "../appMode/AppModeContext";
import { AsyncMessage } from "../components/AsyncMessage";
import { AddSetWizard } from "../components/AddSetWizard";
import { MakeACopyDialog } from "../components/MakeACopyDialog";
import { MultiSelectDropdown } from "../components/MultiSelectDropdown";
import {
  buildGroupedSections,
  paginateGroupedSections,
  sortSetCopyItems,
  type GroupBy,
  type SetSortBy,
  type SortDir,
} from "../utils/setCopyListProcessing";
import {
  readStoredSetsListPreferences,
  writeStoredSetsListPreferences,
  type InvestigatedFilter,
} from "./setsListPreferencesStorage";
import {
  consumePendingThemeFilterRenames,
  applyThemeFilterRenames,
  initialThemeFilter,
} from "./themeFilterSync";
import { formatSetCopyTitle } from "../utils/setCopyTitle";

const PAGE_SIZE = 20;

function formatMeta(item: SetCopyListItem): string {
  const theme = item.theme_name?.trim() || "Unknown theme";
  const parts = item.num_parts != null ? String(item.num_parts) : "?";
  const age = item.age != null ? String(item.age) : "?";
  return `${theme} · ${parts} parts · Age ${age}`;
}

function pageFromSearch(search: string): number {
  const value = Number(new URLSearchParams(search).get("page") ?? "1");
  return Number.isInteger(value) && value > 0 ? value : 1;
}

function offsetForPage(page: number): number {
  return (page - 1) * PAGE_SIZE;
}

function toggleValue<T extends string>(values: T[], value: T): T[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

export function SetsListPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { canAddOrDuplicate } = useCapabilities();
  const [items, setItems] = useState<SetCopyListItem[]>([]);
  const [themeOptions, setThemeOptions] = useState<string[]>([]);
  const [offset, setOffset] = useState(() =>
    offsetForPage(pageFromSearch(location.search)),
  );
  const [filter, setFilter] = useState<InvestigatedFilter>(
    () => readStoredSetsListPreferences().investigatedFilter,
  );
  const [themeFilter, setThemeFilter] = useState<string[]>(() =>
    initialThemeFilter(readStoredSetsListPreferences().themeFilter),
  );
  const [missingOnly, setMissingOnly] = useState(
    () => readStoredSetsListPreferences().missingOnly,
  );
  const [sortBy, setSortBy] = useState<SetSortBy>(
    () => readStoredSetsListPreferences().sortBy,
  );
  const [sortDir, setSortDir] = useState<SortDir>(
    () => readStoredSetsListPreferences().sortDir,
  );
  const [groupBy, setGroupBy] = useState<GroupBy[]>(
    () => readStoredSetsListPreferences().groupBy,
  );
  const [pageInput, setPageInput] = useState(() =>
    String(pageFromSearch(location.search)),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copyDialogId, setCopyDialogId] = useState<number | null>(null);
  const [addSetOpen, setAddSetOpen] = useState(false);
  const loadGenerationRef = useRef(0);

  const load = useCallback(async () => {
    const generation = ++loadGenerationRef.current;
    setLoading(true);
    setError(null);
    try {
      const investigated =
        filter === "all" ? undefined : filter === "true";
      const data = await listAllFilteredSetCopies({
        investigated,
        themes: themeFilter,
        missing_only: missingOnly,
      });
      if (generation !== loadGenerationRef.current) {
        return;
      }
      setItems(data.items);
    } catch (err) {
      if (generation !== loadGenerationRef.current) {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load sets");
    } finally {
      if (generation === loadGenerationRef.current) {
        setLoading(false);
      }
    }
  }, [filter, missingOnly, themeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    writeStoredSetsListPreferences({
      sortBy,
      sortDir,
      groupBy,
      investigatedFilter: filter,
      themeFilter,
      missingOnly,
    });
  }, [filter, groupBy, missingOnly, sortBy, sortDir, themeFilter]);

  useEffect(() => {
    let ignore = false;
    async function loadThemeOptions() {
      try {
        const data = await listSetCopyThemeOptions();
        if (!ignore) {
          setThemeOptions(Array.isArray(data.themes) ? data.themes : []);
        }
      } catch {
        if (!ignore) {
          setThemeOptions([]);
        }
      }
    }
    void loadThemeOptions();
    return () => {
      ignore = true;
    };
  }, [location.key]);

  useEffect(() => {
    const renames = consumePendingThemeFilterRenames();
    if (renames.length === 0) {
      return;
    }
    setThemeFilter((current) => applyThemeFilterRenames(current, renames));
    setOffset(0);
  }, [location.key]);

  useEffect(() => {
    if (themeOptions.length === 0) {
      return;
    }
    setThemeFilter((current) => {
      const optionSet = new Set(themeOptions);
      const pruned = current.filter((theme) => optionSet.has(theme));
      return pruned.length === current.length ? current : pruned;
    });
  }, [themeOptions]);

  useEffect(() => {
    setOffset(offsetForPage(pageFromSearch(location.search)));
  }, [location.search]);

  useEffect(() => {
    const state = location.state as { openAddSet?: boolean } | null;
    if (state?.openAddSet && canAddOrDuplicate) {
      setAddSetOpen(true);
      navigate(`${location.pathname}${location.search}`, { replace: true, state: {} });
    }
  }, [canAddOrDuplicate, location.pathname, location.search, location.state, navigate]);

  const sortedItems = useMemo(
    () => sortSetCopyItems(items, sortBy, sortDir),
    [items, sortBy, sortDir],
  );
  const groupedItems = useMemo(
    () => buildGroupedSections(items, groupBy, sortBy, sortDir),
    [groupBy, items, sortBy, sortDir],
  );
  const visibleGroupedItems = useMemo(
    () => paginateGroupedSections(groupedItems, offset, PAGE_SIZE),
    [groupedItems, offset],
  );
  const visibleItems = useMemo(
    () => sortedItems.slice(offset, offset + PAGE_SIZE),
    [offset, sortedItems],
  );
  const showPagination = sortedItems.length > PAGE_SIZE;

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(sortedItems.length / PAGE_SIZE));

  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  useEffect(() => {
    if (sortedItems.length === 0) {
      return;
    }
    if (page > totalPages) {
      goToPage(totalPages, { replace: true });
    }
  }, [page, sortedItems.length, totalPages]);

  function goToPage(nextPage: number, options?: { replace?: boolean }) {
    if (!Number.isFinite(nextPage)) {
      return;
    }
    const clampedPage = Math.min(Math.max(nextPage, 1), totalPages);
    setOffset(offsetForPage(clampedPage));
    const search = new URLSearchParams(location.search);
    if (clampedPage === 1) {
      search.delete("page");
    } else {
      search.set("page", String(clampedPage));
    }
    const searchText = search.toString();
    navigate(
      {
        pathname: location.pathname,
        search: searchText ? `?${searchText}` : "",
      },
      { replace: options?.replace ?? false },
    );
  }

  function resetToFirstPage() {
    goToPage(1, { replace: true });
  }
  const themeFilterLabel =
    themeFilter.length === 0
      ? "All"
      : themeFilter.length === 1
        ? themeFilter[0]
        : `${themeFilter.length} themes`;
  const groupByLabel =
    groupBy.length === 0
      ? "None"
      : groupBy.map((group) => (group === "theme" ? "Theme" : "Age")).join(", ");

  function renderSetCard(item: SetCopyListItem) {
    return (
      <li key={item.id} className="set-card">
        <Link to={`/sets/${item.id}`} className="set-card__main">
          {item.image_url ? (
            <img
              src={item.image_url}
              alt=""
              className="set-card__image"
            />
          ) : (
            <div className="set-card__image set-card__image--placeholder" />
          )}
          <div className="set-card__body">
            <h2 className="set-card__title">
              {formatSetCopyTitle(item.set_num, item.name, item.display_label)}
            </h2>
            <p className="set-card__meta">{formatMeta(item)}</p>
            <div className="set-card__badges">
              <span
                className={
                  item.investigated
                    ? "badge badge--ok"
                    : "badge badge--pending"
                }
              >
                {item.investigated ? "Investigated" : "Not investigated"}
              </span>
              {item.missing_count > 0 && (
                <span className="badge badge--warn">
                  {item.missing_count} missing
                </span>
              )}
            </div>
          </div>
        </Link>
        <button
          type="button"
          className="btn btn--secondary set-card__duplicate"
          disabled={!canAddOrDuplicate}
          title={
            canAddOrDuplicate
              ? undefined
              : "Switch to Edit mode in Settings"
          }
          onClick={() => {
            if (canAddOrDuplicate) {
              setCopyDialogId(item.id);
            }
          }}
        >
          Make a copy
        </button>
      </li>
    );
  }

  return (
    <section className="page">
      <header className="page__header">
        <h1>Your sets</h1>
        <p className="page__lede">
          {sortedItems.length} copy{sortedItems.length === 1 ? "" : "ies"} in your
          collection (each LEGO set number may appear multiple times).
        </p>
      </header>

      <div className="toolbar">
        {canAddOrDuplicate && (
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => setAddSetOpen(true)}
        >
          Add set
        </button>
        )}
        <label className="toolbar__field">
          Investigation
          <select
            value={filter}
            onChange={(e) => {
              resetToFirstPage();
              setFilter(e.target.value as InvestigatedFilter);
            }}
          >
            <option value="all">All</option>
            <option value="false">Not investigated</option>
            <option value="true">Investigated</option>
          </select>
        </label>
        <MultiSelectDropdown label="Theme" summary={themeFilterLabel}>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={themeFilter.length === 0}
              onChange={() => {
                resetToFirstPage();
                setThemeFilter([]);
              }}
            />
            All
          </label>
          {themeOptions.map((theme) => (
            <label key={theme} className="checkbox">
              <input
                type="checkbox"
                checked={themeFilter.includes(theme)}
                onChange={() => {
                  resetToFirstPage();
                  setThemeFilter((current) => toggleValue(current, theme));
                }}
              />
              {theme}
            </label>
          ))}
        </MultiSelectDropdown>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={missingOnly}
            onChange={(e) => {
              resetToFirstPage();
              setMissingOnly(e.target.checked);
            }}
          />
          Missing parts only
        </label>
        <label className="toolbar__field">
          Sort by
          <select
            value={sortBy}
            onChange={(e) => {
              resetToFirstPage();
              setSortBy(e.target.value as SetSortBy);
            }}
          >
            <option value="created">Added order</option>
            <option value="set_num">Set number</option>
            <option value="name">Set name</option>
            <option value="theme">Theme</option>
            <option value="num_parts">Number of parts</option>
            <option value="age">Age</option>
          </select>
        </label>
        <label className="toolbar__field">
          Direction
          <select
            value={sortDir}
            onChange={(e) => {
              resetToFirstPage();
              setSortDir(e.target.value as SortDir);
            }}
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </label>
        <MultiSelectDropdown label="Group by" summary={groupByLabel}>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={groupBy.length === 0}
              onChange={() => {
                resetToFirstPage();
                setGroupBy([]);
              }}
            />
            None
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={groupBy.includes("theme")}
              onChange={() => {
                resetToFirstPage();
                setGroupBy((current) => toggleValue(current, "theme"));
              }}
            />
            Theme
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={groupBy.includes("age")}
              onChange={() => {
                resetToFirstPage();
                setGroupBy((current) => toggleValue(current, "age"));
              }}
            />
            Age
          </label>
        </MultiSelectDropdown>
      </div>

      <AsyncMessage error={error} loading={loading && items.length === 0} />

      {!loading && sortedItems.length === 0 && !error && (
        <p className="empty-state">
          Nothing in your collection yet.{" "}
          {canAddOrDuplicate ? (
            <>
              <button
                type="button"
                className="link-button"
                onClick={() => setAddSetOpen(true)}
              >
                Add a set manually
              </button>{" "}
              or <Link to="/import">import a CSV</Link> to get started.
            </>
          ) : (
            <>
              Switch to <Link to="/settings">Edit mode</Link> in Settings to add
              sets or import a CSV.
            </>
          )}
        </p>
      )}

      {groupBy.length > 0 ? (
        <div className="set-categories" aria-label="Sets grouped by selected fields">
          {visibleGroupedItems.map(({ primaryLabel, secondaries }) => (
            <section key={primaryLabel} className="set-category">
              <h2>{primaryLabel}</h2>
              {secondaries.map(({ secondaryLabel, items: bucket }) => (
                <section
                  key={`${primaryLabel}-${secondaryLabel || "items"}`}
                  className="set-category__age"
                >
                  {secondaryLabel && <h3>{secondaryLabel}</h3>}
                  <ul className="set-list">{bucket.map(renderSetCard)}</ul>
                </section>
              ))}
            </section>
          ))}
        </div>
      ) : (
        <ul className="set-list" aria-label="Sets in collection">
          {visibleItems.map(renderSetCard)}
        </ul>
      )}

      {showPagination && (
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
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={offset + PAGE_SIZE >= sortedItems.length || loading}
              onClick={() => goToPage(page + 1)}
            >
              Next
            </button>
          </div>
          {totalPages > 2 && (
            <div className="pagination__goto">
              <button
                type="button"
                className="btn btn--ghost"
                disabled={loading}
                onClick={() => goToPage(Number(pageInput))}
              >
                Go to page #
              </button>
              <input
                type="number"
                value={pageInput}
                disabled={loading}
                aria-label="Page number"
                onChange={(e) => setPageInput(e.target.value)}
              />
            </div>
          )}
        </div>
      )}

      {addSetOpen && canAddOrDuplicate && (
        <AddSetWizard
          onClose={() => setAddSetOpen(false)}
          onCreated={(newId) => {
            setAddSetOpen(false);
            navigate(`/sets/${newId}`);
          }}
        />
      )}

      {copyDialogId != null && canAddOrDuplicate && (
        <MakeACopyDialog
          setCopyId={copyDialogId}
          onClose={() => setCopyDialogId(null)}
          onCreated={(newId) => navigate(`/sets/${newId}`)}
        />
      )}
    </section>
  );
}
