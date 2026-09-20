import { FormEvent, Fragment, useState } from "react";
import { Link } from "react-router-dom";

import { mediaUrl, searchCatalog } from "../api/client";
import type { SearchResponse } from "../api/types";
import { AsyncMessage } from "../components/AsyncMessage";

type SearchType = "set" | "part" | "element";

function formatElementIds(elementIds: string[]): string {
  return elementIds.length > 0 ? elementIds.join(", ") : "No Element ID";
}

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState<SearchType>("set");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a search term");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await searchCatalog({ q: trimmed, type: searchType });
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page">
      <header className="page__header">
        <h1>Search</h1>
        <p className="page__lede">
          Find LEGO sets, part numbers, or Element IDs that appear in your
          collection.
        </p>
      </header>

      <form className="search-form" onSubmit={(e) => void onSubmit(e)}>
        <input
          type="search"
          value={query}
          placeholder="Set number, part number, or Element ID…"
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search query"
        />
        <select
          value={searchType}
          onChange={(e) => setSearchType(e.target.value as SearchType)}
          aria-label="Search type"
        >
          <option value="set">Set</option>
          <option value="part">Part number</option>
          <option value="element">Element ID</option>
        </select>
        <button type="submit" className="btn btn--primary" disabled={loading}>
          Search
        </button>
      </form>

      <AsyncMessage error={error} loading={loading} />

      {results && !loading && (
        <div className="search-results">
          {searchType === "set" && (
            <section>
              <h2>Sets ({results.sets.length})</h2>
              {results.sets.length === 0 ? (
                <p className="empty-hint">No matching sets.</p>
              ) : (
                <ul className="result-list">
                  {results.sets.map((row) => (
                    <li key={row.owned_set_id}>
                      <Link to={`/sets/${row.owned_set_id}`}>
                        <strong>{row.set_num}</strong>
                        {row.name ? ` — ${row.name}` : ""}
                        <span className="result-list__meta">
                          {row.label ?? "Unlabeled copy"} ·{" "}
                          {row.investigated ? "investigated" : "not investigated"}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {searchType === "part" && (
            <section>
              <h2>Part Numbers ({results.parts.length})</h2>
              {results.parts.length === 0 ? (
                <p className="empty-hint">No matching parts in owned inventories.</p>
              ) : (
                <ul className="result-list result-list--parts">
                  {results.parts.map((part) => (
                    <li key={part.part_num} className="result-list__part-hit">
                      {part.image_url && (
                        <img
                          src={mediaUrl(part.image_url) ?? undefined}
                          alt=""
                          className="result-list__thumb"
                        />
                      )}
                      <div className="result-list__part-body">
                        {part.name && (
                          <p className="result-list__part-name">{part.name}</p>
                        )}
                        <ul className="result-list__part-lines">
                          {part.lines.map((line) => (
                            <li key={line.display_part_num}>
                              <strong>{line.display_part_num}</strong>
                              <span className="result-list__part-dash"> - </span>
                              {line.sets.length === 0 ? (
                                <span className="empty-hint">No sets in collection</span>
                              ) : (
                                line.sets.map((occ, i) => (
                                  <Fragment key={`${line.display_part_num}-${occ.owned_set_id}-${occ.set_num}`}>
                                    {i > 0 ? ", " : null}
                                    <Link to={`/sets/${occ.owned_set_id}`}>
                                      {occ.set_num}
                                    </Link>
                                    <span>
                                      {" "}
                                      ({occ.quantity}
                                      {occ.colors.length > 0
                                        ? `; ${occ.colors
                                            .map(
                                              (color) =>
                                                `${color.color_name} x${color.quantity}`,
                                            )
                                            .join(", ")}`
                                        : ""}
                                      )
                                    </span>
                                  </Fragment>
                                ))
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {searchType === "element" && (
            <section>
              <h2>Element IDs ({results.elements.length})</h2>
              {results.elements.length === 0 ? (
                <p className="empty-hint">No matching Element IDs in owned inventories.</p>
              ) : (
                <ul className="result-list result-list--parts">
                  {results.elements.map((element) => (
                    <li
                      key={`${element.part_num}-${element.color_id}-${element.element_ids.join("-")}`}
                      className="result-list__part-hit"
                    >
                      <div className="result-list__part-body">
                        <p className="result-list__part-name">
                          <strong>{formatElementIds(element.element_ids)}</strong>
                          {" — "}
                          {element.part_num}
                          {element.part_name ? `, ${element.part_name}` : ""}
                          {` (${element.color_name})`}
                        </p>
                        {element.sets.length === 0 ? (
                          <span className="empty-hint">No sets in collection</span>
                        ) : (
                          element.sets.map((occ, i) => (
                            <Fragment key={`${element.part_num}-${occ.owned_set_id}-${occ.set_num}`}>
                              {i > 0 ? ", " : null}
                              <Link to={`/sets/${occ.owned_set_id}`}>
                                {occ.set_num}
                              </Link>
                              <span> ({occ.quantity})</span>
                            </Fragment>
                          ))
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      )}
    </section>
  );
}
