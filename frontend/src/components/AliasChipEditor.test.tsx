import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AliasChipEditor, normalizePartAliases } from "./AliasChipEditor";

describe("normalizePartAliases", () => {
  it("excludes canonical part number and dedupes", () => {
    expect(normalizePartAliases("3024", ["3024b", "3024", "3024b"])).toEqual([
      "3024b",
    ]);
  });
});

describe("AliasChipEditor", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders chips and adds a new alias", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <AliasChipEditor
        partNum="3024"
        aliases={["3024b"]}
        onChange={onChange}
      />,
    );

    expect(screen.getByText("3024b")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText(/add alias/i), "3024pr");
    await user.click(screen.getByRole("button", { name: /add alias/i }));

    expect(onChange).toHaveBeenCalledWith(["3024b", "3024pr"]);
  });

  it("removes a chip", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <AliasChipEditor
        partNum="3024"
        aliases={["3024b", "3024pr"]}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /remove alias 3024b/i }));

    expect(onChange).toHaveBeenCalledWith(["3024pr"]);
  });
});
