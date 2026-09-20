import { KeyboardEvent, useState } from "react";

export function normalizePartAliases(
  partNum: string,
  aliases: readonly string[],
): string[] {
  const exclude = partNum.trim();
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of aliases) {
    const trimmed = raw.trim();
    if (!trimmed || trimmed === exclude || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    result.push(trimmed);
  }
  return result;
}

interface AliasChipEditorProps {
  partNum: string;
  aliases: string[];
  onChange: (aliases: string[]) => void;
  disabled?: boolean;
}

export function AliasChipEditor({
  partNum,
  aliases,
  onChange,
  disabled = false,
}: AliasChipEditorProps) {
  const [draft, setDraft] = useState("");

  function addDraft() {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === partNum.trim()) {
      setDraft("");
      return;
    }
    onChange(normalizePartAliases(partNum, [...aliases, trimmed]));
    setDraft("");
  }

  function removeAlias(alias: string) {
    onChange(aliases.filter((a) => a !== alias));
  }

  function onDraftKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      addDraft();
    }
  }

  return (
    <div className="alias-chip-editor">
      <p className="form-hint">Aliases (alternate part numbers)</p>
      <div className="alias-chip-editor__chips" aria-label="Part aliases">
        {aliases.length === 0 ? (
          <span className="alias-chip-editor__empty">None</span>
        ) : (
          aliases.map((alias) => (
            <span key={alias} className="alias-chip">
              {alias}
              <button
                type="button"
                className="alias-chip__remove"
                disabled={disabled}
                aria-label={`Remove alias ${alias}`}
                onClick={() => removeAlias(alias)}
              >
                ×
              </button>
            </span>
          ))
        )}
      </div>
      <div className="alias-chip-editor__add">
        <label className="sr-only" htmlFor="alias-draft">
          Add alias
        </label>
        <input
          id="alias-draft"
          value={draft}
          disabled={disabled}
          placeholder="Add alias"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onDraftKeyDown}
        />
        <button
          type="button"
          className="btn btn--small btn--secondary"
          disabled={disabled || !draft.trim()}
          onClick={addDraft}
        >
          Add alias
        </button>
      </div>
    </div>
  );
}
