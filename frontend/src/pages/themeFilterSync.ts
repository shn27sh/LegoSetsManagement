import type { CatalogThemeScope } from "../api/types";

export type ThemeFilterRename = {
  from: string;
  to: string;
  scope: CatalogThemeScope;
};

const PENDING_THEME_FILTER_SYNC_KEY = "lcm.pendingThemeFilterSync";

export function queueThemeFilterRename(rename: ThemeFilterRename): void {
  if (!rename.from || !rename.to || rename.from === rename.to) {
    return;
  }
  try {
    const existing = readPendingThemeFilterRenames();
    existing.push(rename);
    sessionStorage.setItem(
      PENDING_THEME_FILTER_SYNC_KEY,
      JSON.stringify(existing),
    );
  } catch {
    // ignore unavailable storage
  }
}

export function readPendingThemeFilterRenames(): ThemeFilterRename[] {
  try {
    const raw = sessionStorage.getItem(PENDING_THEME_FILTER_SYNC_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    const renames: ThemeFilterRename[] = [];
    for (const entry of parsed) {
      if (
        entry &&
        typeof entry === "object" &&
        typeof (entry as ThemeFilterRename).from === "string" &&
        typeof (entry as ThemeFilterRename).to === "string" &&
        ((entry as ThemeFilterRename).scope === "all" ||
          (entry as ThemeFilterRename).scope === "this_set")
      ) {
        renames.push(entry as ThemeFilterRename);
      }
    }
    return renames;
  } catch {
    return [];
  }
}

export function consumePendingThemeFilterRenames(): ThemeFilterRename[] {
  const renames = readPendingThemeFilterRenames();
  try {
    sessionStorage.removeItem(PENDING_THEME_FILTER_SYNC_KEY);
  } catch {
    // ignore
  }
  return renames;
}

export function applyThemeFilterRenames(
  themeFilter: string[],
  renames: ThemeFilterRename[],
): string[] {
  let next = [...themeFilter];
  for (const { from, to, scope } of renames) {
    if (!next.includes(from)) {
      continue;
    }
    if (scope === "all") {
      next = next.map((theme) => (theme === from ? to : theme));
    } else if (!next.includes(to)) {
      next.push(to);
    }
  }
  const seen = new Set<string>();
  return next.filter((theme) => {
    if (seen.has(theme)) {
      return false;
    }
    seen.add(theme);
    return true;
  });
}

/** Apply any pending renames when initializing list filters (consumes the queue). */
export function initialThemeFilter(storedThemeFilter: string[]): string[] {
  const renames = consumePendingThemeFilterRenames();
  if (renames.length === 0) {
    return storedThemeFilter;
  }
  return applyThemeFilterRenames(storedThemeFilter, renames);
}

export function syncThemeFilterWithOptions(
  themeFilter: string[],
  themeOptions: string[],
  renames: ThemeFilterRename[],
): string[] {
  let next = applyThemeFilterRenames(themeFilter, renames);
  if (themeOptions.length > 0) {
    const optionSet = new Set(themeOptions);
    next = next.filter((theme) => optionSet.has(theme));
  }
  return next;
}
