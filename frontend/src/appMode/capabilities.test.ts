import { describe, expect, it } from "vitest";

import { getCapabilities } from "./capabilities";

describe("getCapabilities", () => {
  it("view mode is read-only", () => {
    const caps = getCapabilities("view");
    expect(caps.canSync).toBe(false);
    expect(caps.canImport).toBe(false);
    expect(caps.canAddOrDuplicate).toBe(false);
    expect(caps.canEditCopyFields).toBe(false);
    expect(caps.canEditCatalog).toBe(false);
    expect(caps.canEditQuantities).toBe(false);
    expect(caps.canEditParts).toBe(false);
    expect(caps.canDeleteCopy).toBe(false);
    expect(caps.canEditImages).toBe(false);
    expect(caps.canToggleInvestigated).toBe(false);
    expect(caps.canEditMissing).toBe(false);
    expect(caps.canEditMissingPhotos).toBe(false);
  });

  it("investigate mode allows investigated and missing only", () => {
    const caps = getCapabilities("investigate");
    expect(caps.canToggleInvestigated).toBe(true);
    expect(caps.canEditMissing).toBe(true);
    expect(caps.canEditMissingPhotos).toBe(true);
    expect(caps.canSync).toBe(false);
    expect(caps.canImport).toBe(false);
    expect(caps.canAddOrDuplicate).toBe(false);
    expect(caps.canEditCopyFields).toBe(false);
    expect(caps.canEditCatalog).toBe(false);
    expect(caps.canEditQuantities).toBe(false);
    expect(caps.canEditParts).toBe(false);
    expect(caps.canDeleteCopy).toBe(false);
    expect(caps.canEditImages).toBe(false);
  });

  it("edit mode allows all mutations", () => {
    const caps = getCapabilities("edit");
    expect(caps.canSync).toBe(true);
    expect(caps.canImport).toBe(true);
    expect(caps.canAddOrDuplicate).toBe(true);
    expect(caps.canEditCopyFields).toBe(true);
    expect(caps.canEditCatalog).toBe(true);
    expect(caps.canEditQuantities).toBe(true);
    expect(caps.canEditParts).toBe(true);
    expect(caps.canDeleteCopy).toBe(true);
    expect(caps.canEditImages).toBe(true);
    expect(caps.canToggleInvestigated).toBe(true);
    expect(caps.canEditMissing).toBe(true);
    expect(caps.canEditMissingPhotos).toBe(true);
  });
});
