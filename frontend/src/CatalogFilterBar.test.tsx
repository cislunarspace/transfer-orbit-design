// 轨道库过滤栏测试（#468）：查询结果 → 树数据源的富化字段透传与 label 简化，
// 以及结果计数 / 过滤条件 / 仅星标状态的显式回显。
//
// Catalog filter bar tests (#468): enrichment-field passthrough and label
// simplification in the query-result → tree-source mapping, plus the explicit
// echo of the result count, active filters, and the starred-only state.

import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CatalogFilterBar } from "./CatalogFilterBar";
import { catalogQuery } from "./catalogApi";
import type { ArtifactSummary } from "./projectApi";

// 只桩网络出口；分组判别等纯函数走真实实现（#470）
// Only the network egress is stubbed; pure helpers like the grouping
// classifier run for real (#470).
vi.mock("./catalogApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./catalogApi")>()),
  catalogQuery: vi.fn(),
  catalogExport: vi.fn(),
}));

// jsdom 无 matchMedia / ResizeObserver，antd Select/Switch 需要
// jsdom lacks matchMedia / ResizeObserver, needed by antd Select/Switch.
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

const RECORDS = [
  {
    record_id: "r1",
    orbit_family: "HALO",
    libration_point: 2,
    jacobi: [3.10, 3.1536], // 线上为包络数组 [min, max]，publish 透传时取下界
    member_count: 12,
    has_ephemeris: true,
    tags: ["★"],
    note: "",
    source_tool: "orbit_family_generation",
    created_at: "2026-01-01",
  },
  {
    record_id: "r2",
    orbit_family: "NRHO",
    member_count: 1,
    tags: [],
    source_tool: "single_orbit",
    created_at: "2026-01-02",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(catalogQuery).mockResolvedValue({ records: RECORDS, message: "" });
});

function resultsSink() {
  const calls: ArtifactSummary[][] = [];
  const onResults = vi.fn((arts: ArtifactSummary[]) => calls.push(arts));
  return { onResults, calls };
}

describe("CatalogFilterBar 查询映射（#468）", () => {
  it("富化字段透传给树行；label 只留族名，成员数移入第二行摘要", async () => {
    const { onResults } = resultsSink();
    render(<CatalogFilterBar onResults={onResults} />);

    await waitFor(() => expect(onResults).toHaveBeenCalled());
    const arts = onResults.mock.calls[0][0] as ArtifactSummary[];
    expect(arts[0]).toMatchObject({
      label: "HALO",
      memberCount: 12,
      librationPoint: 2,
      jacobi: 3.10, // 包络 [3.10, 3.1536] 取下界（与后端 record_to_artifact 同口径）
      hasEphemeris: true,
    });
    // 未携带富化字段的记录：字段缺省而非脏值
    // Records without enrichment: fields absent rather than dirty values.
    expect(arts[1]).toMatchObject({ label: "NRHO", memberCount: 1 });
    expect(arts[1].librationPoint).toBeUndefined();
    expect(arts[1].jacobi).toBeUndefined();
  });
});

describe("CatalogFilterBar 分组判别（#470）", () => {
  // 结构化字段优先：transfer_type / has_ephemeris&&!has_cr3bp / member_count，
  // source_tool 仅兜底（旧内联口径只出 orbit/family 两类，已删）
  it("结构化字段优先，source_tool 仅兜底；taxonomy_labels 透传给子分组", async () => {
    vi.mocked(catalogQuery).mockResolvedValue({
      records: [
        // 纯星历记录（control_orbit）：旧口径误归「轨道」，现归 ephemeris
        { record_id: "c1", orbit_family: "HALO", member_count: 0, has_ephemeris: true, has_cr3bp: false, source_tool: "control_orbit", tags: [] },
        // 转移记录：transfer_type 命中 → transfer（旧 tool 映射里没有它）
        { record_id: "t1", orbit_family: "", member_count: 0, has_ephemeris: false, has_cr3bp: false, transfer_type: "HMN", source_tool: "transfer_design", tags: [] },
        // 单成员族：结构化不命中，回退 tool 映射仍归 family
        { record_id: "f1", orbit_family: "NRHO", member_count: 1, has_ephemeris: false, has_cr3bp: true, source_tool: "orbit_family_generation", tags: [], taxonomy_labels: ["halo_l1_southern"] },
      ],
      message: "",
    });
    const { onResults } = resultsSink();
    render(<CatalogFilterBar onResults={onResults} />);

    await waitFor(() => expect(onResults).toHaveBeenCalled());
    const arts = onResults.mock.calls[0][0] as ArtifactSummary[];
    expect(arts.map((a) => a.artifactType)).toEqual(["ephemeris", "transfer", "family"]);
    expect(arts[2].taxonomyLabels).toEqual(["halo_l1_southern"]);
  });
});

describe("CatalogFilterBar 状态回显（#468）", () => {
  it("查询后回显结果计数与活动条件（族 / L 点 / Jacobi 区间）", async () => {
    render(<CatalogFilterBar onResults={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("共 2 条")).toBeDefined());
    // 无条件时不回显任何条件 Tag
    expect(screen.queryByText("HALO")).toBeNull();

    // 选族 HALO + 平动点 L2 + Jacobi 区间后查询：条件逐项上屏
    // Set family HALO + L2 + Jacobi range, then query: each condition echoes.
    const combos = screen.getAllByRole("combobox");
    fireEvent.mouseDown(combos[0]); // 轨道族类型
    fireEvent.click(await screen.findByText("Halo"));
    fireEvent.mouseDown(combos[1]); // 平动点
    fireEvent.click(await screen.findByText("L2"));
    const min = screen.getByPlaceholderText("Min");
    fireEvent.change(min, { target: { value: "3.0" } });
    fireEvent.change(screen.getByPlaceholderText("Max"), { target: { value: "3.2" } });
    fireEvent.click(screen.getByRole("button", { name: /查\s*询/ }));

    await waitFor(() => {
      expect(screen.getByText("共 2 条")).toBeDefined();
      // 条件 Tag 逐项上屏（下拉选项残留同名文本，按 Tag 元素断言）
      // Each condition tag echoes (dropdown options linger with the same text,
      // so assert against the tag elements).
      const tagTexts = Array.from(document.querySelectorAll(".ant-tag")).map(
        (el) => el.textContent,
      );
      expect(tagTexts).toContain("HALO");
      expect(tagTexts).toContain("L2");
      expect(tagTexts).toContain("C ∈ [3, 3.2]");
    });
    // 查询条件透传给后端
    // Filters pass through to the backend.
    await waitFor(() =>
      expect(catalogQuery).toHaveBeenLastCalledWith(
        expect.objectContaining({
          orbit_family: "HALO",
          libration_point: 2,
          jacobi_min: 3.0,
          jacobi_max: 3.2,
        }),
      ),
    );
  });

  it("仅星标开启：状态行回显，且不重发请求、按前端过滤计数", async () => {
    render(<CatalogFilterBar onResults={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("共 2 条")).toBeDefined());
    const before = vi.mocked(catalogQuery).mock.calls.length;

    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(screen.getByText("共 1 条")).toBeDefined());
    // “仅看星标”在过滤开关 label 与状态行 Tag 两处上屏
    // "Starred only" shows in both the switch label and the status-line tag.
    expect(screen.getAllByText("仅看星标").length).toBe(2);
    expect(vi.mocked(catalogQuery).mock.calls.length).toBe(before);
  });
});
