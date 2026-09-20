import type {
  GroupBy,
  SetSortBy,
  SortDir,
} from "../utils/setCopyListProcessing";

const STORAGE_KEY = "lcm.setsListPreferences";

const SORT_BY_VALUES: SetSortBy[] = [
  "created",
  "set_num",
  "name",
  "theme",
  "num_parts",
  "age",
];
const SORT_DIR_VALUES: SortDir[] = ["asc", "desc"];
const GROUP_BY_VALUES: GroupBy[] = ["theme", "age"];
const INVESTIGATED_FILTER_VALUES = ["all", "true", "false"] as const;

export type InvestigatedFilter = (typeof INVESTIGATED_FILTER_VALUES)[number];

export const DEFAULT_SETS_LIST_SORT_BY: SetSortBy = "set_num";
export const DEFAULT_SETS_LIST_SORT_DIR: SortDir = "asc";
export const DEFAULT_SETS_LIST_GROUP_BY: GroupBy[] = ["theme"];
export const DEFAULT_INVESTIGATED_FILTER: InvestigatedFilter = "all";

export type SetsListPreferences = {
  sortBy: SetSortBy;
  sortDir: SortDir;
  groupBy: GroupBy[];
  investigatedFilter: InvestigatedFilter;
  themeFilter: string[];
  missingOnly: boolean;
};

function defaultPreferences(): SetsListPreferences {
  return {
    sortBy: DEFAULT_SETS_LIST_SORT_BY,
    sortDir: DEFAULT_SETS_LIST_SORT_DIR,
    groupBy: [...DEFAULT_SETS_LIST_GROUP_BY],
    investigatedFilter: DEFAULT_INVESTIGATED_FILTER,
    themeFilter: [],
    missingOnly: false,
  };
}

function parseGroupBy(value: unknown): GroupBy[] {
  if (!Array.isArray(value)) {
    return defaultPreferences().groupBy;
  }
  const seen = new Set<GroupBy>();
  const groupBy: GroupBy[] = [];
  for (const entry of value) {
    if (
      typeof entry === "string" &&
      GROUP_BY_VALUES.includes(entry as GroupBy) &&
      !seen.has(entry as GroupBy)
    ) {
      const group = entry as GroupBy;
      seen.add(group);
      groupBy.push(group);
    }
  }
  return groupBy;
}

function parseInvestigatedFilter(value: unknown): InvestigatedFilter {
  if (
    typeof value === "string" &&
    INVESTIGATED_FILTER_VALUES.includes(value as InvestigatedFilter)
  ) {
    return value as InvestigatedFilter;
  }
  return DEFAULT_INVESTIGATED_FILTER;
}

function parseThemeFilter(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  const themeFilter: string[] = [];
  for (const entry of value) {
    if (typeof entry === "string" && entry && !seen.has(entry)) {
      seen.add(entry);
      themeFilter.push(entry);
    }
  }
  return themeFilter;
}

function parseMissingOnly(value: unknown): boolean {
  return value === true;
}

export function readStoredSetsListPreferences(): SetsListPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaultPreferences();
    }
    const parsed = JSON.parse(raw) as Partial<SetsListPreferences>;
    const sortBy = SORT_BY_VALUES.includes(parsed.sortBy as SetSortBy)
      ? (parsed.sortBy as SetSortBy)
      : DEFAULT_SETS_LIST_SORT_BY;
    const sortDir = SORT_DIR_VALUES.includes(parsed.sortDir as SortDir)
      ? (parsed.sortDir as SortDir)
      : DEFAULT_SETS_LIST_SORT_DIR;
    return {
      sortBy,
      sortDir,
      groupBy: parseGroupBy(parsed.groupBy),
      investigatedFilter: parseInvestigatedFilter(parsed.investigatedFilter),
      themeFilter: parseThemeFilter(parsed.themeFilter),
      missingOnly: parseMissingOnly(parsed.missingOnly),
    };
  } catch {
    return defaultPreferences();
  }
}

export function writeStoredSetsListPreferences(
  preferences: SetsListPreferences,
): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // ignore private browsing / unavailable storage
  }
}
