import { useEffect, useState } from "react";

import { Link } from "react-router-dom";

import { getReportsSummary } from "../api/client";
import type { ReportsSummaryResponse } from "../api/types";
import { AsyncMessage } from "../components/AsyncMessage";

const SUMMARY_ITEMS = [
  { key: "total_sets", label: "Set copies in collection" },
  { key: "investigated_sets", label: "Investigated" },
  { key: "complete_sets", label: "Complete" },
  { key: "total_parts", label: "Total parts" },
  { key: "missing_parts", label: "Missing parts" },
] as const satisfies ReadonlyArray<{
  key: keyof ReportsSummaryResponse;
  label: string;
}>;

function formatStatValue(value: number): string {
  return value.toLocaleString();
}

export function ReportsPage() {
  const [summary, setSummary] = useState<ReportsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getReportsSummary();
        if (!cancelled) {
          setSummary(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report");
          setSummary(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="page">
      <header className="page__header">
        <h1>Reports</h1>
        <p className="page__lede">
          Collection-wide overview. Set counts refer to physical copies in your
          collection; a copy is complete when it is investigated and has no
          missing parts.
        </p>
      </header>

      <AsyncMessage error={error} loading={loading} />

      {summary && !loading && (
        <>
          <dl className="report-stats">
            {SUMMARY_ITEMS.map(({ key, label }) => (
              <div key={key} className="report-stats__item">
                <dt className="report-stats__label">{label}</dt>
                <dd className="report-stats__value">
                  {formatStatValue(summary[key])}
                </dd>
              </div>
            ))}
          </dl>

          <section className="report-links" aria-label="Detailed reports">
            <h2>Detailed reports</h2>
            <ul className="report-links__list">
              <li className="report-links__item">
                <Link to="/reports/incomplete" className="report-links__title">
                  Incomplete sets
                </Link>
                <span className="report-links__note">
                  Copies with missing parts
                </span>
              </li>
              <li className="report-links__item">
                <Link to="/reports/missing" className="report-links__title">
                  Missing parts
                </Link>
                <span className="report-links__note">
                  Grouped by part across sets
                </span>
              </li>
              <li className="report-links__item">
                <Link
                  to="/reports/incomplete-catalog"
                  className="report-links__title"
                >
                  Parts missing Element ID or image
                </Link>
                <span className="report-links__note">
                  Re-sync catalog gaps from Rebrickable
                </span>
              </li>
            </ul>
          </section>
        </>
      )}
    </section>
  );
}
