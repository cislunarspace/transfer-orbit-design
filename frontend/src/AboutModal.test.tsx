import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AboutModal } from "./AboutModal";
import * as updaterModule from "./updater";

describe("AboutModal component", () => {
  it("renders version and app information", () => {
    render(
      <AboutModal
        open={true}
        onClose={vi.fn()}
        onUpdateAvailable={vi.fn()}
        currentVersion="4.1.2"
      />
    );
    expect(screen.getByText(/4\.1\.2/)).toBeDefined();
    expect(screen.getByText(/tod - 地月转移轨道设计系统/)).toBeDefined();
  });

  it("checks for updates when user clicks check button", async () => {
    const mockUpdateInfo: updaterModule.UpdateInfo = {
      version: "4.2.0",
      currentVersion: "4.1.2",
      rawUpdate: {} as any,
    };
    vi.spyOn(updaterModule, "checkForAppUpdates").mockResolvedValue(mockUpdateInfo);
    const onUpdateAvailable = vi.fn();
    const onClose = vi.fn();

    render(
      <AboutModal
        open={true}
        onClose={onClose}
        onUpdateAvailable={onUpdateAvailable}
      />
    );

    const checkBtn = screen.getByRole("button", { name: /检查更新|Check for Updates/i });
    fireEvent.click(checkBtn);

    await waitFor(() => {
      expect(updaterModule.checkForAppUpdates).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
      expect(onUpdateAvailable).toHaveBeenCalledWith(mockUpdateInfo);
    });
  });
});
