import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UpdateModal } from "./UpdateModal";
import type { UpdateInfo } from "./updater";

describe("UpdateModal component", () => {
  const mockUpdateInfo: UpdateInfo = {
    version: "4.2.0",
    currentVersion: "4.1.2",
    body: "New features added",
    rawUpdate: {
      version: "4.2.0",
      currentVersion: "4.1.2",
      downloadAndInstall: vi.fn(),
    } as any,
  };

  it("renders modal when open is true", () => {
    render(
      <UpdateModal
        open={true}
        updateInfo={mockUpdateInfo}
        onClose={vi.fn()}
      />
    );
    expect(screen.getAllByText(/4\.2\.0/).length).toBeGreaterThan(0);
    expect(screen.getByText("New features added")).toBeDefined();
  });

  it("triggers download when clicking download button", async () => {
    const downloadAndInstall = vi.fn().mockImplementation(async (cb) => {
      cb({ event: "Started", data: { contentLength: 100 } });
      cb({ event: "Progress", data: { chunkLength: 100 } });
      cb({ event: "Finished" });
    });

    const info: UpdateInfo = {
      ...mockUpdateInfo,
      rawUpdate: {
        ...mockUpdateInfo.rawUpdate,
        downloadAndInstall,
      } as any,
    };

    render(
      <UpdateModal
        open={true}
        updateInfo={info}
        onClose={vi.fn()}
      />
    );

    const downloadBtn = screen.getByRole("button", { name: /立即更新|Update Now/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(downloadAndInstall).toHaveBeenCalled();
      expect(screen.getByRole("button", { name: /立即重启|Restart Now/i })).toBeDefined();
    });
  });
});
