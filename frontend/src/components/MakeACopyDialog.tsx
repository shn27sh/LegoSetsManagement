import { useEffect, useState } from "react";

import {
  duplicateSetCopy,
  fetchDuplicatePreview,
} from "../api/client";
import type { DuplicatePreviewResponse } from "../api/types";
import { Modal } from "./Modal";

interface MakeACopyDialogProps {
  setCopyId: number;
  onClose: () => void;
  onCreated: (newId: number) => void;
}

export function MakeACopyDialog({
  setCopyId,
  onClose,
  onCreated,
}: MakeACopyDialogProps) {
  const [preview, setPreview] = useState<DuplicatePreviewResponse | null>(null);
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchDuplicatePreview(setCopyId);
        if (!cancelled) {
          setPreview(data);
          setLabel(data.suggested_label);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load preview");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setCopyId]);

  async function onConfirm() {
    setSaving(true);
    setError(null);
    try {
      const created = await duplicateSetCopy(setCopyId, label.trim());
      onCreated(created.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create copy");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="Make a copy" onClose={onClose}>
      {loading && <p>Loading…</p>}
      {error && <p className="async-message--error">{error}</p>}
      {preview && !loading && (
        <>
          <p>
            You are creating a copy of LEGO set number{" "}
            <strong>{preview.set_num}</strong>
            {preview.set_name ? ` (${preview.set_name})` : ""}.
          </p>
          <label className="form-field">
            Label
            <input
              type="text"
              value={label}
              disabled={saving}
              onChange={(e) => setLabel(e.target.value)}
            />
          </label>
          <p className="form-hint">
            Suggested label: {preview.suggested_label}
          </p>
          <div className="modal__actions">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={saving}
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={saving || !label.trim()}
              onClick={() => void onConfirm()}
            >
              Create a copy
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
