// formatToolError 单测（#450）：计算错误 toast 不再把整个错误对象 JSON
// 序列化甩给用户，优先人话 message，缺失回退 code，再缺失才整体序列化。
// formatToolError unit tests (#450): the run-error toast no longer dumps the
// JSON-serialized error object — prefer the human-readable message, fall back
// to the code, then to whole-object serialization.

import { describe, it, expect } from "vitest";
import { formatToolError } from "./sidecarApi";

describe("formatToolError（#450）", () => {
  it("有 message 时优先返回 message", () => {
    expect(
      formatToolError({ code: "E_GENERIC", message: "Jacobi 常数超出可行域" }),
    ).toBe("Jacobi 常数超出可行域");
  });

  it("message 为空串/空白时回退 code", () => {
    expect(formatToolError({ code: "E_TIMEOUT", message: "" })).toBe("E_TIMEOUT");
    expect(formatToolError({ code: "E_TIMEOUT", message: "   " })).toBe("E_TIMEOUT");
  });

  it("两者皆缺时整体 JSON 序列化", () => {
    expect(formatToolError({ code: "", message: "" })).toBe('{"code":"","message":""}');
  });

  it("error 为 null/undefined 时返回空串（调用方自行拼接前缀）", () => {
    expect(formatToolError(null)).toBe("");
    expect(formatToolError(undefined)).toBe("");
  });
});
