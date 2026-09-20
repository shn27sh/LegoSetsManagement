import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SetCopyListResponse } from "../api/types";
import { SetsListPage } from "./SetsListPage";
import { setCopyListFixture } from "../test/fixtures";
import { AppModeProvider } from "../appMode/AppModeContext";
import type { AppMode } from "../appMode/types";

function LocationProbe() {
  const location = useLocation();
  return (
    <div data-testid="location">{`${location.pathname}${location.search}`}</div>
  );
}

function renderPage(
  initialEntries: string[] = ["/"],
  mode: AppMode = "edit",
) {
  return render(
    <AppModeProvider initialMode={mode}>
      <MemoryRouter initialEntries={initialEntries}>
        <SetsListPage />
        <LocationProbe />
      </MemoryRouter>
    </AppModeProvider>,
  );
}

function okJson(body: unknown): Response {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

function makeManySetCopies(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    ...setCopyListFixture.items[0],
    id: index + 1,
    label: `copy ${index + 1}`,
    display_label: `copy ${index + 1}`,
    name: `Set item ${index + 1}`,
  }));
}

function mockCollectionFetch(listBody: unknown = setCopyListFixture) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/owned-sets/theme-options")) {
      return Promise.resolve(okJson({ themes: ["Space", "Town"] }));
    }
    if (url.includes("/owned-sets")) {
      const body = listBody as SetCopyListResponse;
      const urlObj = new URL(url, "http://local.test");
      const offset = Number(urlObj.searchParams.get("offset") ?? "0");
      const limit = Number(urlObj.searchParams.get("limit") ?? "50");
      return Promise.resolve(
        okJson({
          total: body.total,
          items: body.items.slice(offset, offset + limit),
        }),
      );
    }
    return Promise.resolve(okJson(listBody));
  });
}

function listFetchCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls
    .map(([input]) => String(input))
    .filter((url) => url.includes("/owned-sets?") || url.endsWith("/owned-sets"));
}

