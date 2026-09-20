import { FormEvent, useState } from "react";

import { createSetCopy, fetchAddSetPreview, fetchManualAddRebrickableDraft } from "../api/client";
import type {
  AddSetPreviewResponse,
  ManualAddPartInput,
} from "../api/types";
import { AsyncMessage } from "./AsyncMessage";
import { Modal } from "./Modal";

interface AddSetWizardProps {
  onClose: () => void;
  onCreated: (setCopyId: number) => void;
}

interface PartDraft {
  part_num: string;
  part_name: string;
  color_id: string;
  color_name: string;
  quantity: string;
}

function manualPartToDraft(row: ManualAddPartInput): PartDraft {
  return {
    part_num: row.part_num,
    part_name: row.part_name ?? "",
    color_id: String(row.color_id ?? 0),
    color_name: row.color_name ?? "",
    quantity: String(row.quantity),
  };
}

const emptyPart = (): PartDraft => ({
  part_num: "",
  part_name: "",
  color_id: "0",
  color_name: "Black",
  quantity: "1",
});

type WizardStep = 1 | "existing-warning" | 2;

export function AddSetWizard({ onClose, onCreated }: AddSetWizardProps) {
  const [step, setStep] = useState<WizardStep>(1);
  const [setNum, setSetNum] = useState("");
  const [preview, setPreview] = useState<AddSetPreviewResponse | null>(null);
  const [label, setLabel] = useState("");
  const [catalogName, setCatalogName] = useState("");
  const [catalogTheme, setCatalogTheme] = useState("");
  const [catalogYear, setCatalogYear] = useState("");
  const [catalogParts, setCatalogParts] = useState("");
  const [age, setAge] = useState("");
  const [parts, setParts] = useState<PartDraft[]>([emptyPart()]);
  const [loading, setLoading] = useState(false);
  const [prefillLoading, setPrefillLoading] = useState(false);
  const [draftHint, setDraftHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onNext(event: FormEvent) {
    event.preventDefault();
    const trimmed = setNum.trim();
    if (!trimmed) {
      setError("Enter a LEGO set number");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAddSetPreview(trimmed);
      setPreview(result);
      setLabel(result.suggested_label);
      if (result.catalog_exists) {
        setCatalogName(result.set_name ?? "");
        setCatalogTheme(result.theme_name ?? "");
        setCatalogYear(result.year != null ? String(result.year) : "");
        setCatalogParts(
          result.num_parts != null ? String(result.num_parts) : "",
        );
        setAge(result.age != null ? String(result.age) : "");
      } else {
        setCatalogName("");
        setCatalogTheme("");
        setCatalogYear("");
        setCatalogParts("");
        setAge("");
        setParts([emptyPart()]);
        setDraftHint(null);
      }
      setStep(result.catalog_exists ? "existing-warning" : 2);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not look up set number",
      );
    } finally {
      setLoading(false);
    }
  }

  function buildPartsPayload(): ManualAddPartInput[] {
    return parts
      .map((row) => ({
        part_num: row.part_num.trim(),
        part_name: row.part_name.trim() || null,
        color_id: Number.parseInt(row.color_id, 10) || 0,
        color_name: row.color_name.trim() || null,
        quantity: Number.parseInt(row.quantity, 10),
      }))
      .filter((row) => row.part_num.length > 0);
  }

  async function fetchFromRebrickable() {
    if (!preview || preview.catalog_exists) {
      return;
    }
    setPrefillLoading(true);
    setError(null);
    try {
      const draft = await fetchManualAddRebrickableDraft(preview.set_num);
      const { catalog } = draft;
      setCatalogName(catalog.name ?? "");
      setCatalogTheme(catalog.theme_name ?? "");
      setCatalogYear(catalog.year != null ? String(catalog.year) : "");
      setCatalogParts(catalog.num_parts != null ? String(catalog.num_parts) : "");
      setAge(draft.age != null ? String(draft.age) : "");
      setParts(
        draft.parts.length > 0 ? draft.parts.map(manualPartToDraft) : [emptyPart()],
      );
      setDraftHint(draft.note);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load from Rebrickable",
      );
    } finally {
      setPrefillLoading(false);
    }
  }

  function updatePart(index: number, patch: Partial<PartDraft>) {
    setParts((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  }

  function addPartRow() {
    setParts((rows) => [...rows, emptyPart()]);
  }

  function removePartRow(index: number) {
    setParts((rows) =>
      rows.length <= 1 ? [emptyPart()] : rows.filter((_, i) => i !== index),
    );
  }

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    if (!preview) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (preview.catalog_exists) {
        const created = await createSetCopy({
          set_num: preview.set_num,
          label: label.trim() || null,
        });
        onCreated(created.id);
        return;
      }

      const yearTrimmed = catalogYear.trim();
      const partsTrimmed = catalogParts.trim();
      const ageTrimmed = age.trim();
      const partRows = buildPartsPayload();
      for (const row of partRows) {
        if (!Number.isFinite(row.quantity) || row.quantity < 1) {
          setError("Each part needs a quantity of at least 1");
          setLoading(false);
          return;
        }
      }

      const created = await createSetCopy({
        set_num: preview.set_num,
        label: label.trim() || null,
        age: ageTrimmed === "" ? null : Number.parseInt(ageTrimmed, 10),
        catalog: {
          name: catalogName.trim() || null,
          theme_name: catalogTheme.trim() || null,
          year: yearTrimmed === "" ? null : Number.parseInt(yearTrimmed, 10),
          num_parts:
            partsTrimmed === "" ? null : Number.parseInt(partsTrimmed, 10),
        },
        parts: partRows.length > 0 ? partRows : undefined,
      });
      onCreated(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add set");
    } finally {
      setLoading(false);
    }
  }

  function backToStepOne() {
    setStep(1);
    setPreview(null);
    setError(null);
    setDraftHint(null);
  }

  function cancelExistingWarning() {
    backToStepOne();
  }

  function continueExistingWarning() {
    setStep(2);
  }

  if (step === "existing-warning" && preview?.catalog_exists) {
    return (
      <Modal title="Set already exists" onClose={onClose}>
        <p>
          Set number <strong>{preview.set_num}</strong>
          {preview.set_name ? ` (${preview.set_name})` : ""} is already in your
          collection. If you continue, a new copy will be created and filled with
          the part list from the database.{" "}
          <strong>Missing items</strong> and <strong>investigated</strong> status
          are not copied to the new copy.
        </p>
        <div className="modal__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={cancelExistingWarning}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={continueExistingWarning}
          >
            Continue
          </button>
        </div>
      </Modal>
    );
  }

  if (step === 1) {
    return (
      <Modal title="Add LEGO set" onClose={onClose}>
        <form onSubmit={(e) => void onNext(e)}>
          <p>Enter the LEGO set number for the set you want to add.</p>
          <AsyncMessage error={error} />
          <label className="form-field form-field--wide">
            LEGO set number
            <input
              value={setNum}
              disabled={loading}
              placeholder="e.g. 6024 or 65001-2"
              onChange={(e) => setSetNum(e.target.value)}
              autoFocus
            />
          </label>
          <div className="modal__actions">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={loading}
              onClick={onClose}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={loading}>
              {loading ? "Checking…" : "Next"}
            </button>
          </div>
        </form>
      </Modal>
    );
  }

  if (!preview) {
    return null;
  }

  const copyNumber = preview.existing_copy_count + 1;

  return (
    <Modal
      title={
        preview.catalog_exists
          ? `Add instance — ${preview.set_num}`
          : `New set — ${preview.set_num}`
      }
      modalClassName={preview.catalog_exists ? undefined : "modal--wide"}
      onClose={onClose}
    >
      <form onSubmit={(e) => void onAdd(e)}>
        <AsyncMessage error={error} />

        {preview.catalog_exists ? (
          <>
            <p className="add-set-wizard__intro">
              You are adding a <strong>new instance</strong> of LEGO set{" "}
              <strong>{preview.set_num}</strong>
              {preview.set_name ? ` (${preview.set_name})` : ""}. This will be{" "}
              <strong>copy #{copyNumber}</strong>. Shared catalog fields and parts
              inventory are shown below (read-only).
            </p>

            <div className="add-set-wizard__catalog">
              {preview.image_url ? (
                <img
                  src={preview.image_url}
                  alt=""
                  className="add-set-wizard__image"
                />
              ) : (
                <div
                  className="add-set-wizard__image add-set-wizard__image--placeholder"
                  aria-hidden
                />
              )}
              <div className="add-set-wizard__fields">
                <label className="form-field">
                  LEGO set name
                  <input value={catalogName} readOnly />
                </label>
                <label className="form-field">
                  Theme
                  <input value={catalogTheme} readOnly />
                </label>
                <label className="form-field">
                  Number of parts
                  <input value={catalogParts} readOnly />
                </label>
                <label className="form-field">
                  Age
                  <input value={age} readOnly />
                </label>
                <label className="form-field">
                  Instance label
                  <input
                    value={label}
                    disabled={loading}
                    onChange={(e) => setLabel(e.target.value)}
                  />
                </label>
              </div>
            </div>

            {preview.set_parts.length > 0 ? (
              <div className="add-set-wizard__parts">
                <h3>Parts inventory</h3>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Part</th>
                        <th>Color</th>
                        <th>Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.set_parts.map((line) => (
                        <tr
                          key={`${line.part_num}-${line.color_name}`}
                        >
                          <td>
                            <strong>{line.part_num}</strong>
                            {line.part_name ? ` — ${line.part_name}` : ""}
                          </td>
                          <td>{line.color_name}</td>
                          <td>{line.quantity}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="form-hint">
                No parts in the catalog template yet. You can add parts on the set
                detail page after creating this instance.
              </p>
            )}
          </>
        ) : (
          <>
            <p className="add-set-wizard__intro">
              Set number <strong>{preview.set_num}</strong> is not in your
              collection yet. Enter catalog details (optional), add part lines
              here or on the set detail page. You can pull metadata and set-level
              parts from Rebrickable (no images).
            </p>

            <div className="add-set-wizard__toolbar">
              <button
                type="button"
                className="btn btn--secondary btn--small"
                disabled={loading || prefillLoading}
                onClick={() => void fetchFromRebrickable()}
              >
                {prefillLoading ? "Fetching…" : "Fetch from Rebrickable"}
              </button>
              <span className="form-hint" style={{ flex: "1 1 12rem", margin: 0 }}>
                Requires configured API key (same as CSV import / sync).
              </span>
            </div>

            <div className="instance-form__grid">
              <label className="form-field">
                LEGO set name
                <input
                  value={catalogName}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setCatalogName(e.target.value)}
                />
              </label>
              <label className="form-field">
                Theme
                <input
                  value={catalogTheme}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setCatalogTheme(e.target.value)}
                />
              </label>
              <label className="form-field">
                Year
                <input
                  type="number"
                  value={catalogYear}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setCatalogYear(e.target.value)}
                />
              </label>
              <label className="form-field">
                Number of parts
                <input
                  type="number"
                  value={catalogParts}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setCatalogParts(e.target.value)}
                />
              </label>
              <label className="form-field">
                Age
                <input
                  type="number"
                  value={age}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setAge(e.target.value)}
                />
              </label>
              <label className="form-field">
                Instance label
                <input
                  value={label}
                  disabled={loading || prefillLoading}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </label>
            </div>

            {draftHint ? (
              <p className="form-hint" role="status">
                {draftHint}
              </p>
            ) : null}

            <div className="add-set-wizard__parts">
              <h3>Parts (optional)</h3>
              <p className="form-hint" style={{ marginTop: 0 }}>
                Spare/alternate Rebrickable lines are omitted. Add more rows for
                manual entry.
              </p>
              <div className="add-set-wizard__part-rows">
                {parts.map((row, index) => (
                  <div key={index} className="add-set-wizard__part-fields">
                    <label className="form-field">
                      Part #
                      <input
                        value={row.part_num}
                        disabled={loading || prefillLoading}
                        onChange={(e) =>
                          updatePart(index, { part_num: e.target.value })
                        }
                        placeholder="3024"
                      />
                    </label>
                    <label className="form-field">
                      Name
                      <input
                        value={row.part_name}
                        disabled={loading || prefillLoading}
                        onChange={(e) =>
                          updatePart(index, { part_name: e.target.value })
                        }
                      />
                    </label>
                    <label className="form-field">
                      Color id
                      <input
                        inputMode="numeric"
                        value={row.color_id}
                        disabled={loading || prefillLoading}
                        onChange={(e) =>
                          updatePart(index, { color_id: e.target.value })
                        }
                      />
                    </label>
                    <label className="form-field">
                      Color name
                      <input
                        value={row.color_name}
                        disabled={loading || prefillLoading}
                        onChange={(e) =>
                          updatePart(index, { color_name: e.target.value })
                        }
                      />
                    </label>
                    <label className="form-field">
                      Qty
                      <input
                        inputMode="numeric"
                        value={row.quantity}
                        disabled={loading || prefillLoading}
                        onChange={(e) =>
                          updatePart(index, { quantity: e.target.value })
                        }
                      />
                    </label>
                    <div className="add-set-wizard__part-remove-cell">
                      <button
                        type="button"
                        className="btn btn--ghost btn--small"
                        disabled={loading || prefillLoading}
                        onClick={() => removePartRow(index)}
                        aria-label={`Remove part row ${index + 1}`}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="add-set-wizard__part-actions">
                <button
                  type="button"
                  className="btn btn--secondary btn--small"
                  disabled={loading || prefillLoading}
                  onClick={addPartRow}
                >
                  Add part row
                </button>
              </div>
            </div>
          </>
        )}

        <div className="modal__actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={loading || prefillLoading}
            onClick={onClose}
          >
            Cancel
          </button>
          {!preview.catalog_exists && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={loading || prefillLoading}
              onClick={backToStepOne}
            >
              Back
            </button>
          )}
          <button
            type="submit"
            className="btn btn--primary"
            disabled={loading || prefillLoading}
          >
            {loading ? "Adding…" : "Add"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
