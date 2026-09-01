// App 布局收缩契约回归（#462 后续：折叠再展开把助手边栏顶出窗口）。
// 复现路径：右栏是 flex:1 的 flex 子项，WebGL 画布被 renderer.setSize 写上
// px 内联宽度；flex 子项默认 min-width:auto，画布宽即成为右栏的 min-content
// 下限。折叠左栏时画布变宽，再展开时右栏窄不下去——整排超出 100vw，助手
// 边栏被推出窗口，且画布容器等不到变窄、ResizeObserver 不再触发，永久卡死。
// 修复：右栏 minWidth:0，把宽度交回 flex 分配，ResizeObserver 随后缩回画布。
// jsdom 没有布局引擎，无法端到端复现溢出；此处钉住样式契约，真实布局行为
// 已用 headless Chrome 的最小复现页验证（未修复 OVERFLOW / 修复后 ok）。
// App layout shrink-contract regression (follow-up of #462: collapse-then-expand
// pushed the assistant sidebar out of the window). The right column is a flex:1
// item and the WebGL canvas carries the px width renderer.setSize wrote onto it;
// a flex item defaults to min-width:auto, so the stale canvas width becomes the
// column's min-content floor. jsdom has no layout engine, so the overflow cannot
// be reproduced end-to-end here — this pins the style contract; the real layout
// behavior was verified with a headless-Chrome minimal repro page.

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render } from "@testing-library/react";
import App from "./App";

// jsdom 无 matchMedia / ResizeObserver，antd 与画布挂载需要
// jsdom lacks matchMedia / ResizeObserver, required by antd and the canvas mount.
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
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  // jsdom 无 2D canvas：stub 给天体标注用的 getContext("2d")（同 OrbitCanvas.test）
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => ({ fillText: () => {} }) as unknown as CanvasRenderingContext2D,
  );
});

// Tauri 通道：测试只关心布局结构，命令全部拒绝（调用方均有 catch），
// 事件监听立即返回退订函数。
// Tauri channels: the test only cares about layout structure — every command
// rejects (callers all catch) and event listens resolve to an unsubscribe fn.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: () => Promise.reject(new Error("mock: off-app")),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: () => Promise.resolve(() => {}),
}));
vi.mock("@tauri-apps/api/app", () => ({
  getVersion: () => Promise.reject(new Error("mock: off-app")),
}));

// 后端数据通道返回空集即可
// Backend data channels return empty sets.
vi.mock("./projectApi", () => ({
  listArtifacts: () => Promise.resolve([]),
  removeArtifact: () => Promise.resolve(),
  registerArtifact: () => Promise.resolve(),
}));
vi.mock("./sidecarApi", () => ({
  runTool: () => Promise.reject(new Error("mock: off-app")),
  getArtifact: () => Promise.reject(new Error("mock: off-app")),
  ephemerisStatus: () =>
    Promise.resolve({
      kernelDir: null,
      files: [],
      ephemerisReady: true,
      leapsecondReady: true,
      usable: true,
    }),
  formatToolError: (e: unknown) => String(e),
}));
vi.mock("./catalogApi", () => ({
  catalogQuery: () => Promise.resolve({ records: [] }),
}));
vi.mock("./updater", () => ({
  checkForAppUpdates: () => Promise.resolve(null),
  getBundleType: () => Promise.resolve("unknown"),
  inAppUpdateSupported: () => true,
}));
vi.mock("./scenarioApi", () => ({
  saveScenarioFile: () => Promise.resolve(""),
  openScenarioFile: () => Promise.resolve(null),
}));

// jsdom 无 WebGL：只替换 WebGLRenderer，其余 three 保持真实实现
// jsdom has no WebGL: only WebGLRenderer is replaced; the rest of three stays real.
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  class FakeRenderer {
    domElement: HTMLCanvasElement;
    constructor() {
      this.domElement = document.createElement("canvas");
    }
    setSize() {}
    render() {}
    dispose() {}
  }
  return { ...actual, WebGLRenderer: FakeRenderer };
});

describe("App 布局收缩契约（#462 折叠回归）", () => {
  it("画布所在的右栏必须 minWidth: 0，画布 px 宽不得钉住整行布局", () => {
    const { container } = render(<App />);

    // FakeRenderer 的画布挂在 OrbitCanvas 的 mount 里，向上三级即右栏：
    // canvas → mount(width:100%) → 画布盒(flex:1) → 右栏(flex:1 列容器)
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
    const column = canvas!.parentElement?.parentElement?.parentElement;
    expect(column).not.toBeNull();
    expect(column!.style.flexDirection).toBe("column");
    // 契约本体：没有它，折叠再展开就会把助手边栏推出窗口
    expect(column!.style.minWidth).toBe("0px");
  });
});
