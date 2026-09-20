import { useState } from "react";

import { patchMissing } from "../api/client";
import type { MinifigPartLineDetail, SetPartLineDetail } from "../api/types";

type InventoryLine = SetPartLineDetail | MinifigPartLineDetail;

interface MissingLineEditorProps {
  setCopyId: number;
  line: InventoryLine;
  inventoryKind: "set_part" | "minifig_part";
  onUpdated: () => void;
  readOnly?: boolean;
}

function patchBody(
  line: InventoryLine,
  inventoryKind: "set_part" | "minifig_part",
  quantity: number,
) {
  if (inventoryKind === "set_part") {
    return {
      set_part_inventory_line_id: line.catalog_line_id,
      quantity_missing: quantity,
    };
  }
  return {
    minifig_part_inventory_line_id: line.catalog_line_id,
    quantity_missing: quantity,
  };
}

export function MissingLineEditor({
  setCopyId,
  line,
  inventoryKind,
  onUpdated,
  readOnly = false,
}: MissingLineEditorProps) {
  const [qty, setQty] = useState(String(line.missing_quantity));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveQuantity() {
    const parsed = Number.parseInt(qty, 10);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > line.quantity) {
      setError(`Enter 0–${line.quantity}`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await patchMissing(
        setCopyId,
        patchBody(line, inventoryKind, parsed),
      );
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  if (readOnly) {
    return <span>{line.missing_quantity}</span>;
  }

  return (
    <div className="missing-editor">
      <label className="missing-editor__qty">
        <span className="sr-only">Missing quantity</span>
        <input
          type="number"
          min={0}
          max={line.quantity}
          value={qty}
          disabled={busy}
          onChange={(e) => setQty(e.target.value)}
          aria-label={`Missing quantity for ${line.part_num}`}
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
