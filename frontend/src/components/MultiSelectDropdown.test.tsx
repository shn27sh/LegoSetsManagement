import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { MultiSelectDropdown } from "./MultiSelectDropdown";

describe("MultiSelectDropdown", () => {
  afterEach(() => {
    cleanup();
  });

  it("closes when clicking outside", async () => {
    const user = userEvent.setup();
    render(
      <>
        <MultiSelectDropdown label="Theme" summary="All">
          <label className="checkbox">
            <input type="checkbox" />
            Space
          </label>
        </MultiSelectDropdown>
        <button type="button">Outside</button>
      </>,
    );

    const dropdown = screen.getByLabelText("Theme") as HTMLDetailsElement;
    await user.click(within(dropdown).getByText("All"));
    expect(dropdown.open).toBe(true);

    await user.click(screen.getByRole("button", { name: "Outside" }));
    expect(dropdown.open).toBe(false);
  });

  it("stays open when clicking inside the menu", async () => {
    const user = userEvent.setup();
    render(
      <MultiSelectDropdown label="Theme" summary="All">
        <label className="checkbox">
          <input type="checkbox" />
          Space
        </label>
      </MultiSelectDropdown>,
    );

    const dropdown = screen.getByLabelText("Theme") as HTMLDetailsElement;
    await user.click(within(dropdown).getByText("All"));
    await user.click(screen.getByRole("checkbox", { name: "Space" }));

    expect(dropdown.open).toBe(true);
  });
});
