import { resolveImageFetchUrl } from "./resolveImageFetchUrl";

/** Fetch an image URL and return a data URL suitable for jsPDF addImage. */
export async function fetchImageDataUrl(
  pathOrUrl: string | null | undefined,
): Promise<string | null> {
  const url = resolveImageFetchUrl(pathOrUrl);
  if (!url) {
    return null;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    const blob = await response.blob();
    const contentType = blob.type || response.headers.get("content-type") || "";
    if (!contentType.startsWith("image/")) {
      return null;
    }
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        resolve(typeof reader.result === "string" ? reader.result : null);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

export function imageFormatFromDataUrl(dataUrl: string): "JPEG" | "PNG" {
  return dataUrl.startsWith("data:image/jpeg") ? "JPEG" : "PNG";
}
