import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MissingPartsReportPage } from "./MissingPartsReportPage";

vi.mock("../utils/missingPartsReportPdf", () => ({
  downloadMissingPartsPdf: vi.fn(),
}));

import { downloadMissingPartsPdf } from "../utils/missingPartsReportPdf";

const missingPartsFixture = {
  items: [
    {
      part_id: 10,
      part_num: "3001",
      part_name: "Brick 2x4",
      color_id: 0,
      color_name: "Black",
      quantity_missing_total: 3,
      element_ids: ["300100"],
      part_image_url: null,
      needed_sets: [
        {
          owned_set_id: 1,
          set_num: 6024,
          set_name: "Police Car",
          display_label: "Copy #1",
          quantity_missing: 2,
        },
        {
          owned_set_id: 2,
          set_num: 6024,
          set_name: "Police Car",
          display_label: "Copy #2",
          quantity_missing: 1,
        },
      ],
    },
  ],
  total: 1,
};

describe("MissingPartsReportPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.mocked(downloadMissingPartsPdf).mockReset();
  });

  it("loads all incomplete sets when no filter is provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => missingPartsFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/reports/missing"]}>
        <MissingPartsReportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Showing all incomplete sets/i)).toBeInTheDocument();
    expect(screen.getByText("Brick 2x4")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/6024 \(Police Car\) - Copy #1/)).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/reports\/missing-parts(?:\?limit=50&offset=0)?$/),
      undefined,
    );
  });

  it("passes owned_set_ids from the query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => missingPartsFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/reports/missing?owned_set_ids=1&owned_set_ids=3"]}>
        <MissingPartsReportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Showing 2 selected set copies/i)).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("owned_set_ids=1"),
      undefined,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("owned_set_ids=3"),
      undefined,
    );
  });

  it("exports all rows to PDF using the current filter", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("limit=200")) {
        return Promise.resolve({
          ok: true,
          json: async () => missingPartsFixture,
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => missingPartsFixture,
      } as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/reports/missing?owned_set_ids=1"]}>
        <MissingPartsReportPage />
      </MemoryRouter>,
    );

    await screen.findByText("Brick 2x4");
    await user.click(screen.getByRole("button", { name: /export pdf/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/limit=200/),
        undefined,
      );
      expect(downloadMissingPartsPdf).toHaveBeenCalledWith(
        missingPartsFixture.items,
        expect.objectContaining({
          filterLabel: expect.stringContaining("1 selected set copy"),
        }),
      );
    });
  });
});
