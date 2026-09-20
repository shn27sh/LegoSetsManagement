import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportPage } from "./ImportPage";
import { renderWithAppMode } from "../test/renderWithAppMode";

function renderImport(mode: "view" | "edit" = "edit") {
  return renderWithAppMode(<ImportPage />, { mode });
}

type JobKind = "csv" | "rebrickable_sync" | "database";

function mockJobFetch(options: {
  kind: JobKind;
  result: Record<string, unknown>;
  failedSetsCsvPath?: string | null;
  runningFirst?: boolean;
}) {
  let polls = 0;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes("/imports/jobs/active")) {
      return {
        ok: false,
        status: 404,
        json: async () => ({ detail: "No active import job" }),
      } as Response;
    }
    if (url.includes("/imports/jobs") && init?.method === "POST") {
      return {
        ok: true,
        status: 202,
        json: async () => ({ job_id: "job-1", status: "queued" }),
      } as Response;
    }
    if (url.includes("/imports/jobs/job-1")) {
      polls += 1;
      if (options.runningFirst && polls === 1) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-1",
            kind: options.kind,
            status: "running",
            progress: { current: 1, total: 2, label: "Working" },
            result: null,
            error: null,
            failed_sets_csv_path: null,
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({
          job_id: "job-1",
          kind: options.kind,
          status: "completed",
          progress: null,
          result: options.result,
          error: null,
          failed_sets_csv_path: options.failedSetsCsvPath ?? null,
        }),
      } as Response;
    }
    if (url.includes("/imports/local-metadata")) {
      return {
        ok: true,
        json: async () => ({
          owned_set_ages_updated: 2,
          catalog_themes_updated: 1,
          age_values_available: 400,
          theme_values_available: 26000,
        }),
      } as Response;
    }
    return { ok: false, status: 404, statusText: "Not Found" } as Response;
  });
}

