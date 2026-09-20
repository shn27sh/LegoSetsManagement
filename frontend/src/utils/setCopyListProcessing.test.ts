import { describe, expect, it } from "vitest";

import type { SetCopyListItem } from "../api/types";
import {
  buildGroupedSections,
  paginateGroupedSections,
  sortSetCopyItems,
} from "./setCopyListProcessing";

function item(
  overrides: Partial<SetCopyListItem> & Pick<SetCopyListItem, "id">,
): SetCopyListItem {
  return {
    id: overrides.id,
    set_num: 6024,
    name: overrides.name ?? "Police Car",
    year: 1980,
    theme_name: overrides.theme_name ?? "Town",
    image_url: null,
    catalog_sync_state: "ok",
    investigated: false,
    label: null,
    display_label: `copy ${overrides.id}`,
    copy_index: overrides.id,
    age: overrides.age ?? null,
    num_parts: 27,
    missing_count: 0,
  };
}

describe("setCopyListProcessing", () => {
  it("sorts the full list by name", () => {
    const sorted = sortSetCopyItems(
      [item({ id: 1, name: "Zebra" }), item({ id: 2, name: "Alpha" })],
      "name",
      "asc",
    );
    expect(sorted.map((row) => row.name)).toEqual(["Alpha", "Zebra"]);
  });

  it("groups first and then sorts groups and bucket items", () => {
    const grouped = buildGroupedSections(
      [
        item({ id: 1, theme_name: "Town", name: "Zebra" }),
        item({ id: 2, theme_name: "Space", name: "Alpha" }),
        item({ id: 3, theme_name: "Town", name: "Beta" }),
      ],
      ["theme"],
      "name",
      "asc",
    );
    expect(grouped.map((section) => section.primaryLabel)).toEqual(["Space", "Town"]);
    expect(grouped[1]?.secondaries[0]?.items.map((row) => row.name)).toEqual([
      "Beta",
      "Zebra",
    ]);
  });

  it("paginates grouped sections by item count", () => {
    const grouped = buildGroupedSections(
      Array.from({ length: 5 }, (_, index) =>
        item({ id: index + 1, theme_name: "Town", name: `Set ${index + 1}` }),
      ),
      ["theme"],
      "name",
      "asc",
    );
    const page = paginateGroupedSections(grouped, 2, 2);
    expect(page).toHaveLength(1);
    expect(page[0]?.secondaries[0]?.items.map((row) => row.name)).toEqual([
      "Set 3",
      "Set 4",
    ]);
  });
});
