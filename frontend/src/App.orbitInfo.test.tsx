// 轨道信息页签（#476）集成回归：点画布轨道清单项 = 聚焦 + 中栏自动切到
// 「轨道信息」页签并展示该轨道详情（来源来自结果层 = 本次运行产物）；
// 取消聚焦页签不弹回。mock 脚手架与 App.contentMode.test 同源。
// Orbit-info tab (#476) integration: clicking a canvas-orbit-list row is one
// action — focus + the mid pane auto-switches to the "orbit info" tab showing
// that orbit's details (source = result layer, "latest run product");
// unfocusing never snaps the tab back. Mock scaffolding mirrors
// App.contentMode.test.

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./App";

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
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => ({ fillText: () => {} }) as unknown as CanvasRenderingContext2D,
  );
});

vi.mock("@tauri-apps/api/core", () => ({
  invoke: () => Promise.reject(new Error("mock: off-app")),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: () => Promise.resolve(() => {}),
}));
vi.mock("@tauri-apps/api/app", () => ({
  getVersion: () => Promise.reject(new Error("mock: off-app")),
}));
vi.mock("./updater", () => ({
  checkForAppUpdates: () => Promise.resolve(null),
  checkManualAppUpdate: () => Promise.resolve(null),
  getBundleType: () => Promise.resolve("unknown"),
  inAppUpdateSupported: () => true,
}));
vi.mock("./scenarioApi", () => ({
  saveScenarioFile: () => Promise.resolve(""),
  openScenarioFile: () => Promise.resolve(null),
}));

const treeRecords = [
  {
    record_id: "rid-a",
    orbit_family: "DRO",
    member_count: 1,
    has_ephemeris: true,
    source_tool: "design_orbit",
    tags: [],
    note: "",
  },
];

vi.mock("./catalogApi", () => ({
  catalogQuery: () => Promise.resolve({ records: treeRecords, message: "mock" }),
  catalogTag: () => Promise.resolve(true),
  STAR_TAG: "★",
}));
vi.mock("./projectApi", () => ({
  listArtifacts: () =>
    Promise.resolve([
      { artifactId: "rid-a", artifactType: "orbit", label: "DRO (1 成员)", recordId: "rid-a" },
    ]),
  removeArtifact: () => Promise.resolve(),
  registerArtifact: () => Promise.resolve(),
}));
vi.mock("./sidecarApi", () => ({
  runTool: () => Promise.reject(new Error("mock: off-app")),
  getArtifact: (rid: string) => Promise.resolve(dualSegmentArtifact(rid)),
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

// 与 App.contentMode.test 同一双段记录：CR3BP 基段（2 点）+ 星历段（3 点）。
// The same dual-segment record as App.contentMode.test: a CR3BP base segment
// (2 points) plus an ephemeris segment (3 points).
const dualSegmentArtifact = (recordId: string) => ({
  recordId,
  orbitFamily: "DRO",
  memberCount: 1,
  mu: 0.012150585609624,
  familyMembers: [
    {
      states: [
        0.87, 0, 0.05, 0, 0.1, 0,
        0.88, 0.01, 0.05, 0, 0.1, 0,
      ],
      times: [],
      period: null,
      jacobi: 3.047,
    },
  ],
  members: [
    [0.87, 0, 0.05],
    [0.88, 0.01, 0.05],
  ],
  jacobi: null,
  ephemeris: {
    synodic_position: [0.83, 0.009, -0.06, 0.84, 0.01, -0.05, 0.85, 0.012, -0.04],
    position_km: null,
    year: [2024, 2024, 2024],
    month: [1, 1, 1],
    day: [1, 1, 1],
    hour: [0, 1, 2],
    minute: [0, 0, 0],
    second: [0, 0, 0],
  },
  transfer: null,
  error: null,
});

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

const orbitRow = (label: string): HTMLElement => {
  const container = screen.getByTestId("canvas-orbit-list");
  const row = Array.from(container.querySelectorAll("[data-orbit-item]")).find(
    (el) => (el.textContent ?? "").includes(label),
  );
  expect(row, `清单行 ${label} 应存在`).toBeTruthy();
  return row as HTMLElement;
};

describe("轨道信息页签（#476）", () => {
  it("点清单项：中栏切到轨道信息页并展示该轨道详情；取消聚焦页签不弹回", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText("DRO (1 成员)")).toBeTruthy());
    fireEvent.click(screen.getByText("DRO (1 成员)"));
    // 双段记录 → 清单两行（CR3BP 参考轨道 + 星历段）；初始中栏是设计工具
    // （工具 Select 在场），轨道信息页签未选中
    await waitFor(() => orbitRow("CR3BP 参考轨道"));
    expect(screen.queryByTestId("orbit-info-panel")).toBeNull();

    fireEvent.click(orbitRow("CR3BP 参考轨道"));
    await waitFor(() => {
      const panel = screen.getByTestId("orbit-info-panel");
      // 标题即轨道名；字段：类型 / 数据系 / Jacobi / 点数 / 来源（结果层）
      expect(panel.textContent).toContain("CR3BP 参考轨道");
      expect(panel.textContent).toContain("会合系无量纲");
      expect(panel.textContent).toContain("3.047000");
      expect(panel.textContent).toContain("本次运行产物");
    });
    // 聚焦行带标记
    expect(orbitRow("CR3BP 参考轨道").getAttribute("data-focused")).toBe("true");

    // 再点一次取消聚焦：页签留在轨道信息（空态指引），不弹回设计工具
    fireEvent.click(orbitRow("CR3BP 参考轨道"));
    await waitFor(() =>
      expect(screen.getByTestId("orbit-info-panel").textContent).toContain("点击"),
    );
  });

  it("清单无内容时手动切页签：轨道信息页显示空态指引", async () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("mid-tab-orbitInfo"));
    await waitFor(() => expect(screen.getByTestId("orbit-info-panel")).toBeTruthy());
    // 切回设计工具：工具 Select 回归
    fireEvent.click(screen.getByTestId("mid-tab-tool"));
    await waitFor(() => expect(screen.queryByTestId("orbit-info-panel")).toBeNull());
  });
});
