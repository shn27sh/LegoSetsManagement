/** Gate switching to Edit mode. MVP always allows; future may prompt for a password. */
export async function ensureEditAccess(): Promise<boolean> {
  return true;
}
