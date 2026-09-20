import { describe, expect, it } from "vitest";

import type { MissingPartReportItem } from "../api/types";
import {
  buildMissingPartsPdfFilename,
  buildMissingPartsPdfTableBody,
  collectPdfImagePlacement,
  formatMissingPartLabel,
  formatNeededSetsCell,
} from "./missingPartsReportPdf";

const sampleItem: MissingPartReportItem = {
  part_id: 10,
  part_num: "3001",
  part_name: "Brick 2x4",
  color_id: 0,
  color_name: "Black",
  quantity_missing_total: 3,
  element_ids: ["300100", "300101"],
  part_image_url: null,
  needed_sets: [
    {
      owned_set_id: 1,
      set_num: 6024,
      set_name: "Police Car",
      display_label: "Copy #1",
      quantity_missing: 2,
    },
    {
      owned_set_id: 2,
      set_num: 6024,
      set_name: "Police Car",
      display_label: "Copy #2",
      quantity_missing: 1,
    },
  ],
};

describe("missingPartsReportPdf", () => {
  it("formats part label with hyphen when name exists", () => {
    expect(formatMissingPartLabel(sampleItem)).toBe("3001 - Brick 2x4");
  });

  it("builds table rows for PDF export with image column placeholder", () => {
    expect(buildMissingPartsPdfTableBody([sampleItem])).toEqual([
      [
        "",
        "3001 - Brick 2x4",
        "Black",
        "300100, 300101",
        "3",
        "6024 ×2, 6024",
      ],
    ]);
  });

  it("formats needed sets as set numbers only", () => {
    expect(formatNeededSetsCell(sampleItem)).toBe("6024 ×2, 6024");
  });

  it("builds dated filename", () => {
    expect(
      buildMissingPartsPdfFilename(new Date("2026-05-23T12:00:00.000Z")),
    ).toBe("missing-parts-2026-05-23.pdf");
  });

  it("collects image placement for the first body row", () => {
    const placement = collectPdfImagePlacement(
      {
        section: "body",
        column: { index: 0 },
        row: { index: 0 },
        cell: { x: 40, y: 100 },
        pageNumber: 1,
      },
      ["data:image/png;base64,abc"],
      4,
    );
    expect(placement).toEqual({
      pageNumber: 1,
      x: 44,
      y: 104,
      dataUrl: "data:image/png;base64,abc",
    });
  });
});
