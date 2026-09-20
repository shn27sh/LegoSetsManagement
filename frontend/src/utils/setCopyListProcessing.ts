import type { SetCopyListItem } from "../api/types";

export type SetSortBy = "created" | "set_num" | "name" | "theme" | "num_parts" | "age";
export type SortDir = "asc" | "desc";
export type GroupBy = "theme" | "age";

export type GroupedSecondarySection = {
  secondaryLabel: string;
  items: SetCopyListItem[];
};

export type GroupedPrimarySection = {
  primaryLabel: string;
  secondaries: GroupedSecondarySection[];
};

function groupLabel(item: SetCopyListItem, groupBy: GroupBy): string {
  if (groupBy === "theme") {
    return item.theme_name?.trim() || "Unknown theme";
  }
  return item.age != null ? `Age ${item.age}` : "Age unknown";
}

function sortDirectionMultiplier(sortDir: SortDir): number {
  return sortDir === "asc" ? 1 : -1;
}

export function compareSetCopyItems(
  a: SetCopyListItem,
  b: SetCopyListItem,
  sortBy: SetSortBy,
  sortDir: SortDir,
): number {
  const direction = sortDirectionMultiplier(sortDir);
  let cmp = 0;
  switch (sortBy) {
    case "created":
      cmp = a.id - b.id;
      break;
    case "set_num":
      cmp = String(a.set_num).localeCompare(String(b.set_num), undefined, {
        numeric: true,
      });
      break;
    case "name":
      cmp = (a.name ?? "").localeCompare(b.name ?? "", undefined, {
        sensitivity: "base",
      });
      break;
    case "theme":
      cmp = (a.theme_name ?? "").localeCompare(b.theme_name ?? "", undefined, {
        sensitivity: "base",
      });
      break;
    case "num_parts":
      cmp = (a.num_parts ?? -1) - (b.num_parts ?? -1);
      break;
    case "age":
      cmp = (a.age ?? -1) - (b.age ?? -1);
      break;
  }
  return cmp * direction || a.id - b.id;
}

export function sortSetCopyItems(
  list: SetCopyListItem[],
  sortBy: SetSortBy,
  sortDir: SortDir,
): SetCopyListItem[] {
  return [...list].sort((a, b) => compareSetCopyItems(a, b, sortBy, sortDir));
}

export function buildGroupedSections(
  items: SetCopyListItem[],
  groupBy: GroupBy[],
  sortBy: SetSortBy,
  sortDir: SortDir,
): GroupedPrimarySection[] {
  if (groupBy.length === 0) {
    return [];
  }
  const primary = groupBy[0]!;
  const secondary = groupBy[1];
  const groups = new Map<string, Map<string, SetCopyListItem[]>>();
  for (const item of items) {
    const primaryLabel = groupLabel(item, primary);
    const secondaryLabel = secondary ? groupLabel(item, secondary) : "";
    const secondaryMap = groups.get(primaryLabel) ?? new Map<string, SetCopyListItem[]>();
    const bucket = secondaryMap.get(secondaryLabel) ?? [];
    bucket.push(item);
    secondaryMap.set(secondaryLabel, bucket);
    groups.set(primaryLabel, secondaryMap);
  }

  const compareGroups = (left: SetCopyListItem[], right: SetCopyListItem[]) =>
    compareSetCopyItems(
      sortSetCopyItems(left, sortBy, sortDir)[0]!,
      sortSetCopyItems(right, sortBy, sortDir)[0]!,
      sortBy,
      sortDir,
    );

  return Array.from(groups.entries())
    .map(([primaryLabel, secondaryMap]) => {
      const secondaries = Array.from(secondaryMap.entries())
        .map(([secondaryLabel, bucket]) => ({
          secondaryLabel,
          items: sortSetCopyItems(bucket, sortBy, sortDir),
        }))
        .sort((a, b) => compareGroups(a.items, b.items));
      return { primaryLabel, secondaries };
    })
    .sort((a, b) =>
      compareGroups(
        a.secondaries.flatMap((section) => section.items),
        b.secondaries.flatMap((section) => section.items),
      ),
    );
}

/** Returns grouped sections containing only items in [offset, offset + pageSize). */
export function paginateGroupedSections(
  sections: GroupedPrimarySection[],
  offset: number,
  pageSize: number,
): GroupedPrimarySection[] {
  let skip = offset;
  let remaining = pageSize;
  const result: GroupedPrimarySection[] = [];

  outer: for (const primary of sections) {
    const pageSecondaries: GroupedSecondarySection[] = [];

    for (const secondary of primary.secondaries) {
      const bucket = secondary.items;
      if (skip >= bucket.length) {
        skip -= bucket.length;
        continue;
      }

      const visible = bucket.slice(skip, skip + remaining);
      skip = 0;
      remaining -= visible.length;

      if (visible.length > 0) {
        pageSecondaries.push({
          secondaryLabel: secondary.secondaryLabel,
          items: visible,
        });
      }

      if (remaining <= 0) {
        if (pageSecondaries.length > 0) {
          result.push({
            primaryLabel: primary.primaryLabel,
            secondaries: pageSecondaries,
          });
        }
        break outer;
      }
    }

    if (pageSecondaries.length > 0) {
      result.push({
        primaryLabel: primary.primaryLabel,
        secondaries: pageSecondaries,
      });
    }

    if (remaining <= 0) {
      break;
    }
  }

  return result;
}
