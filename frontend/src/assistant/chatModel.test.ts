// chatModel 单测：持久化历史的恢复与 live 事件折叠。
// Unit tests for chatModel: restoring persisted history and folding live events.

import { describe, it, expect } from "vitest";
import { restoreItems, foldEvent, type ChatItem } from "./chatModel";
import type { RawMessage } from "./api";

describe("restoreItems", () => {
  it("restores user and assistant bubbles", () => {
    const history: RawMessage[] = [
      { role: "user", content: "你好" },
      { role: "assistant", content: "你好！我能帮你做什么？" },
    ];
    const items = restoreItems(history);
    expect(items).toEqual([
      { kind: "user", text: "你好" },
      { kind: "assistant", text: "你好！我能帮你做什么？" },
    ]);
  });

  it("pairs tool_calls with tool messages into a done card with recordId", () => {
    const history: RawMessage[] = [
      { role: "user", content: "生成一个 halo 轨道" },
      {
        role: "assistant",
        content: "好的，我来调用工具。",
        tool_calls: [
          { id: "call_1", function: { name: "design_orbit", arguments: '{"a":1}' } },
        ],
      },
      {
        role: "tool",
        tool_call_id: "call_1",
        content: JSON.stringify({ status: "ok", data: { record_id: "rec-42" } }),
      },
    ];
    const items = restoreItems(history);
    const card = items.find((i) => i.kind === "tool");
    expect(card && card.kind === "tool" && card.card.status).toBe("done");
    expect(card && card.kind === "tool" && card.card.summary?.recordId).toBe("rec-42");
    expect(card && card.kind === "tool" && card.card.args).toEqual({ a: 1 });
  });

  it("marks rejected calls from the rejection prefix", () => {
    const history: RawMessage[] = [
      {
        role: "assistant",
        content: null,
        tool_calls: [{ id: "c2", function: { name: "catalog_delete", arguments: "{}" } }],
      },
      { role: "tool", tool_call_id: "c2", content: "用户拒绝了本次工具调用，未执行。……" },
    ];
    const items = restoreItems(history);
    const card = items[0];
    expect(card.kind === "tool" && card.card.status).toBe("rejected");
  });

  it("marks a dangling proposed card (interrupted run) as failed", () => {
    const history: RawMessage[] = [
      {
        role: "assistant",
        content: null,
        tool_calls: [{ id: "c3", function: { name: "design_orbit", arguments: "{}" } }],
      },
    ];
    const items = restoreItems(history);
    const card = items[0];
    expect(card.kind === "tool" && card.card.status).toBe("error");
  });
});

describe("foldEvent", () => {
  it("accumulates streaming deltas into one assistant bubble", () => {
    let items: ChatItem[] = [{ kind: "user", text: "q" }];
    items = foldEvent(items, { kind: "delta", text: "你" });
    items = foldEvent(items, { kind: "delta", text: "好" });
    expect(items).toEqual([
      { kind: "user", text: "q" },
      { kind: "assistant", text: "你好" },
    ]);
  });

  it("runs a tool card through proposed → running → done", () => {
    let items: ChatItem[] = [];
    items = foldEvent(items, { kind: "tool_proposed", callId: "c", tool: "design_orbit", arguments: {} });
    items = foldEvent(items, { kind: "tool_started", callId: "c", tool: "design_orbit", arguments: {} });
    items = foldEvent(items, {
      kind: "tool_done", callId: "c", tool: "design_orbit", ok: true,
      summary: { status: "ok", recordId: "rec-1" },
    });
    const card = items[0];
    expect(card.kind === "tool" && card.card.status).toBe("done");
    expect(card.kind === "tool" && card.card.summary?.recordId).toBe("rec-1");
  });

  it("starts a new assistant bubble after a tool card", () => {
    let items: ChatItem[] = [];
    items = foldEvent(items, { kind: "tool_proposed", callId: "c", tool: "t", arguments: {} });
    items = foldEvent(items, { kind: "delta", text: "接着…" });
    expect(items).toHaveLength(2);
    expect(items[1]).toEqual({ kind: "assistant", text: "接着…" });
  });

  it("folds runtime errors into a persistent error bubble", () => {
    let items: ChatItem[] = [{ kind: "user", text: "q" }];
    items = foldEvent(items, { kind: "error", message: "模型服务未配置" });
    expect(items[1]).toEqual({ kind: "error", text: "模型服务未配置" });
  });
});