describe("ImportPage", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    try {
      sessionStorage.clear();
    } catch {
      /* jsdom may restrict storage in some environments */
    }
  });

  it("starts CSV import job and shows result", async () => {
    const fetchMock = mockJobFetch({
      kind: "csv",
      result: {
        instances_created: 2,
        catalog_stubs_created: 0,
        sets_fetched: 2,
        existing_sets_skipped: 0,
        skipped_existing_sets: [],
        sets_failed: [],
        errors: [],
        set_images_downloaded: 0,
        minifig_images_downloaded: 0,
        part_images_downloaded: 0,
        image_downloads_failed: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    const file = new File(["6024-1,9999-1"], "sets.csv", { type: "text/plain" });
    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /import csv/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/imports/jobs"),
        expect.objectContaining({ method: "POST" }),
      );
    });
    const requestInit = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    )?.[1] as RequestInit;
    const body = requestInit.body as FormData;
    expect(body.get("kind")).toBe("csv");
    expect(body.get("existing_set_mode")).toBe("skip");

    const csvStatus = await screen.findByRole("status");
    expect(csvStatus).toHaveTextContent("Created");
    expect(csvStatus).toHaveTextContent("2");
    expect(csvStatus).toHaveTextContent("instance");
  });

  it("shows skipped existing sets in the import report", async () => {
    const fetchMock = mockJobFetch({
      kind: "csv",
      result: {
        instances_created: 0,
        catalog_stubs_created: 0,
        sets_fetched: 0,
        existing_sets_skipped: 1,
        skipped_existing_sets: [{ token_index: 0, set_num: "6024-1" }],
        sets_failed: [],
        errors: [],
        set_images_downloaded: 0,
        minifig_images_downloaded: 0,
        part_images_downloaded: 0,
        image_downloads_failed: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    const file = new File(["6024-1"], "sets.csv", { type: "text/plain" });
    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /import csv/i }));

    expect(
      await screen.findByText(
        /not imported because .* already exist in your collection/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/6024-1/)).toBeInTheDocument();
  });

  it("starts database import job", async () => {
    const fetchMock = mockJobFetch({
      kind: "database",
      result: {
        sets_added: 1,
        sets_updated: 0,
        sets_skipped: 0,
        skipped_set_nums: [],
        instances_created: 1,
        parts_upserted: 2,
        inventory_lines_written: 3,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    const file = new File(["sqlite"], "other.db", {
      type: "application/octet-stream",
    });
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const databaseInput = fileInputs[1] as HTMLInputElement;
    await user.upload(databaseInput, file);
    await user.click(screen.getByRole("button", { name: /import database/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/imports/jobs"),
        expect.objectContaining({ method: "POST" }),
      );
    });
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = (postCall?.[1] as RequestInit).body as FormData;
    expect(body.get("kind")).toBe("database");
    expect(body.get("mode")).toBe("add_only_new");

    const dbStatus = await screen.findByRole("status");
    expect(dbStatus).toHaveTextContent("Added");
    expect(dbStatus).toHaveTextContent("1");
    expect(dbStatus).toHaveTextContent("parts");
  });

  it("passes add_and_update mode when selected", async () => {
    const fetchMock = mockJobFetch({
      kind: "database",
      result: {
        sets_added: 0,
        sets_updated: 2,
        sets_skipped: 0,
        skipped_set_nums: [],
        instances_created: 0,
        parts_upserted: 5,
        inventory_lines_written: 10,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    await user.click(
      screen.getByLabelText(/add new sets and update existing/i),
    );

    const file = new File(["sqlite"], "other.db", {
      type: "application/octet-stream",
    });
    const databaseInput = document.querySelectorAll(
      'input[type="file"]',
    )[1] as HTMLInputElement;
    await user.upload(databaseInput, file);
    await user.click(screen.getByRole("button", { name: /import database/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = (postCall?.[1] as RequestInit).body as FormData;
    expect(body.get("mode")).toBe("add_and_update");
  });

  it("passes selected image options to sync job", async () => {
    const fetchMock = mockJobFetch({
      kind: "rebrickable_sync",
      result: {
        sets_synced: 1,
        sets_failed: [],
        parts_upserted: 2,
        inventory_lines_written: 3,
        set_images_downloaded: 1,
        minifig_images_downloaded: 1,
        part_images_downloaded: 1,
        image_downloads_failed: [],
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    expect(screen.getByLabelText(/download set images/i)).not.toBeChecked();
    expect(screen.getByLabelText(/do not download images for parts/i)).toBeChecked();
    await user.click(screen.getByLabelText(/download set images/i));
    await user.click(screen.getByLabelText(/download part images for all sets/i));
    await user.click(screen.getByRole("button", { name: /sync entire collection/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/imports/jobs"),
        expect.objectContaining({ method: "POST" }),
      );
    });
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = (postCall?.[1] as RequestInit).body as FormData;
    expect(body.get("kind")).toBe("rebrickable_sync");
    const syncOptions = JSON.parse(String(body.get("sync_options")));
    expect(syncOptions).toEqual({
      download_set_images: true,
      part_image_download_mode: "all",
    });
    const syncStatus = await screen.findByRole("status");
    expect(syncStatus).toHaveTextContent("Downloaded");
    expect(syncStatus).toHaveTextContent("set image");
  });

  it("shows failed sets download link when job exposes csv path", async () => {
    const fetchMock = mockJobFetch({
      kind: "rebrickable_sync",
      result: {
        sets_synced: 0,
        sets_failed: [{ set_num: "9999-1", message: "HTTP 404" }],
        parts_upserted: 0,
        inventory_lines_written: 0,
        set_images_downloaded: 0,
        minifig_images_downloaded: 0,
        part_images_downloaded: 0,
        image_downloads_failed: [],
      },
      failedSetsCsvPath: "/data/failedSets.csv",
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();
    await user.click(screen.getByRole("button", { name: /sync entire collection/i }));

    expect(
      await screen.findByRole("link", { name: /download failed sets/i }),
    ).toHaveAttribute("href", expect.stringContaining("/imports/failed-sets.csv"));
  });

  it("can update missing ages and themes from local metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        owned_set_ages_updated: 2,
        catalog_themes_updated: 1,
        age_values_available: 400,
        theme_values_available: 26000,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    await user.click(screen.getByRole("button", { name: /update missing ages and themes/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/imports/local-metadata"),
        expect.objectContaining({ method: "POST" }),
      );
    });
    const metadataStatus = await screen.findByRole("status");
    expect(metadataStatus).toHaveTextContent("Updated");
    expect(metadataStatus).toHaveTextContent("2");
    expect(metadataStatus).toHaveTextContent("theme");
  });

  it("cancel import job sends DELETE", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/imports/jobs/active")) {
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "No active import job" }),
        } as Response;
      }
      if (url.includes("/imports/jobs") && init?.method === "POST") {
        return {
          ok: true,
          status: 202,
          json: async () => ({ job_id: "job-1", status: "queued" }),
        } as Response;
      }
      if (url.includes("/imports/jobs/job-1") && init?.method === "DELETE") {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-1",
            kind: "csv",
            status: "cancelled",
            progress: null,
            result: null,
            error: null,
            failed_sets_csv_path: null,
          }),
        } as Response;
      }
      if (url.includes("/imports/jobs/job-1")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job-1",
            kind: "csv",
            status: "running",
            progress: { current: 1, total: 3, label: "Working" },
            result: null,
            error: null,
            failed_sets_csv_path: null,
          }),
        } as Response;
      }
      return { ok: false, status: 404 } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderImport();

    const file = new File(["6024-1"], "sets.csv", { type: "text/plain" });
    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      file,
    );
    fireEvent.click(screen.getByRole("button", { name: /import csv/i }));
    await user.click(
      await screen.findByRole("button", { name: /cancel import/i }),
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/imports/jobs/job-1"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  it("hides import forms in view mode", () => {
    renderImport("view");
    expect(screen.getByText(/edit mode/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /import csv/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /import database/i }),
    ).not.toBeInTheDocument();
  });

});
