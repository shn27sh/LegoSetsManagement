/** Resolved URL for part photo display (list + modal), not raw API fields alone. */
export interface PartPhotoDisplayLine {
  part_image_url: string | null;
  image_url: string | null;
  part_image_user_removed?: boolean;
}

/**
 * Inventory row thumbnail: color-specific line URL from the API (element BLOB
 * first, then part BLOB fallback). Never use global part_image_url alone — the
 * same part_num in different colors shares one parts row.
 */
export function inventoryLineImageUrl(
  line: Pick<PartPhotoDisplayLine, "image_url">,
): string | null {
  return line.image_url ?? null;
}

/** Global part-photo editor only (PUT/DELETE /parts/{id}/image). */
export function partPhotoEditorUrl(
  line: Pick<PartPhotoDisplayLine, "part_image_url">,
): string | null {
  return line.part_image_url ?? null;
}
