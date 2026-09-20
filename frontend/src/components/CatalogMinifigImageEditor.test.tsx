import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CatalogMinifigImageEditor } from "./CatalogMinifigImageEditor";

describe("CatalogMinifigImageEditor", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens and closes a lightbox when the minifigure image is clicked", async () => {
    const user = userEvent.setup();
    render(
      <CatalogMinifigImageEditor
        catalogMinifigId={12}
        imageUrl="/api/catalog-minifigs/12/image"
        minifigNum="cop01"
        name="Police Officer"
        onUpdated={vi.fn()}
        disabled
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: /view larger: minifigure cop01 — police officer/i,
      }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "Minifigure cop01 — Police Officer",
    });
    const enlarged = within(dialog).getByRole("img", {
      name: "Minifigure cop01 — Police Officer",
    });
    expect(enlarged).toHaveAttribute("src", "/api/catalog-minifigs/12/image");

    await user.click(enlarged);
    expect(
      screen.queryByRole("dialog", {
        name: "Minifigure cop01 — Police Officer",
      }),
    ).not.toBeInTheDocument();
  });
});
