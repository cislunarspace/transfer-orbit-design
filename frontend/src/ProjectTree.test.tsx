// ProjectTree 交互测试：勾选多选（绘制所选）、星标切换、备注 Tooltip 与编辑。
//
// ProjectTree interaction tests: check-based multi-select ("Plot Selected"), star toggling,
// note tooltip, and note editing.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ProjectTree } from "./ProjectTree";
import { catalogTag, catalogQuerySummaryById } from "./catalogApi";
import type { ArtifactSummary } from "./projectApi";

// 只桩网络出口；taxonomy 判别等纯函数走真实实现（#470）。
// 注意 catalogQuerySummaryById 也必须显式桩：ESM 模块内函数互调不经过 mock 注册表。
// Only the network egress is stubbed; pure helpers like the taxonomy
// classifier run for real (#470). catalogQuerySummaryById must be stubbed
// explicitly too: intra-module calls bypass the mock registry.
vi.mock("./catalogApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./catalogApi")>()),
  catalogDelete: vi.fn(),
  catalogQuery: vi.fn(),
  catalogQuerySummaryById: vi.fn(),
  catalogTag: vi.fn().mockResolvedValue(true),
}));

// 三条 orbit 叶子：a1 行数据带 tags/note；a2 缺 tags（走详情查询分支）
// Three orbit leaves: a1 carries tags/note in row data; a2 lacks tags (the detail-query branch).
const ITEMS: ArtifactSummary[] = [
  { artifactId: "a1", artifactType: "orbit", label: "Halo A", orbitType: "HALO", sourceTool: "", recordId: "r1", createdAt: "", tags: ["demo"], note: "N".repeat(100) },
  { artifactId: "a2", artifactType: "orbit", label: "NRHO B", orbitType: "NRHO", sourceTool: "", recordId: "r2", createdAt: "" },
  { artifactId: "a3", artifactType: "orbit", label: "DRO C", orbitType: "DRO", sourceTool: "", recordId: "r3", createdAt: "" },
];

function setup(artifacts: ArtifactSummary[] = ITEMS) {
  const props = {
    artifacts,
    selectedId: null,
    onSelect: vi.fn(),
    onRemove: vi.fn(),
    onPlotSelected: vi.fn(),
    onMetaChange: vi.fn(),
  };
  const view = render(<ProjectTree {...props} />);
  return { props, view };
}

// 行定位：按叶子标签找到树行，再取行内勾选框
// Row lookup: find the tree row by leaf label, then grab its checkbox.
function checkboxOf(label: string): HTMLElement {
  const row = screen.getByText(label).closest(".ant-tree-treenode");
  expect(row).not.toBeNull();
  const box = row!.querySelector(".ant-tree-checkbox") as HTMLElement | null;
  expect(box).not.toBeNull();
  return box!;
}

beforeEach(() => {
  vi.clearAllMocks();
  // jsdom 无 ResizeObserver（antd Tree 虚拟列表依赖）：stub 空实现
  // jsdom lacks ResizeObserver (antd Tree's virtual list needs it): stub an empty impl.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
  vi.mocked(catalogQuerySummaryById).mockImplementation(async (rid: string) =>
    rid === "r2" ? ({ record_id: "r2", orbit_family: "", tags: ["t2"] } as never) : null,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProjectTree 勾选多选", () => {
  it("勾选 ≥2 叶子出现“绘制所选”，点击回传勾选集合", async () => {
    const { props } = setup();
    // 只勾 1 条不出现入口
    fireEvent.click(checkboxOf("Halo A"));
    expect(screen.queryByRole("button", { name: /绘制所选/ })).toBeNull();

    fireEvent.click(checkboxOf("NRHO B"));
    const btn = screen.getByRole("button", { name: /绘制所选/ });
    expect(btn.textContent).toContain("2");
    fireEvent.click(btn);
    await waitFor(() => expect(props.onPlotSelected).toHaveBeenCalledTimes(1));
    expect(props.onPlotSelected.mock.calls[0][0].map((a: ArtifactSummary) => a.artifactId)).toEqual(["a1", "a2"]);
  });

  it("勾选不触发单击选中；单击叶子仍走 onSelect", () => {
    const { props } = setup();
    fireEvent.click(checkboxOf("Halo A"));
    expect(props.onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("DRO C"));
    expect(props.onSelect).toHaveBeenCalledTimes(1);
    expect(props.onSelect.mock.calls[0][0].artifactId).toBe("a3");
  });
});

describe("ProjectTree 星标切换", () => {
  it("行缺 tags 时先查详情再追加 ★（catalog_tag 整体替换，note 不动）", async () => {
    const { props } = setup();
    fireEvent.click(screen.getAllByRole("button", { name: "星标" })[1]); // NRHO B
    // 点查走 catalogQuerySummaryById（5.9.2 起 catalog_query 无 record_id 过滤）
    await waitFor(() => expect(catalogQuerySummaryById).toHaveBeenCalledWith("r2"));
    await waitFor(() => expect(catalogTag).toHaveBeenCalledWith("r2", ["t2", "★"]));
    await waitFor(() => expect(props.onMetaChange).toHaveBeenCalledWith("r2", ["t2", "★"]));
  });

  it("已星标行再点移除 ★，直接用行内 tags 不重查", async () => {
    const starred = ITEMS.map((a: ArtifactSummary) =>
      a.artifactId === "a1" ? { ...a, tags: ["★", "demo"] } : a,
    );
    const { props } = setup(starred);
    fireEvent.click(screen.getAllByRole("button", { name: "星标" })[0]); // Halo A
    await waitFor(() => expect(catalogTag).toHaveBeenCalledWith("r1", ["demo"]));
    expect(catalogQuerySummaryById).not.toHaveBeenCalled();
    await waitFor(() => expect(props.onMetaChange).toHaveBeenCalledWith("r1", ["demo"]));
  });
});

describe("ProjectTree 备注", () => {
  it("悬停显示备注摘要（超长截断到 80 字符）", async () => {
    setup();
    fireEvent.mouseEnter(screen.getByText("Halo A"));
    await waitFor(() => {
      expect(screen.getByText(`${"N".repeat(80)}…`)).toBeDefined();
    });
  });

  it("右键“编辑备注”保存走 catalog_tag（行内 tags 整体替换 + 新 note）", async () => {
    const { props } = setup();
    fireEvent.contextMenu(screen.getByText("Halo A"));
    fireEvent.click(await screen.findByText("编辑备注..."));

    const area = await screen.findByPlaceholderText("备注内容...");
    fireEvent.change(area, { target: { value: "新备注" } });
    // antd 两字中文按钮自动插入空格（“保 存”），用正则匹配
    // antd auto-inserts a space in two-char Chinese buttons ("保 存"); match with a regex.
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));

    await waitFor(() => expect(catalogTag).toHaveBeenCalledWith("r1", ["demo"], "新备注"));
    await waitFor(() => expect(props.onMetaChange).toHaveBeenCalledWith("r1", ["demo"], "新备注"));
  });
});

