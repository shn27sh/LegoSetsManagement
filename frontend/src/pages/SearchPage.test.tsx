import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchPage } from "./SearchPage";
import { searchFixture } from "../test/fixtures";

describe("SearchPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("submits search and shows set results", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => searchFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/search query/i), "6024");
    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(await screen.findByText(/Sets \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/copy A/)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/search?q=6024&type=set"),
        undefined,
      );
    });
  });

  it("submits an Element ID search and shows element results", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => searchFixture,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText(/search type/i), "element");
    await user.type(screen.getByLabelText(/search query/i), "302400");
    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(await screen.findByText(/Element IDs \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/302400, 6252045/)).toBeInTheDocument();
    expect(screen.getByText(/Plate 1 x 1/)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/search?q=302400&type=element"),
        undefined,
      );
    });
  });
});
