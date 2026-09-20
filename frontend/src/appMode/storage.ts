import { APP_MODES, type AppMode } from "./types";

const STORAGE_KEY = "lcm.appMode";

export function readStoredAppMode(): AppMode {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value && APP_MODES.includes(value as AppMode)) {
      return value as AppMode;
    }
  } catch {
    // ignore private browsing / unavailable storage
  }
  return "view";
}

export function writeStoredAppMode(mode: AppMode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // ignore
  }
}
