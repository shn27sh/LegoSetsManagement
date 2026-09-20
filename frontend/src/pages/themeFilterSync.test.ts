import { afterEach, describe, expect, it } from "vitest";

import {
  applyThemeFilterRenames,
  consumePendingThemeFilterRenames,
  initialThemeFilter,
  queueThemeFilterRename,
  syncThemeFilterWithOptions,
} from "./themeFilterSync";

describe("themeFilterSync", () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it("replaces a renamed theme when scope is all", () => {
    expect(
      applyThemeFilterRenames(["Town", "Space"], [
        { from: "Town", to: "Classic Town", scope: "all" },
      ]),
    ).toEqual(["Classic Town", "Space"]);
  });

  it("keeps the old theme and adds the new one when scope is this_set", () => {
    expect(
      applyThemeFilterRenames(["Town"], [
        { from: "Town", to: "Classic Town", scope: "this_set" },
      ]),
    ).toEqual(["Town", "Classic Town"]);
  });

  it("queues and consumes pending renames once", () => {
    queueThemeFilterRename({
      from: "Town",
      to: "Classic Town",
      scope: "all",
    });
    expect(consumePendingThemeFilterRenames()).toEqual([
      { from: "Town", to: "Classic Town", scope: "all" },
    ]);
    expect(consumePendingThemeFilterRenames()).toEqual([]);
  });

  it("applies pending renames during initial theme filter read", () => {
    queueThemeFilterRename({
      from: "4 Juniors Two",
      to: "4 Juniors Three",
      scope: "all",
    });
    expect(initialThemeFilter(["4 Juniors Two"])).toEqual(["4 Juniors Three"]);
    expect(consumePendingThemeFilterRenames()).toEqual([]);
  });

  it("prunes stale themes after applying renames", () => {
    expect(
      syncThemeFilterWithOptions(
        ["Town"],
        ["Classic Town"],
        [{ from: "Town", to: "Classic Town", scope: "all" }],
      ),
    ).toEqual(["Classic Town"]);
  });
});
