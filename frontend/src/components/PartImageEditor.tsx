import { deletePartImage, uploadPartImage } from "../api/client";
import { ImageBlobEditor } from "./ImageBlobEditor";

interface PartImageEditorProps {
  partId: number;
  partNum: string;
  imageUrl: string | null;
  onUpdated: () => void;
}

export function PartImageEditor({
  partId,
  partNum,
  imageUrl,
  onUpdated,
}: PartImageEditorProps) {
  return (
    <ImageBlobEditor
      className="part-image-editor"
      imageUrl={imageUrl}
      alt={`Part ${partNum}`}
      uploadLabel="Part photo"
      onUpload={(file) => uploadPartImage(partId, file)}
      onDelete={() => deletePartImage(partId)}
      onUpdated={onUpdated}
    />
  );
}
