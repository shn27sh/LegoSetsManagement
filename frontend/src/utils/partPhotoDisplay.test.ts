import { describe, expect, it } from "vitest";

import {
  inventoryLineImageUrl,
  partPhotoEditorUrl,
} from "./partPhotoDisplay";

describe("inventoryLineImageUrl", () => {
  it("uses line image_url (element-first from API)", () => {
    expect(
      inventoryLineImageUrl({
        image_url: "/api/elements/302424/image",
        part_image_url: "/api/parts/42/image",
      }),
    ).toBe("/api/elements/302424/image");
  });

  it("returns null when line has no resolved image", () => {
    expect(
      inventoryLineImageUrl({
        image_url: null,
        part_image_url: "/api/parts/42/image",
      }),
    ).toBeNull();
  });
});

describe("partPhotoEditorUrl", () => {
  it("returns part blob URL only", () => {
    expect(
      partPhotoEditorUrl({
        part_image_url: "/api/parts/42/image",
        image_url: "/api/elements/302400/image",
      }),
    ).toBe("/api/parts/42/image");
  });

  it("returns null when no part blob", () => {
    expect(
      partPhotoEditorUrl({
        part_image_url: null,
        image_url: "/api/elements/302400/image",
      }),
    ).toBeNull();
  });
});
