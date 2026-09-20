import type { MissingPartReportItem } from "../api/types";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import {
  fetchImageDataUrl,
  imageFormatFromDataUrl,
} from "./fetchImageDataUrl";

export function formatMissingPartLabel(item: MissingPartReportItem): string {
  if (item.part_name) {
    return `${item.part_num} - ${item.part_name}`;
  }
  return item.part_num;
}

export function formatElementIds(elementIds: string[]): string {
  return elementIds.length > 0 ? elementIds.join(", ") : "No Element ID";
}

/** Set numbers only, comma-separated, with optional ×qty when > 1. */
export function formatNeededSetsCell(item: MissingPartReportItem): string {
  return item.needed_sets
    .map((setRow) => {
      const setNum = String(setRow.set_num);
      return setRow.quantity_missing > 1
        ? `${setNum} ×${setRow.quantity_missing}`
        : setNum;
    })
    .join(", ");
}

export interface MissingPartsPdfOptions {
  filterLabel: string;
  generatedAt?: Date;
}

export interface PdfImagePlacement {
  pageNumber: number;
  x: number;
  y: number;
  dataUrl: string;
}

export function buildMissingPartsPdfFilename(generatedAt: Date = new Date()): string {
  const stamp = generatedAt.toISOString().slice(0, 10);
  return `missing-parts-${stamp}.pdf`;
}

export function buildMissingPartsPdfTableBody(
  items: MissingPartReportItem[],
): string[][] {
  return items.map((item) => [
    "",
    formatMissingPartLabel(item),
    item.color_name ?? String(item.color_id),
    formatElementIds(item.element_ids),
    String(item.quantity_missing_total),
    formatNeededSetsCell(item),
  ]);
}

async function loadPartImageDataUrls(
  items: MissingPartReportItem[],
): Promise<(string | null)[]> {
  return Promise.all(
    items.map((item) => fetchImageDataUrl(item.part_image_url)),
  );
}

export function collectPdfImagePlacement(
  data: {
    section: string;
    column: { index: number };
    row: { index: number };
    cell: { x: number; y: number };
    pageNumber: number;
  },
  imageDataUrls: (string | null)[],
  padding: number,
): PdfImagePlacement | null {
  if (data.section !== "body" || data.column.index !== 0) {
    return null;
  }
  const imageDataUrl = imageDataUrls[data.row.index];
  if (!imageDataUrl) {
    return null;
  }
  return {
    pageNumber: data.pageNumber,
    x: data.cell.x + padding,
    y: data.cell.y + padding,
    dataUrl: imageDataUrl,
  };
}

export function drawPdfImagePlacements(
  doc: {
    setPage(page: number): void;
    addImage(
      imageData: string,
      format: string,
      x: number,
      y: number,
      width: number,
      height: number,
    ): void;
  },
  placements: PdfImagePlacement[],
  imageSize: number,
): void {
  for (const placement of placements) {
    doc.setPage(placement.pageNumber);
    doc.addImage(
      placement.dataUrl,
      imageFormatFromDataUrl(placement.dataUrl),
      placement.x,
      placement.y,
      imageSize,
      imageSize,
    );
  }
}

export async function downloadMissingPartsPdf(
  items: MissingPartReportItem[],
  options: MissingPartsPdfOptions,
): Promise<void> {
  const imageDataUrls = await loadPartImageDataUrls(items);
  const generatedAt = options.generatedAt ?? new Date();
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  const imageSize = 28;
  const padding = 4;
  const placements: PdfImagePlacement[] = [];

  doc.setFontSize(16);
  doc.text("Missing parts report", 40, 40);
  doc.setFontSize(10);
  doc.text(options.filterLabel, 40, 58);
  doc.text(
    `Generated ${generatedAt.toLocaleString()} · ${items.length} part${items.length === 1 ? "" : "s"}`,
    40,
    72,
  );

  autoTable(doc, {
    startY: 88,
    head: [["Image", "Part", "Color", "Element ID", "Needed", "Sets"]],
    body: buildMissingPartsPdfTableBody(items),
    styles: { fontSize: 9, cellPadding: 4, overflow: "linebreak" },
    headStyles: { fillColor: [45, 55, 72] },
    columnStyles: {
      0: { cellWidth: imageSize + 8, minCellHeight: imageSize + 8 },
      1: { cellWidth: 130 },
      2: { cellWidth: 65 },
      3: { cellWidth: 85 },
      4: { cellWidth: 45, halign: "right" },
      5: { cellWidth: "auto" },
    },
    didDrawCell: (data) => {
      const placement = collectPdfImagePlacement(data, imageDataUrls, padding);
      if (placement) {
        placements.push(placement);
      }
    },
  });

  drawPdfImagePlacements(doc, placements, imageSize);

  doc.save(buildMissingPartsPdfFilename(generatedAt));
}
