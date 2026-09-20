/**
 * Primary display title for a set copy (home list + detail header):
 * `{set_num} ({catalog name}) - {copy label}`.
 * `set_num` is the catalog base number (Rebrickable `-n` variant suffix is omitted in the UI).
 * Example: `65001 (Police Station) - Copy #2`
 */
export function formatSetCopyTitle(
  setNum: string | number,
  catalogName: string | null | undefined,
  copyDisplayLabel: string,
): string {
  const displayName = catalogName?.trim() || "Unknown name";
  return `${String(setNum)} (${displayName}) - ${copyDisplayLabel}`;
}