describe("ProjectTree 分组头与结构化摘要（#468）", () => {
  it("分组头为文字 + 计数徽标，无 emoji；空组徽标置灰", () => {
    setup();
    // 四个分组按固定顺序渲染，emoji 全部消失
    expect(screen.getByText("轨道")).toBeDefined();
    expect(screen.queryByText(/🪐|🌀|🚀|📡/)).toBeNull();

    const badges = Array.from(document.querySelectorAll(".ant-badge-count")) as HTMLElement[];
    expect(badges.length).toBe(4);
    // 组序 orbit/family/transfer/ephemeris：orbit 3 条蓝徽标，family 0 条灰徽标
    expect(badges[0].textContent).toBe("3");
    expect(badges[0].style.backgroundColor).not.toBe("");
    expect(badges[1].textContent).toBe("0");
    expect(badges[1].style.backgroundColor).not.toBe(badges[0].style.backgroundColor);
  });

  it("叶子第二行挂结构化摘要：成员数 / L 点 / Jacobi；缺字段不渲染第二行", () => {
    const items: ArtifactSummary[] = [
      {
        artifactId: "a1", artifactType: "family", label: "HALO 家族", orbitType: "HALO",
        sourceTool: "", recordId: "r1", createdAt: "",
        memberCount: 12, librationPoint: 2, jacobi: 3.1536,
      },
      ...ITEMS.slice(0, 1),
    ];
    setup(items);
    expect(screen.getByText("12 成员 · L2 · C 3.154")).toBeDefined();
    // 无富化字段的行（Halo A）不渲染第二行：全文只此一处成员摘要
    // The row without enrichment (Halo A) renders no second line: exactly one member summary overall.
    expect(screen.getAllByText(/成员/).length).toBe(1);
  });

  it("受控展开：初始全展开，点分组头折叠后子行消失", () => {
    // Tree 本体已按 ADR 0020 传 motion={false}，jsdom 里无收起动画卡滞
    // The Tree itself passes motion={false} per ADR 0020, so jsdom has no
    // stuck collapse motion.
    const props = {
      artifacts: ITEMS,
      selectedId: null,
      onSelect: vi.fn(),
      onRemove: vi.fn(),
      onPlotSelected: vi.fn(),
      onMetaChange: vi.fn(),
    };
    render(<ProjectTree {...props} />);
    expect(screen.getByText("Halo A")).toBeDefined();

    const groupState = () =>
      screen.getByText("轨道").closest(".ant-tree-treenode") as HTMLElement;
    const switcherOf = () =>
      groupState().querySelector(".ant-tree-switcher") as HTMLElement;

    expect(groupState().getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(switcherOf());
    expect(groupState().getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(switcherOf());
    expect(groupState().getAttribute("aria-expanded")).toBe("true");
  });

  it("容器量得高度后 Tree 启用虚拟滚动（height 传入）", () => {
    // RO stub：observe 即给元素定高，模拟真实浏览器量高回调路径
    // RO stub: observe marks the element measured, mimicking the real browser measure path.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe(el: Element) {
          Object.defineProperty(el, "clientHeight", { configurable: true, value: 400 });
        }
        disconnect() {}
        unobserve() {}
      },
    );
    const { view } = setup();
    const holder = view.container.querySelector(".ant-tree-list-holder") as HTMLElement | null;
    expect(holder).not.toBeNull();
    expect(holder!.getAttribute("style")).toContain("400px");
  });
});

