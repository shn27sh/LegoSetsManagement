import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  buildSyncJobOptions,
  pollImportJobUntilTerminal,
  startCsvImportJob,
} from "./importJobs";

describe("buildSyncJobOptions", () => {
  it("defaults download_set_images to false", () => {
    expect(JSON.parse(buildSyncJobOptions({}))).toEqual({
      download_set_images: false,
      part_image_download_mode: "none",
    });
  });

  it("includes owned_set_ids when provided", () => {
    expect(
      JSON.parse(
        buildSyncJobOptions({
          owned_set_ids: [42],
          download_set_images: true,
          part_image_download_mode: "all",
        }),
      ),
    ).toEqual({
      owned_set_ids: [42],
      download_set_images: true,
      part_image_download_mode: "all",
    });
  });
});

describe("startCsvImportJob", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("surfaces 409 when another job is active", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        statusText: "Conflict",
        json: async () => ({ detail: "Another import job is already running" }),
      } as Response),
    );

    const file = new File(["6024-1"], "sets.csv", { type: "text/plain" });
    await expect(startCsvImportJob(file)).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "Another import job is already running",
    });
    await expect(startCsvImportJob(file)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("pollImportJobUntilTerminal", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("polls until status is completed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: "j1",
          kind: "csv",
          status: "running",
          progress: { current: 1, total: 2, label: "x" },
          result: null,
          error: null,
          failed_sets_csv_path: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: "j1",
          kind: "csv",
          status: "completed",
          progress: null,
          result: { instances_created: 1 },
          error: null,
          failed_sets_csv_path: null,
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const onStatus = vi.fn();
    const promise = pollImportJobUntilTerminal("j1", {
      onStatus,
      pollIntervalMs: 100,
    });
    await vi.runAllTimersAsync();
    const final = await promise;

    expect(final.status).toBe("completed");
    expect(onStatus).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/imports/jobs/j1"),
      undefined,
    );
  });
});
