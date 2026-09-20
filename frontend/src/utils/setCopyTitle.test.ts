import { describe, expect, it } from "vitest";

import { formatSetCopyTitle } from "./setCopyTitle";

describe("formatSetCopyTitle", () => {
  it("uses catalog name and copy label", () => {
    expect(
      formatSetCopyTitle(65001, "Police Station", "Copy #2"),
    ).toBe("65001 (Police Station) - Copy #2");
  });

  it("uses Unknown name when catalog name is missing", () => {
    expect(formatSetCopyTitle(6024, null, "Copy #1")).toBe(
      "6024 (Unknown name) - Copy #1",
    );
  });

  it("trims catalog name whitespace", () => {
    expect(formatSetCopyTitle(1, " Castle  ", "ebay")).toBe(
      "1 (Castle) - ebay",
    );
  });
});
