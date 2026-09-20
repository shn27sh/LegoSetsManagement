import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IncompleteSetsReportPage } from "./IncompleteSetsReportPage";
import { MissingPartsReportPage } from "./MissingPartsReportPage";

const incompleteFixture = {
  items: [
    {
      id: 1,
      set_num: 6024,
      name: "Police Car",
      display_label: "Copy #1",
      investigated: false,
      missing_line_count: 1,
      missing_parts_total: 2,
      missing_lines: [
        {
          part_id: 10,
          part_num: "3001",
          part_name: "Brick 2x4",
          color_id: 0,
          color_name: "Black",
          quantity_missing: 2,
          element_ids: ["300100"],
          part_image_url: null,
        },
      ],
    },
    {
      id: 2,
      set_num: 6030,
      name: "Fire Car",
      display_label: "Copy #1",
      investigated: true,
      missing_line_count: 1,
      missing_parts_total: 1,
      missing_lines: [],
    },
  ],
  total: 2,
};

describe("IncompleteSetsReportPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads incomplete sets with collapsed details by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => incompleteFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <IncompleteSetsReportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/6024 \(Police Car\) - Copy #1/)).toBeInTheDocument();
    expect(screen.getByText(/1 line, 2 missing parts/)).toBeInTheDocument();
    const details = screen.getByText(/6024 \(Police Car\) - Copy #1/).closest("details");
    expect(details).toBeTruthy();
    expect((details as HTMLDetailsElement).open).toBe(false);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/reports/incomplete-sets"),
      undefined,
    );
  });

  it("expands details to show missing lines", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => incompleteFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <IncompleteSetsReportPage />
      </MemoryRouter>,
    );

    await screen.findByText(/6024 \(Police Car\) - Copy #1/);
    await user.click(screen.getByText(/1 line, 2 missing parts/));

    expect(await screen.findByText("Brick 2x4")).toBeInTheDocument();
    expect(screen.getByText("300100")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("navigates to all missing parts when none are selected", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => incompleteFixture,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/reports/incomplete"]}>
        <Routes>
          <Route path="/reports/incomplete" element={<IncompleteSetsReportPage />} />
          <Route path="/reports/missing" element={<MissingPartsReportPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText(/6024 \(Police Car\) - Copy #1/);
    await user.click(screen.getByRole("button", { name: /Missing parts report/i }));

    expect(await screen.findByText(/Showing all incomplete sets/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/reports\/missing-parts(?:\?limit=50&offset=0)?$/),
        undefined,
      );
    });
  });

  it("navigates with owned_set_ids for a partial selection", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => incompleteFixture,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/reports/incomplete"]}>
        <Routes>
          <Route path="/reports/incomplete" element={<IncompleteSetsReportPage />} />
          <Route path="/reports/missing" element={<MissingPartsReportPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText(/6024 \(Police Car\) - Copy #1/);
    await user.click(
      screen.getByLabelText(/Select 6024 \(Police Car\) - Copy #1/i),
    );
    await user.click(screen.getByRole("button", { name: /Missing parts report/i }));

    expect(await screen.findByText(/Showing 1 selected set copy/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("owned_set_ids=1"),
        undefined,
      );
    });
  });
});
