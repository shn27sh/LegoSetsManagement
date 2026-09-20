import {
  deleteCatalogSetImage,
  uploadCatalogSetImage,
} from "../api/client";
import { ImageBlobEditor } from "./ImageBlobEditor";

interface CatalogSetImageEditorProps {
  catalogSetId: number;
  imageUrl: string | null;
  setNum: string | number;
  onUpdated: () => void;
  disabled?: boolean;
}

export function CatalogSetImageEditor({
  catalogSetId,
  imageUrl,
  setNum,
  onUpdated,
  disabled = false,
}: CatalogSetImageEditorProps) {
  return (
    <ImageBlobEditor
      className="catalog-set-image-editor"
      imageUrl={imageUrl}
      alt={`Set ${setNum}`}
      uploadLabel="Set photo"
      enlargeOnClick
      disabled={disabled}
      onUpload={(file) => uploadCatalogSetImage(catalogSetId, file)}
      onDelete={() => deleteCatalogSetImage(catalogSetId)}
      onUpdated={onUpdated}
    />
  );
}
