import {
  deleteCatalogMinifigImage,
  uploadCatalogMinifigImage,
} from "../api/client";
import { ImageBlobEditor } from "./ImageBlobEditor";

interface CatalogMinifigImageEditorProps {
  catalogMinifigId: number;
  imageUrl: string | null;
  minifigNum: string;
  name?: string | null;
  onUpdated: () => void;
  disabled?: boolean;
}

export function CatalogMinifigImageEditor({
  catalogMinifigId,
  imageUrl,
  minifigNum,
  name,
  onUpdated,
  disabled = false,
}: CatalogMinifigImageEditorProps) {
  const alt = name
    ? `Minifigure ${minifigNum} — ${name}`
    : `Minifigure ${minifigNum}`;

  return (
    <ImageBlobEditor
      className="catalog-minifig-image-editor"
      imageUrl={imageUrl}
      alt={alt}
      uploadLabel="Minifigure photo"
      enlargeOnClick
      disabled={disabled}
      onUpload={(file) => uploadCatalogMinifigImage(catalogMinifigId, file)}
      onDelete={() => deleteCatalogMinifigImage(catalogMinifigId)}
      onUpdated={onUpdated}
    />
  );
}