describe("SetsListPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders display label before set number", async () => {
    vi.stubGlobal("fetch", mockCollectionFetch());

    renderPage();

    expect(await screen.findByText(/6024 \(Police Car\) - copy A/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /make a copy/i })).toHaveLength(2);
    expect(screen.queryByText(/sync:/i)).not.toBeInTheDocument();
  });

  it("opens make a copy dialog and posts on confirm", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/owned-sets/theme-options")) {
        return Promise.resolve(okJson({ themes: ["Town"] }));
      }
      if (url.includes("/duplicate-preview")) {
        return Promise.resolve(okJson({
          source_owned_set_id: 1,
          set_num: 6024,
          set_name: "Police Car",
          existing_copy_count: 2,
          suggested_label: "Copy #3",
        }));
      }
      if (url.includes("/duplicate")) {
        return Promise.resolve(okJson({
          ...setCopyListFixture.items[0],
          id: 9,
          label: "Copy #3",
          display_label: "Copy #3",
          copy_index: 3,
          duplicated_from_owned_set_id: 1,
        }));
      }
      return Promise.resolve(okJson(setCopyListFixture));
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();

    const makeCopyButtons = await screen.findAllByRole("button", {
      name: /make a copy/i,
    });
    await user.click(makeCopyButtons[0]!);

    expect(
      await screen.findByText(/creating a copy of lego set number/i),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Copy #3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /create a copy/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/owned-sets/1/duplicate"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ label: "Copy #3" }),
        }),
      );
    });
  });

  it("passes sort/theme/missing filters and can group by theme and age", async () => {
    const fetchMock = mockCollectionFetch();
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/6024 \(Police Car\) - copy A/);

    const initialListCalls = listFetchCalls(fetchMock).length;
    await user.selectOptions(screen.getByLabelText(/sort by/i), "theme");
    expect(listFetchCalls(fetchMock).length).toBe(initialListCalls);
    for (const url of listFetchCalls(fetchMock)) {
      expect(url).not.toContain("sort_by=theme");
    }

    await user.click(screen.getByRole("checkbox", { name: "All" }));
    await user.click(screen.getByRole("checkbox", { name: "Space" }));
    await user.click(screen.getByRole("checkbox", { name: "Town" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/theme=Space.*theme=Town|theme=Town.*theme=Space/),
        undefined,
      );
    });

    await user.click(screen.getByLabelText(/missing parts only/i));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("missing_only=true"),
        undefined,
      );
    });

    await user.click(screen.getByRole("checkbox", { name: "None" }));
    await user.click(screen.getByRole("checkbox", { name: "Theme" }));
    await user.click(screen.getByRole("checkbox", { name: "Age" }));
    expect(screen.getByRole("heading", { name: "Town" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age unknown" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age 8" })).toBeInTheDocument();
  });

  it("shows pagination when grouping a large filtered collection", async () => {
    const manyItems = makeManySetCopies(65);
    const fetchMock = mockCollectionFetch({ total: 65, items: manyItems });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();
    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 1) - copy 1",
      }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "None" }));
    await user.click(screen.getByRole("checkbox", { name: "Theme" }));

    expect(screen.getByText(/page 1 of 4/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 21) - copy 21",
      }),
    ).toBeInTheDocument();
  });

  it("groups first then sorts groups and items within groups", async () => {
    const groupedFixture = {
      total: 3,
      items: [
        {
          ...setCopyListFixture.items[0],
          id: 1,
          theme_name: "Town",
          name: "Zebra Set",
          age: 8,
        },
        {
          ...setCopyListFixture.items[1],
          id: 2,
          theme_name: "Space",
          name: "Alpha Set",
          age: 4,
        },
        {
          ...setCopyListFixture.items[0],
          id: 3,
          theme_name: "Town",
          name: "Beta Set",
          age: 4,
        },
      ],
    };
    const fetchMock = mockCollectionFetch(groupedFixture);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/Zebra Set/);

    await user.click(screen.getByRole("checkbox", { name: "None" }));
    await user.click(screen.getByRole("checkbox", { name: "Theme" }));
    await user.selectOptions(screen.getByLabelText(/sort by/i), "name");
    await user.selectOptions(screen.getByLabelText(/direction/i), "asc");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenLastCalledWith(
        expect.not.stringContaining("sort_by=name"),
        undefined,
      );
    });

    const categoryHeadings = Array.from(
      document.querySelectorAll(".set-category > h2"),
    ).map((heading) => heading.textContent);
    expect(categoryHeadings).toEqual(["Space", "Town"]);

    const townCards = screen
      .getByRole("heading", { name: "Town" })
      .closest("section")!
      .querySelectorAll(".set-card__title");
    expect(Array.from(townCards).map((node) => node.textContent)).toEqual([
      expect.stringContaining("Beta Set"),
      expect.stringContaining("Zebra Set"),
    ]);
  });

  it("loads theme filter options from the whole collection", async () => {
    const fetchMock = mockCollectionFetch();
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByRole("checkbox", { name: "Space" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Town" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "None" })).toBeInTheDocument();
  });

  it("shows direct page navigation when there are more than two pages", async () => {
    const manyItems = makeManySetCopies(65);
    const fetchMock = mockCollectionFetch({ total: 65, items: manyItems });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage(["/?page=2"]);

    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 21) - copy 21",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "6024 (Set item 1) - copy 1" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/page 2 of 4/i)).toBeInTheDocument();
    expect(listFetchCalls(fetchMock)).toEqual([
      expect.stringContaining("limit=200"),
    ]);

    const pageInput = screen.getByLabelText(/page number/i);
    await user.clear(pageInput);
    await user.type(pageInput, "99");
    await user.click(screen.getByRole("button", { name: /go to page #/i }));

    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 61) - copy 61",
      }),
    ).toBeInTheDocument();
    expect(listFetchCalls(fetchMock)).toHaveLength(1);

    await user.clear(pageInput);
    await user.type(pageInput, "0");
    await user.click(screen.getByRole("button", { name: /go to page #/i }));

    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 1) - copy 1",
      }),
    ).toBeInTheDocument();
    expect(listFetchCalls(fetchMock)).toHaveLength(1);
  });

  it("keeps the current page in the collection URL before opening a set", async () => {
    const manyItems = makeManySetCopies(65);
    const fetchMock = mockCollectionFetch({ total: 65, items: manyItems });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 1) - copy 1",
      }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /next/i }));

    expect(
      await screen.findByRole("heading", {
        name: "6024 (Set item 21) - copy 21",
      }),
    ).toBeInTheDocument();
    expect(listFetchCalls(fetchMock)).toHaveLength(1);
    expect(screen.getByTestId("location")).toHaveTextContent("/?page=2");
    expect(screen.getByRole("link", { name: /Set item 21/i })).toHaveAttribute(
      "href",
      "/sets/21",
    );
  });

  it("loads the full filtered collection for client-side sort and group", async () => {
    const manyItems = makeManySetCopies(250);
    const fetchMock = mockCollectionFetch({ total: 250, items: manyItems });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByText(/page 1 of 13/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(listFetchCalls(fetchMock)).toHaveLength(2);
    });
    expect(listFetchCalls(fetchMock)[1]).toContain("offset=200");
  });

  it("defaults to theme grouping and set number sorting", async () => {
    vi.stubGlobal("fetch", mockCollectionFetch());

    renderPage();

    await screen.findByText(/6024 \(Police Car\) - copy A/);
    expect(screen.getByLabelText(/sort by/i)).toHaveValue("set_num");
    expect(screen.getByRole("heading", { name: "Town" })).toBeInTheDocument();
  });

  it("persists sort and group preferences to localStorage", async () => {
    vi.stubGlobal("fetch", mockCollectionFetch());

    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/6024 \(Police Car\) - copy A/);

    await user.selectOptions(screen.getByLabelText(/sort by/i), "name");
    await user.selectOptions(screen.getByLabelText(/direction/i), "desc");
    await user.click(screen.getByRole("checkbox", { name: "None" }));
    await user.click(screen.getByRole("checkbox", { name: "Age" }));

    expect(localStorage.getItem("lcm.setsListPreferences")).toBe(
      JSON.stringify({
        sortBy: "name",
        sortDir: "desc",
        groupBy: ["age"],
        investigatedFilter: "all",
        themeFilter: [],
        missingOnly: false,
      }),
    );
  });

  it("persists filter preferences to localStorage", async () => {
    vi.stubGlobal("fetch", mockCollectionFetch());

    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/6024 \(Police Car\) - copy A/);

    await user.selectOptions(screen.getByLabelText(/investigation/i), "true");
    await user.click(screen.getByRole("checkbox", { name: "Town" }));
    await user.click(screen.getByLabelText("Missing parts only"));

    expect(localStorage.getItem("lcm.setsListPreferences")).toBe(
      JSON.stringify({
        sortBy: "set_num",
        sortDir: "asc",
        groupBy: ["theme"],
        investigatedFilter: "true",
        themeFilter: ["Town"],
        missingOnly: true,
      }),
    );
  });

  it("restores sort and group preferences from localStorage", async () => {
    localStorage.setItem(
      "lcm.setsListPreferences",
      JSON.stringify({
        sortBy: "theme",
        sortDir: "desc",
        groupBy: ["theme", "age"],
        investigatedFilter: "all",
        themeFilter: [],
        missingOnly: false,
      }),
    );
    vi.stubGlobal("fetch", mockCollectionFetch());

    renderPage();

    await screen.findByText(/6024 \(Police Car\) - copy A/);
    expect(screen.getByLabelText(/sort by/i)).toHaveValue("theme");
    expect(screen.getByLabelText(/direction/i)).toHaveValue("desc");
    expect(screen.getByRole("heading", { name: "Town" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age 8" })).toBeInTheDocument();
  });

  it("restores filter preferences from localStorage", async () => {
    localStorage.setItem(
      "lcm.setsListPreferences",
      JSON.stringify({
        sortBy: "set_num",
        sortDir: "asc",
        groupBy: ["theme"],
        investigatedFilter: "false",
        themeFilter: ["Town"],
        missingOnly: true,
      }),
    );
    vi.stubGlobal("fetch", mockCollectionFetch());

    renderPage();

    await screen.findByText(/6024 \(Police Car\) - copy A/);
    expect(screen.getByLabelText(/investigation/i)).toHaveValue("false");
    expect(screen.getByLabelText("Missing parts only")).toBeChecked();
  });

  it("disables make a copy and hides add set in view mode", async () => {
    vi.stubGlobal("fetch", mockCollectionFetch());

    renderPage(["/"], "view");

    expect(await screen.findByText(/6024 \(Police Car\) - copy A/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^add set$/i })).not.toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: /make a copy/i })) {
      expect(button).toBeDisabled();
    }
  });

  it("applies pending theme filter renames before the first list fetch", async () => {
    localStorage.setItem(
      "lcm.setsListPreferences",
      JSON.stringify({
        sortBy: "set_num",
        sortDir: "asc",
        groupBy: ["theme"],
        investigatedFilter: "all",
        themeFilter: ["Town"],
        missingOnly: false,
      }),
    );
    sessionStorage.setItem(
      "lcm.pendingThemeFilterSync",
      JSON.stringify([{ from: "Town", to: "Classic Town", scope: "all" }]),
    );

    const classicItem = {
      ...setCopyListFixture.items[0]!,
      id: 99,
      name: "Classic Car",
      theme_name: "Classic Town",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/owned-sets/theme-options")) {
        return Promise.resolve(okJson({ themes: ["Classic Town", "Town"] }));
      }
      if (url.includes("theme=Classic+Town") || url.includes("theme=Classic%20Town")) {
        return Promise.resolve(okJson({ total: 1, items: [classicItem] }));
      }
      if (url.includes("theme=Town")) {
        return Promise.resolve(okJson({ total: 0, items: [] }));
      }
      return Promise.resolve(okJson(setCopyListFixture));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(
      await screen.findByText(/6024 \(Classic Car\) - copy A/),
    ).toBeInTheDocument();
    expect(
      listFetchCalls(fetchMock).some(
        (url) => url.includes("theme=Classic+Town") || url.includes("theme=Classic%20Town"),
      ),
    ).toBe(true);
    expect(listFetchCalls(fetchMock).some((url) => url.includes("theme=Town"))).toBe(
      false,
    );
  });

  it("ignores stale list responses when the theme filter changes quickly", async () => {
    const spaceItem = {
      ...setCopyListFixture.items[0]!,
      id: 99,
      name: "Space Ship",
      theme_name: "Space",
      display_label: "Space copy",
      label: "Space copy",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/owned-sets/theme-options")) {
        return Promise.resolve(okJson({ themes: ["Space", "Town"] }));
      }
      if (url.includes("theme=Space")) {
        return Promise.resolve(okJson({ total: 1, items: [spaceItem] }));
      }
      if (url.includes("theme=Town")) {
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve(
              okJson({
                total: 1,
                items: [setCopyListFixture.items[0]!],
              }),
            );
          }, 150);
        });
      }
      return Promise.resolve(okJson(setCopyListFixture));
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/6024 \(Police Car\) - copy A/);

    await user.click(screen.getByRole("checkbox", { name: "All" }));
    await user.click(screen.getByRole("checkbox", { name: "Town" }));
    await user.click(screen.getByRole("checkbox", { name: "Space" }));

    expect(
      await screen.findByText(/6024 \(Space Ship\) - Space copy/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/6024 \(Police Car\) - copy A/)).not.toBeInTheDocument();

    await waitFor(
      () => {
        expect(screen.queryByText(/6024 \(Police Car\) - copy A/)).not.toBeInTheDocument();
      },
      { timeout: 500 },
    );
  });
});
