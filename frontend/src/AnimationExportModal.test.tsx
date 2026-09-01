// 导出动画设置弹窗（#455）：模式（自转/时间轴播放）与时长（2–30 秒），
// 确认携带参数回调、取消无副作用；量程不可用时时间轴模式禁用并注明原因。
// Export-animation settings modal (#455): mode (spin / timeline playback) and
// duration (2–30 s); confirm reports the options, cancel has no side effects;
// with no timeline range the timeline mode is disabled with a reason.

import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { AnimationExportModal } from "./AnimationExportModal";

beforeAll(() => {
  const mm = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  });
  vi.stubGlobal("matchMedia", mm);
  window.matchMedia = mm as unknown as typeof window.matchMedia;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

function setup(timeRange: [number, number] | null = [0, 10_000_000]) {
  const onClose = vi.fn();
  const onExport = vi.fn();
  render(
    <AnimationExportModal open timeRange={timeRange} onClose={onClose} onExport={onExport} />,
  );
  return { onClose, onExport };
}

describe("AnimationExportModal（#455）", () => {
  it("默认自转模式、8 秒；确认携带参数回调", () => {
    const { onExport } = setup();
    expect((screen.getByRole("radio", { name: "自转" }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "开始导出" }));
    expect(onExport).toHaveBeenCalledWith({ mode: "spin", durationSec: 8 });
  });

  it("切换到时间轴播放后确认携带 timeline 模式", () => {
    const { onExport } = setup();
    fireEvent.click(screen.getByRole("radio", { name: "时间轴播放" }));
    fireEvent.click(screen.getByRole("button", { name: "开始导出" }));
    expect(onExport).toHaveBeenCalledWith({ mode: "timeline", durationSec: 8 });
  });

  it("量程不可用：时间轴模式禁用并提示原因，确认只能携带自转", () => {
    const { onExport } = setup(null);
    expect((screen.getByRole("radio", { name: "时间轴播放" }) as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText(/带历元/)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "开始导出" }));
    expect(onExport).toHaveBeenCalledWith({ mode: "spin", durationSec: 8 });
  });

  it("取消只关弹窗，不触发导出", () => {
    const { onClose, onExport } = setup();
    fireEvent.click(screen.getByRole("button", { name: "取 消" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onExport).not.toHaveBeenCalled();
  });

  it("时长滑到 15 秒后确认携带 15", () => {
    const { onExport } = setup();
    // antd Slider 手柄是 role=slider，键盘步进（step=1）：8 + 7 次右移 = 15
    // The antd Slider handle is role=slider; keyboard steps (step=1): 8 + 7 rights = 15.
    const handle = screen.getByRole("slider");
    for (let i = 0; i < 7; i++) {
      fireEvent.keyDown(handle, { key: "ArrowRight", keyCode: 39 });
    }
    expect(handle.getAttribute("aria-valuenow")).toBe("15");
    fireEvent.click(screen.getByRole("button", { name: "开始导出" }));
    expect(onExport).toHaveBeenCalledWith({ mode: "spin", durationSec: 15 });
  });
});
