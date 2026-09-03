// catalogQuerySummaryById 真身链路测试（#470）：e2m2e 5.9.2 移除 catalog_query 的
// record_id 过滤字段（传了被 pydantic extra_forbidden 拒为 INVALID_PARAMS），
// 点查 = 全量查询 + 客户端按 id 找。桩打在 Tauri invoke 边界，catalogApi 内部
// 函数互调全真（模块内互调不走模块级 mock 注册表，故不能桩 catalogQuery）。
//
// Real-chain tests for catalogQuerySummaryById (#470). The stub lives at the
// Tauri invoke boundary so every catalogApi-internal call runs for real
// (intra-module calls bypass module-level mocks, so stubbing catalogQuery
// would not exercise the real lookup).

import { describe, it, expect, vi, beforeEach } from "vitest";
import { catalogQuerySummaryById, classifyArtifactType, type CatalogRecord } from "./catalogApi";
import { invoke } from "@tauri-apps/api/core";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

const RECORDS = [
  { record_id: "r1", orbit_family: "HALO", tags: ["★"] },
  { record_id: "r2", orbit_family: "NRHO", tags: [] },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(invoke).mockImplementation(async () => ({ records: RECORDS, message: "" }) as never);
});

describe("catalogQuerySummaryById（5.9.2 点查）", () => {
  it("全量查询后按 record_id 客户端命中；查询参数不得携带 record_id", async () => {
    const rec = await catalogQuerySummaryById("r2");
    expect(rec?.orbit_family).toBe("NRHO");
    expect(vi.mocked(invoke)).toHaveBeenCalledWith("catalog_query", { arguments: {} });
  });

  it("查不到（并发删除等）返回 null 而不是抛错", async () => {
    await expect(catalogQuerySummaryById("ghost")).resolves.toBeNull();
  });
});

// 跨语言同步（#470 评审）：与后端 _classify_artifact_type 读同一份用例
// tests/engine/fixtures/classify_artifact_type_cases.json——规则改动只动 JSON,
// 任一侧实现漂移都会两侧同时红灯。record 缺省字段 = falsy 语义,与 Python 侧
// 显式中性默认值对齐。(?raw 由 vite/client 类型声明,避免引入 node 类型)
// Cross-language parity (#470 review): shares classify_artifact_type_cases.json
// with the backend pytest suite — a rule change touches only the JSON, and any
// implementation drift fails both sides at once. Missing record fields carry
// falsy semantics, aligned with the Python side's explicit neutral defaults.
// (The ?raw import is typed by vite/client, so no node types are needed.)
import casesRaw from "../../tests/engine/fixtures/classify_artifact_type_cases.json?raw";

const PARITY_CASES = (
  JSON.parse(casesRaw) as {
    cases: { name: string; record: Record<string, unknown>; expect: string }[];
  }
).cases;

describe("classifyArtifactType 跨语言同步用例（#470）", () => {
  for (const c of PARITY_CASES) {
    it(`${c.name} → ${c.expect}`, () => {
      expect(classifyArtifactType(c.record as CatalogRecord)).toBe(c.expect);
    });
  }
});
