import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportsPage } from "./ReportsPage";

const summaryFixture = {
  total_sets: 12,
  investigated_sets: 8,
  complete_sets: 5,
  total_parts: 4200,
  missing_parts: 37,
};

describe("ReportsPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads and renders summary stat cards", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => summaryFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("Set copies in collection")).toBeInTheDocument();
    expect(screen.getByText("4,200")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Incomplete sets/i })).toHaveAttribute(
      "href",
      "/reports/incomplete",
    );
    expect(screen.getByRole("link", { name: /Missing parts/i })).toHaveAttribute(
      "href",
      "/reports/missing",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/reports/summary"),
      undefined,
    );
  });
});
