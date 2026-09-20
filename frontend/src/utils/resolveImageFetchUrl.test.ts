import { describe, expect, it } from "vitest";

import { resolveImageFetchUrl } from "./resolveImageFetchUrl";

describe("resolveImageFetchUrl", () => {
  it("returns null for empty input", () => {
    expect(resolveImageFetchUrl(null)).toBeNull();
  });

  it("resolves same-origin API paths", () => {
    expect(resolveImageFetchUrl("/api/parts/42/image")).toBe(
      `${window.location.origin}/api/parts/42/image`,
    );
  });

  it("rejects external HTTPS URLs", () => {
    expect(
      resolveImageFetchUrl("https://cdn.rebrickable.com/media/parts/3024.png"),
    ).toBeNull();
  });

  it("keeps same-origin absolute URLs", () => {
    expect(
      resolveImageFetchUrl(`${window.location.origin}/api/parts/1/image`),
    ).toBe(`${window.location.origin}/api/parts/1/image`);
  });
});
