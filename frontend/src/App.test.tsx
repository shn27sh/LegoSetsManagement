import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { setCopyListFixture } from "./test/fixtures";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the application title and collection nav", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => setCopyListFixture,
      } as Response),
    );

    render(<App />);

    expect(
      screen.getByRole("link", { name: /lego collection manager/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /your sets/i }),
    ).toBeInTheDocument();
  });
});