describe("ProjectTree taxonomy 子分组（#470）", () => {
  const labeled = (over: Partial<ArtifactSummary>): ArtifactSummary => ({
    artifactId: "x", artifactType: "orbit", label: "X", orbitType: "",
    sourceTool: "", recordId: "rx", createdAt: "", ...over,
  });

  it("轨道组内有已打标记录时按一级类别分层，未打标归「未分类」", () => {
    setup([
      labeled({ artifactId: "a1", label: "Halo A", taxonomyLabels: ["halo_l2_northern"] }),
      labeled({ artifactId: "a2", label: "DRO B", taxonomyLabels: ["distant_retrograde"] }),
      labeled({ artifactId: "a3", label: "Res C", taxonomyLabels: ["resonant_3_1"] }),
      labeled({ artifactId: "a4", label: "Liss D", taxonomyLabels: null }),
    ]);
    // 三个类别子组 + 未分类子组（空类别不渲染）
    for (const g of ["平动点", "月心", "共振", "未分类"]) {
      expect(screen.getByText(g)).toBeDefined();
    }
    // rc-tree 行是扁平 DOM（层级只体现在视觉缩进），用行序断言归位：
    // 每个子组头之后紧跟该类叶子
    const rows = Array.from(document.querySelectorAll(".ant-tree-treenode")).map(
      (n) => n.textContent ?? "",
    );
    const order = rows.map((t) => {
      const hit = ["平动点", "月心", "共振", "未分类", "Halo A", "DRO B", "Res C", "Liss D"].find(
        (s) => t.includes(s),
      );
      return hit ?? "";
    }).filter(Boolean);
    expect(order).toEqual(["平动点", "Halo A", "月心", "DRO B", "共振", "Res C", "未分类", "Liss D"]);
  });

  it("平动点子分组内按 L 点编号再分层；缺 L 字段的记录留子分组直属", () => {
    setup([
      labeled({ artifactId: "a1", label: "Halo L1", taxonomyLabels: ["halo_l1_northern"], librationPoint: 1 }),
      labeled({ artifactId: "a2", label: "Halo L2a", taxonomyLabels: ["halo_l2_northern"], librationPoint: 2 }),
      labeled({ artifactId: "a3", label: "Halo L2b", taxonomyLabels: ["halo_l2_southern"], librationPoint: 2 }),
      labeled({ artifactId: "a4", label: "Lya L4", taxonomyLabels: ["lyapunov_l4"], librationPoint: 4 }),
      // 缺 librationPoint 字段：仍归平动点子分组，但不进任何 L 层（不丢行）
      // Missing librationPoint: still in the libration-point subgroup, but no L level.
      labeled({ artifactId: "a5", label: "No L", taxonomyLabels: ["halo_l1_northern"] }),
      labeled({ artifactId: "a6", label: "DRO B", taxonomyLabels: ["distant_retrograde"] }),
    ]);
    // 无记录的 L3/L5 层不渲染（叶子的摘要行只含各自的 L1/L2/L4，不会撞名）
    expect(screen.queryByText("L3")).toBeNull();
    expect(screen.queryByText("L5")).toBeNull();
    // 行序断言（rc-tree 扁平 DOM）：平动点 → L1/L2/L4 层各带叶子 → 直属的
    // No L → 月心子组（月心不分 L 层）
    const rows = Array.from(document.querySelectorAll(".ant-tree-treenode")).map(
      (n) => n.textContent ?? "",
    );
    // 叶子 label 排在层名之前：叶子行文本同时含 label 与摘要 "L1"，先中 label
    const NAMES = [
      "Halo L1", "Halo L2a", "Halo L2b", "Lya L4", "No L", "DRO B",
      "平动点", "月心", "L1", "L2", "L4",
    ];
    const order = rows
      .map((t) => NAMES.find((s) => t.includes(s)) ?? "")
      .filter(Boolean);
    expect(order).toEqual([
      "平动点", "L1", "Halo L1", "L2", "Halo L2a", "Halo L2b", "L4", "Lya L4", "No L",
      "月心", "DRO B",
    ]);
  });

  it("全组未打标（会话产物）保持平铺，不多一层", () => {
    setup();
    expect(screen.queryByText("平动点")).toBeNull();
    expect(screen.queryByText("未分类")).toBeNull();
    // 叶子仍直接挂在「轨道」组下
    expect(screen.getByText("Halo A")).toBeDefined();
  });

  it("转移/星历组不分层（taxonomy 子分组只属轨道/轨道族）", () => {
    setup([
      labeled({ artifactId: "t1", artifactType: "transfer", label: "TLI", taxonomyLabels: ["halo_l1_northern"] }),
    ]);
    expect(screen.getByText("转移")).toBeDefined();
    expect(screen.queryByText("平动点")).toBeNull();
    expect(screen.getByText("TLI")).toBeDefined();
  });
});
