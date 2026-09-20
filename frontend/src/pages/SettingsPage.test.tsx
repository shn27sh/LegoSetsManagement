import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { AppModeProvider } from "../appMode/AppModeContext";
import { SettingsPage } from "./SettingsPage";

function renderSettings(initialMode: "view" | "investigate" | "edit" = "view") {
  localStorage.clear();
  return render(
    <AppModeProvider initialMode={initialMode}>
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </MemoryRouter>
    </AppModeProvider>,
  );
}

describe("SettingsPage", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("defaults to view mode selection", () => {
    renderSettings("view");
    expect(screen.getByLabelText(/view mode/i)).toBeChecked();
  });

  it("persists mode changes to localStorage", async () => {
    renderSettings("view");
    const user = userEvent.setup();
    await user.click(screen.getByLabelText(/investigate mode/i));
    expect(localStorage.getItem("lcm.appMode")).toBe("investigate");
    await user.click(screen.getByLabelText(/edit mode/i));
    expect(localStorage.getItem("lcm.appMode")).toBe("edit");
  });

  it("describes edit mode password note", () => {
    renderSettings("view");
    expect(
      screen.getByText(/will require a password in a future release/i),
    ).toBeInTheDocument();
  });
});
