import { describe, it, expect } from "vitest";
import { validateToolParams, type ParamIssue } from "./index";
import type { ToolSchema, SchemaProperty } from "../schema";

// 最小 schema：必填枚举 + 可空数值（anyOf 分支携带范围，与真实 schema 同构）
// + 整数独占上界 + 仅独占下界的普通数值字段
// Minimal schema: required enum + nullable number (anyOf branch carries the range, isomorphic to the real
// schema) + an integer with an exclusive upper bound + a plain number with only an exclusive lower bound.
const schema: ToolSchema = {
  required: ["orbit_type", "amplitude"],
  properties: {
    orbit_type: { type: "string", title: "Orbit Type", enum: ["HALO", "NRHO"] },
    amplitude: {
      title: "Amplitude",
      anyOf: [
        { type: "number", minimum: -110000, maximum: 200000 } as SchemaProperty,
        { type: "null" },
      ],
    },
    n_revs: { type: "integer", title: "N Revs", minimum: 1, exclusiveMaximum: 10 },
    phase: { type: "number", title: "Phase", exclusiveMinimum: 0 },
  },
};

const OK_VALUES = { orbit_type: "HALO", amplitude: 5000, n_revs: 5, phase: 0.1 };

function reasons(toolName: string, values: Record<string, unknown>): string[] {
  return validateToolParams(toolName, schema, values).map((i: ParamIssue) => i.reason);
}

describe("validateToolParams", () => {
  it("必填字段缺失或空串报必填，可空字段缺省不报", () => {
    const rs = reasons("generic_tool", { amplitude: 1000 });
    expect(rs.some((r) => r.includes("必填"))).toBe(true);
    // phase 非必填、未填 → 不报
    // phase is optional and unfilled → no error.
    expect(rs.every((r) => !r.includes("Phase"))).toBe(true);
    expect(reasons("generic_tool", { ...OK_VALUES, orbit_type: "" }).some((r) => r.includes("必填"))).toBe(true);
  });

  it("anyOf 分支的 minimum/maximum 参与越界校验，恰在边界通过", () => {
    expect(reasons("generic_tool", { ...OK_VALUES, amplitude: 250000 })[0]).toContain("超出可填范围");
    expect(reasons("generic_tool", { ...OK_VALUES, amplitude: -120000 })[0]).toContain("超出可填范围");
    expect(validateToolParams("generic_tool", schema, { ...OK_VALUES, amplitude: 200000 })).toEqual([]);
    expect(validateToolParams("generic_tool", schema, { ...OK_VALUES, amplitude: -110000 })).toEqual([]);
  });

  it("独占边界：等于边界值报错，紧邻边界通过", () => {
    expect(reasons("generic_tool", { ...OK_VALUES, n_revs: 10 })[0]).toContain("超出可填范围");
    expect(reasons("generic_tool", { ...OK_VALUES, phase: 0 })[0]).toContain("超出可填范围");
    expect(validateToolParams("generic_tool", schema, { ...OK_VALUES, n_revs: 9 })).toEqual([]);
    expect(validateToolParams("generic_tool", schema, { ...OK_VALUES, phase: 0.001 })).toEqual([]);
  });

  it("全部合法返回空列表", () => {
    expect(validateToolParams("generic_tool", schema, OK_VALUES)).toEqual([]);
  });

  it("问题条目携带字段名与人读标签", () => {
    const issues = validateToolParams("generic_tool", schema, { amplitude: 999999 });
    expect(issues[0].field).toBe("orbit_type");
    expect(issues[0].label).toBe("Orbit Type");
    expect(issues.some((i) => i.field === "amplitude" && i.label === "Amplitude")).toBe(true);
  });
});
