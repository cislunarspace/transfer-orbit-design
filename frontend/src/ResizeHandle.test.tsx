// ResizeHandle 单测（#454）：拖拽方向随边沿、宽度钳制、松手才上报终值、
// 松手后拖拽失效。行为对齐助手边栏既有手感（实时跟手、松手持久化）。
// ResizeHandle unit tests (#454): drag direction follows the edge, width is
// clamped, the final width reports once on release, and drags after release
// are inert. Behavior matches the assistant sidebar's existing feel (live
// tracking, persist on release).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { ResizeHandle } from "./ResizeHandle";

function setup(edge: "left" | "right", width = 280) {
  const onResize = vi.fn();
  const onResizeEnd = vi.fn();
  const { container } = render(
    <ResizeHandle edge={edge} width={width} min={220} max={420} onResize={onResize} onResizeEnd={onResizeEnd} />,
  );
  const handle = container.firstChild as HTMLElement;
  return { onResize, onResizeEnd, handle };
}

afterEach(cleanup);

describe("ResizeHandle（#454）", () => {
  it("右缘手柄：向右拖宽度增大，实时上报钳制后的宽度", () => {
    const { onResize, handle } = setup("right");
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(window, { clientX: 130 });
    expect(onResize).toHaveBeenLastCalledWith(310);
  });

  it("左缘手柄（右栏）：向左拖宽度增大", () => {
    const { onResize, handle } = setup("left");
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(window, { clientX: 70 });
    expect(onResize).toHaveBeenLastCalledWith(310);
  });

  it("越界钳制到 min/max", () => {
    const { onResize, handle } = setup("right");
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(window, { clientX: 400 });
    expect(onResize).toHaveBeenLastCalledWith(420);
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(window, { clientX: 0 });
    expect(onResize).toHaveBeenLastCalledWith(220);
  });

  it("松手才上报终值（拖拽过程不调 onResizeEnd），松手后拖拽失效", () => {
    const { onResize, onResizeEnd, handle } = setup("right");
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(window, { clientX: 130 });
    expect(onResizeEnd).not.toHaveBeenCalled();
    fireEvent.mouseUp(window, { clientX: 130 });
    expect(onResizeEnd).toHaveBeenCalledTimes(1);
    expect(onResizeEnd).toHaveBeenLastCalledWith(310);
    // 松手后移动不再上报
    // Moves after release report nothing.
    fireEvent.mouseMove(window, { clientX: 200 });
    expect(onResize).toHaveBeenCalledTimes(1);
    expect(onResizeEnd).toHaveBeenCalledTimes(1);
  });

  it("未移动直接松手：终值为起始宽度", () => {
    const { onResizeEnd, handle } = setup("right", 300);
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseUp(window, { clientX: 100 });
    expect(onResizeEnd).toHaveBeenLastCalledWith(300);
  });
});

// —— 折叠态持久化（#462）：仅 "1" 视为折叠，缺失/其他值回落展开 ——
// Collapsed-state persistence (#462): only "1" counts as collapsed; missing
// or other values fall back to expanded.

import { loadPanelCollapsed } from "./ResizeHandle";

describe("loadPanelCollapsed（#462）", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("\"1\" 视为折叠", () => {
    localStorage.setItem("tod-x-collapsed", "1");
    expect(loadPanelCollapsed("tod-x-collapsed")).toBe(true);
  });

  it("\"0\"/缺失/非法值回落展开", () => {
    localStorage.setItem("tod-x-collapsed", "0");
    expect(loadPanelCollapsed("tod-x-collapsed")).toBe(false);
    expect(loadPanelCollapsed("tod-x-collapsed")).toBe(false); // 显式展开
    localStorage.removeItem("tod-x-collapsed");
    expect(loadPanelCollapsed("tod-x-collapsed")).toBe(false);
    localStorage.setItem("tod-x-collapsed", "yes");
    expect(loadPanelCollapsed("tod-x-collapsed")).toBe(false);
  });
});
