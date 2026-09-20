const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

function apiBaseUrl(): string {
  if (API_BASE.startsWith("http://") || API_BASE.startsWith("https://")) {
    return API_BASE.replace(/\/$/, "");
  }
  const path = API_BASE.startsWith("/") ? API_BASE : `/${API_BASE}`;
  return `${window.location.origin}${path}`.replace(/\/$/, "");
}

function isSameOriginUrl(url: string): boolean {
  try {
    return new URL(url).origin === window.location.origin;
  } catch {
    return false;
  }
}

/** Resolve a local API image path to an absolute same-origin fetch URL. */
export function resolveImageFetchUrl(path: string | null | undefined): string | null {
  if (!path) {
    return null;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return isSameOriginUrl(path) ? path : null;
  }
  if (path.startsWith("/")) {
    return new URL(path, window.location.origin).href;
  }
  return new URL(`${apiBaseUrl()}/${path.replace(/^\//, "")}`).href;
}
