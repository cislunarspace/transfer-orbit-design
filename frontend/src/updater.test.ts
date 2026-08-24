import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  checkForAppUpdates,
  type UpdateInfo,
} from "./updater";

describe("updater module", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when no update is available", async () => {
    const mockCheck = vi.fn().mockResolvedValue(null);
    const result = await checkForAppUpdates(mockCheck);
    expect(result).toBeNull();
  });

  it("extracts version and body correctly when update is found", async () => {
    const mockUpdate = {
      version: "4.2.0",
      currentVersion: "4.1.2",
      body: "Release notes: fixed orbit rendering",
      downloadAndInstall: vi.fn(),
    };
    const mockCheck = vi.fn().mockResolvedValue(mockUpdate);

    const result = await checkForAppUpdates(mockCheck);
    expect(result).toEqual({
      version: "4.2.0",
      currentVersion: "4.1.2",
      body: "Release notes: fixed orbit rendering",
      rawUpdate: mockUpdate,
    });
  });

  it("handles errors gracefully and throws formatted updater error", async () => {
    const mockCheck = vi.fn().mockRejectedValue(new Error("Network offline"));
    await expect(checkForAppUpdates(mockCheck)).rejects.toThrow("Network offline");
  });

  it("downloads and installs update with progress tracking", async () => {
    const mockRawUpdate: any = {
      version: "4.2.0",
      currentVersion: "4.1.2",
      downloadAndInstall: vi.fn().mockImplementation(async (onEvent) => {
        if (onEvent) {
          onEvent({ event: "Started", data: { contentLength: 1000 } });
          onEvent({ event: "Progress", data: { chunkLength: 500 } });
          onEvent({ event: "Finished" });
        }
      }),
    };

    const updateInfo: UpdateInfo = {
      version: "4.2.0",
      currentVersion: "4.1.2",
      rawUpdate: mockRawUpdate,
    };

    const events: any[] = [];
    const { downloadAndApplyUpdate } = await import("./updater");
    await downloadAndApplyUpdate(updateInfo, (evt) => events.push(evt));

    expect(mockRawUpdate.downloadAndInstall).toHaveBeenCalled();
    expect(events.length).toBe(3);
    expect(events[0]).toEqual({ event: "Started", data: { contentLength: 1000 } });
    expect(events[1]).toEqual({ event: "Progress", data: { chunkLength: 500 } });
    expect(events[2]).toEqual({ event: "Finished" });
  });
});
