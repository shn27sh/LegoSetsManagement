import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchImageDataUrl } from "./fetchImageDataUrl";

class MockFileReader {
  result: string | ArrayBuffer | null = "data:image/png;base64,abc";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  readAsDataURL(): void {
    this.onload?.();
  }
}

describe("fetchImageDataUrl", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns a data URL when fetch succeeds", async () => {
    vi.stubGlobal("FileReader", MockFileReader as unknown as typeof FileReader);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array([1, 2, 3]), {
        headers: { "Content-Type": "image/png" },
      })),
    );

    const result = await fetchImageDataUrl("/api/parts/1/image");
    expect(result).toBe("data:image/png;base64,abc");
  });

  it("returns null when response is not an image", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { headers: { "Content-Type": "text/plain" } })),
    );

    expect(await fetchImageDataUrl("/api/parts/1/image")).toBeNull();
  });
});
