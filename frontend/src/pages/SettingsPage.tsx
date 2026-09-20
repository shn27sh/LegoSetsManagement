import { useState } from "react";

import { APP_MODES, MODE_LABELS, type AppMode } from "../appMode/types";
import { useAppMode } from "../appMode/AppModeContext";

const MODE_DESCRIPTIONS: Record<AppMode, string> = {
  view:
    "Browse your collection, search, and reports. You cannot sync, import, or change any data.",
  investigate:
    "Mark copies as investigated and update missing part quantities and photos. Catalog, sync, and other edits are not available.",
  edit:
    "Full access: import, sync, add sets, edit catalog and inventory, and delete copies. Switching to Edit mode will require a password in a future release.",
};

export function SettingsPage() {
  const { mode, setMode } = useAppMode();
  const [pending, setPending] = useState(false);

  async function onModeChange(next: AppMode) {
    if (next === mode) {
      return;
    }
    setPending(true);
    try {
      await setMode(next);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="page">
      <header className="page__header">
        <h1>Settings</h1>
        <p className="page__lede">
          Choose how much you can change in the app. The selected mode is saved
          in this browser.
        </p>
      </header>

      <fieldset className="settings-mode" disabled={pending}>
        <legend className="settings-mode__legend">App mode</legend>
        {APP_MODES.map((option) => (
          <label key={option} className="settings-mode__option">
            <input
              type="radio"
              name="app-mode"
              value={option}
              checked={mode === option}
              onChange={() => void onModeChange(option)}
            />
            <span className="settings-mode__label">{MODE_LABELS[option]}</span>
            <span className="settings-mode__description">
              {MODE_DESCRIPTIONS[option]}
            </span>
          </label>
        ))}
      </fieldset>
    </section>
  );
}
