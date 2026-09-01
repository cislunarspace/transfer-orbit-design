import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import { AboutModal } from "./AboutModal";
import * as updaterModule from "./updater";

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn().mockResolvedValue("4.9.9"),
}));

vi.mock("@tauri-apps/plugin-opener", () => ({
  openUrl: vi.fn().mockResolvedValue(undefined),
}));

beforeEach(() => {
  vi.mocked(getVersion).mockClear();
  vi.mocked(openUrl).mockClear();
});

describe("AboutModal component", () => {
  it("缺省显示 Tauri 运行时真实版本（不再硬编码）", async () => {
    render(
      <AboutModal open={true} onClose={vi.fn()} onUpdateAvailable={vi.fn()} />
    );
    await waitFor(() => {
      expect(getVersion).toHaveBeenCalled();
      expect(screen.getByText(/v4\.9\.9/)).toBeDefined();
    });
  });

  it("currentVersion prop 注入时优先于运行时版本（测试口）", async () => {
    render(
      <AboutModal
        open={true}
        onClose={vi.fn()}
        onUpdateAvailable={vi.fn()}
        currentVersion="4.1.2"
      />
    );
    expect(screen.getByText(/v4\.1\.2/)).toBeDefined();
    expect(getVersion).not.toHaveBeenCalled();
    expect(screen.getByText(/tod - 地月转移轨道设计系统/)).toBeDefined();
  });

  it("checks for updates when user clicks check button", async () => {
    const mockUpdateInfo: updaterModule.UpdateInfo = {
      version: "4.2.0",
      currentVersion: "4.1.2",
      rawUpdate: {} as any,
    };
    vi.spyOn(updaterModule, "getBundleType").mockResolvedValue("appimage");
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

  it("deb 安装时更新按钮变为前往下载页：不调 updater，打开 Releases 页并提示", async () => {
    vi.spyOn(updaterModule, "getBundleType").mockResolvedValue("deb");
    // spyOn 对已 spy 的模块导出幂等返回同一 mock，清掉上一用例的调用记录再断言
    vi.spyOn(updaterModule, "checkForAppUpdates").mockClear();
    const onUpdateAvailable = vi.fn();
    const onClose = vi.fn();

    render(<AboutModal open={true} onClose={onClose} onUpdateAvailable={onUpdateAvailable} />);

    // bundleType 解析到 deb 后按钮文案切换
    const btn = await screen.findByRole("button", { name: /前往下载页|Open Download Page/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(openUrl).toHaveBeenCalledWith(updaterModule.RELEASES_PAGE_URL);
      expect(screen.getByText(/已打开版本发布页|releases page has been opened/i)).toBeDefined();
    });
    expect(updaterModule.checkForAppUpdates).not.toHaveBeenCalled();
    expect(onUpdateAvailable).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
