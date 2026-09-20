import { useState } from "react";

import { patchInstanceInventoryLine } from "../api/client";
import type { MinifigPartLineDetail, SetPartLineDetail } from "../api/types";

type InventoryLine = SetPartLineDetail | MinifigPartLineDetail;

interface InstanceQuantityEditorProps {
  setCopyId: number;
  line: InventoryLine;
  onUpdated: () => void;
  readOnly?: boolean;
}

export function InstanceQuantityEditor({
  setCopyId,
  line,
  onUpdated,
  readOnly = false,
}: InstanceQuantityEditorProps) {
  const [qty, setQty] = useState(String(line.quantity));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveQuantity() {
    const parsed = Number.parseInt(qty, 10);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError("Enter a quantity greater than 0");
      return;
    }
    if (parsed < line.missing_quantity) {
      setError(`Quantity must be at least missing count (${line.missing_quantity})`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await patchInstanceInventoryLine(setCopyId, line.instance_line_id, {
        quantity: parsed,
      });
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  if (readOnly) {
    return <span>{line.quantity}</span>;
  }

  return (
    <div className="qty-editor">
      <label className="qty-editor__field">
        <span className="sr-only">Quantity in this copy for {line.part_num}</span>
        <input
          type="number"
          min={1}
          value={qty}
          disabled={busy}
          onChange={(e) => setQty(e.target.value)}
          aria-label={`Quantity in this copy for ${line.part_num}`}
        />
      </label>
      <button
        type="button"
        className="btn btn--small"
        disabled={busy}
        onClick={() => void saveQuantity()}
      >
        Save
      </button>
      {error && <span className="missing-editor__error">{error}</span>}
    </div>
  );
}
