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
import { catalogQuerySummaryById } from "./catalogApi";
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
