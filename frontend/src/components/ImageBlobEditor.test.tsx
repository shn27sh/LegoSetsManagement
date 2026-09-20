import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImageBlobEditor } from "./ImageBlobEditor";

describe("ImageBlobEditor", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens and closes a lightbox when enlargeOnClick is enabled", async () => {
    const user = userEvent.setup();
    render(
      <ImageBlobEditor
        imageUrl="/api/catalog-sets/10/image"
        alt="Set 6024"
        enlargeOnClick
        onUpload={vi.fn()}
        onDelete={vi.fn()}
        onUpdated={vi.fn()}
        disabled
      />,
    );

    await user.click(screen.getByRole("button", { name: /view larger: set 6024/i }));
    const dialog = screen.getByRole("dialog", { name: "Set 6024" });
    const enlarged = within(dialog).getByRole("img", { name: "Set 6024" });
    expect(enlarged).toHaveAttribute("src", "/api/catalog-sets/10/image");

    await user.click(enlarged);
    expect(screen.queryByRole("dialog", { name: "Set 6024" })).not.toBeInTheDocument();
  });
});
