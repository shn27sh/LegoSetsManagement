import { useEffect, useState } from "react";

import { mediaUrl } from "../api/client";
import { ImageLightbox } from "./ImageLightbox";

interface ImageBlobEditorProps {
  imageUrl: string | null;
  alt: string;
  uploadLabel?: string;
  onUpload: (file: File) => Promise<{ image_url: string | null }>;
  onDelete: () => Promise<{ image_url: string | null }>;
  onUpdated: () => void;
  className?: string;
  disabled?: boolean;
  /** When true, clicking the preview opens a larger view; click again to close. */
  enlargeOnClick?: boolean;
}

export function ImageBlobEditor({
  imageUrl,
  alt,
  uploadLabel = "Upload image",
  onUpload,
  onDelete,
  onUpdated,
  className = "",
  disabled = false,
  enlargeOnClick = false,
}: ImageBlobEditorProps) {
  const [previewUrl, setPreviewUrl] = useState(imageUrl);
  const [enlarged, setEnlarged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPreviewUrl(imageUrl);
  }, [imageUrl]);

  useEffect(() => {
    if (!previewUrl) {
      setEnlarged(false);
    }
  }, [previewUrl]);

  async function onFileSelected(file: File | undefined) {
    if (!file) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await onUpload(file);
      setPreviewUrl(result.image_url);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeImage() {
    setBusy(true);
    setError(null);
    try {
      const result = await onDelete();
      setPreviewUrl(result.image_url);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  const preview = mediaUrl(previewUrl);

  return (
    <div className={`image-blob-editor ${className}`.trim()}>
      {preview ? (
        enlargeOnClick ? (
          <button
            type="button"
            className="image-blob-editor__preview-btn"
            aria-label={`View larger: ${alt}`}
            onClick={() => setEnlarged(true)}
          >
            <img src={preview} alt="" className="image-blob-editor__preview" />
          </button>
        ) : (
          <img src={preview} alt={alt} className="image-blob-editor__preview" />
        )
      ) : (
        <div className="image-blob-editor__placeholder" aria-hidden />
      )}
      {!disabled ? (
        <div className="image-blob-editor__actions">
          <label className="btn btn--small btn--secondary">
            {uploadLabel}
            <input
              type="file"
              accept="image/jpeg,image/png"
              className="sr-only"
              disabled={busy}
              onChange={(e) => void onFileSelected(e.target.files?.[0])}
            />
          </label>
          {preview && (
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={busy}
              onClick={() => void removeImage()}
            >
              Remove
            </button>
          )}
        </div>
      ) : null}
      {error && <span className="image-blob-editor__error">{error}</span>}
      {enlargeOnClick && preview && enlarged && (
        <ImageLightbox
          src={preview}
          alt={alt}
          onClose={() => setEnlarged(false)}
        />
      )}
    </div>
  );
}
