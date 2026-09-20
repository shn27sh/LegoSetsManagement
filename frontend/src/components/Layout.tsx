import { Link, Outlet, useLocation } from "react-router-dom";

import { useAppMode, useCapabilities } from "../appMode/AppModeContext";
import { useImportJobRunner } from "../importJob/ImportJobContext";

const EDIT_MODE_HINT = "Switch to Edit mode in Settings";

const NAV = [
  {
    to: "/",
    label: "Collection",
    match: (path: string) => path === "/" || path.startsWith("/sets"),
    requiresAdd: false,
    requiresImport: false,
  },
  {
    to: "/",
    label: "Add set",
    state: { openAddSet: true } as const,
    match: () => false,
    requiresAdd: true,
    requiresImport: false,
  },
  {
    to: "/search",
    label: "Search",
    match: (path: string) => path.startsWith("/search"),
    requiresAdd: false,
    requiresImport: false,
  },
  {
    to: "/reports",
    label: "Reports",
    match: (path: string) => path.startsWith("/reports"),
    requiresAdd: false,
    requiresImport: false,
  },
  {
    to: "/import",
    label: "Import",
    match: (path: string) => path.startsWith("/import"),
    requiresAdd: false,
    requiresImport: true,
  },
  {
    to: "/settings",
    label: "Settings",
    match: (path: string) => path.startsWith("/settings"),
    requiresAdd: false,
    requiresImport: false,
  },
] as const;

export function Layout() {
  const { pathname } = useLocation();
  const { modeLabel } = useAppMode();
  const { canAddOrDuplicate, canImport } = useCapabilities();
  const { isRunning: importJobRunning } = useImportJobRunner();

  return (
    <div className="layout">
      <header className="layout__header">
        <div className="layout__brand">
          <Link to="/" className="layout__title">
            LEGO Collection Manager
          </Link>
          <p className="layout__tagline">Local-first LEGO collection</p>
        </div>
        <span className="layout__mode-badge" aria-live="polite">
          {modeLabel}
        </span>
        <nav className="layout__nav" aria-label="Main">
          {NAV.map(({ to, label, match, ...rest }) => {
            const disabled =
              (rest.requiresAdd && !canAddOrDuplicate) ||
              (rest.requiresImport && !canImport);
            const className = match(pathname)
              ? "layout__nav-link layout__nav-link--active"
              : "layout__nav-link";

            if (disabled) {
              return (
                <span
                  key={label}
                  className={`${className} layout__nav-link--disabled`}
                  title={EDIT_MODE_HINT}
                  aria-disabled="true"
                >
                  {label}
                </span>
              );
            }

            return (
              <Link
                key={label}
                to={to}
                state={"state" in rest ? rest.state : undefined}
                className={className}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </header>
      {importJobRunning && (
        <p className="layout__import-banner" role="status">
          Background import in progress.{" "}
          <Link to="/import">View progress and cancel</Link>
        </p>
      )}
      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  );
}
