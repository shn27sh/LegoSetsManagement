import { afterEach, describe, expect, it, vi } from "vitest";

import { listAllFilteredSetCopies } from "./client";
import type { SetCopyListResponse } from "./types";

function okJson(body: unknown): Response {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

function paginatedOwnedSetsFetch(items: SetCopyListResponse["items"]) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://local.test");
    const offset = Number(url.searchParams.get("offset") ?? "0");
    const limit = Number(url.searchParams.get("limit") ?? "50");
    return Promise.resolve(
      okJson({
        total: items.length,
        items: items.slice(offset, offset + limit),
      }),
    );
  });
}

describe("listAllFilteredSetCopies", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests additional pages until the filtered total is loaded", async () => {
    const items = Array.from({ length: 250 }, (_, index) => ({
      id: index + 1,
      set_num: 6024,
      name: `Set ${index + 1}`,
      year: 1980,
      theme_name: "Town",
      image_url: null,
      catalog_sync_state: "ok" as const,
      investigated: false,
      label: null,
      display_label: `copy ${index + 1}`,
      copy_index: index + 1,
      age: null,
      num_parts: 27,
      missing_count: 0,
    }));
    const fetchMock = paginatedOwnedSetsFetch(items);
    vi.stubGlobal("fetch", fetchMock);

    const result = await listAllFilteredSetCopies({});

    expect(result.items).toHaveLength(250);
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      expect.stringContaining("offset=0"),
      expect.stringContaining("offset=200"),
    ]);
  });
});
