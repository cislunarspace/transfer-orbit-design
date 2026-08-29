// 会话显示模型：把持久化的 OpenAI 形状历史重建为气泡 + 工具卡片，
// 以及 live 事件流的增量归并。纯函数，便于单测。
// Chat display model: rebuilds bubbles + tool cards from the persisted
// OpenAI-shaped history, and folds the live event stream in incrementally.
// Pure functions, kept unit-testable.

import type { AssistantEventPayload, RawMessage } from "./api";
import type { ToolCardData } from "./ToolCardView";

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "error"; text: string }
  | { kind: "tool"; card: ToolCardData };

// 后端 tool 消息文本的前缀约定（assistant/mod.rs），重启恢复时据此判定卡片终态。
// Prefix conventions of the backend tool messages (assistant/mod.rs), used to
// determine a card's terminal state when restoring after a restart.
const REJECT_PREFIX = "用户拒绝了本次工具调用";
const CHECK_REFUSE_PREFIX = "调用被验证链拒绝";
const BAD_JSON_PREFIX = "工具参数不是合法 JSON";

function parseArgs(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

/** 重启恢复：持久化历史 → 气泡与工具卡片序列。 */
/** Restore after restart: persisted history → sequence of bubbles and tool cards. */
export function restoreItems(history: RawMessage[]): ChatItem[] {
  const items: ChatItem[] = [];
  const cardByCallId = new Map<string, ToolCardData>();

  for (const msg of history) {
    if (msg.role === "user") {
      items.push({ kind: "user", text: msg.content ?? "" });
    } else if (msg.role === "assistant") {
      if (msg.content && msg.content.trim()) {
        items.push({ kind: "assistant", text: msg.content });
      }
      for (const tc of msg.tool_calls ?? []) {
        const card: ToolCardData = {
          callId: tc.id,
          tool: tc.function.name,
          args: parseArgs(tc.function.arguments),
          // 终态由紧随的 tool 消息落定；缺 tool 消息（异常中断）按失败显示
          // Terminal state resolved by the following tool message; a missing one
          // (interrupted run) shows as failed.
          status: "proposed",
        };
        cardByCallId.set(tc.id, card);
        items.push({ kind: "tool", card });
      }
    } else if (msg.role === "tool" && msg.tool_call_id) {
      const card = cardByCallId.get(msg.tool_call_id);
      if (!card) continue;
      const content = msg.content ?? "";
      if (content.startsWith(REJECT_PREFIX)) {
        card.status = "rejected";
      } else if (content.startsWith(CHECK_REFUSE_PREFIX) || content.startsWith(BAD_JSON_PREFIX)) {
        card.status = "error";
        card.summary = { error: { message: content } };
      } else {
        const parsed = tryParse(content);
        const status = parsed?.status;
        const recordId = parsed?.data?.record_id ?? parsed?.record_id;
        const errMsg = parsed?.error?.message;
        card.status = status === "ok" ? "done" : "error";
        card.summary = {
          status: typeof status === "string" ? status : undefined,
          recordId: typeof recordId === "string" ? recordId : undefined,
          error: errMsg ? { message: errMsg } : undefined,
        };
      }
    }
  }
  // 恢复后仍停在 proposed 的卡片 = 重启打断的等待确认，标记为失败以免误导
  // Cards still stuck at proposed after restore = a confirmation interrupted by
  // restart; mark them failed so they don't mislead.
  for (const item of items) {
    if (item.kind === "tool" && item.card.status === "proposed") {
      item.card.status = "error";
      item.card.summary = { error: { message: "（会话被重启打断，未完成）" } };
    }
  }
  return items;
}

function tryParse(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * 折叠一条 live 事件到显示序列。返回新数组（不可变更新，配合 React）。
 * Fold one live event into the display sequence. Returns a new array
 * (immutable update, for React).
 */
export function foldEvent(items: ChatItem[], ev: AssistantEventPayload): ChatItem[] {
  switch (ev.kind) {
    case "delta": {
      const next = items.slice();
      const last = next[next.length - 1];
      if (last && last.kind === "assistant") {
        next[next.length - 1] = { kind: "assistant", text: last.text + ev.text };
      } else {
        next.push({ kind: "assistant", text: ev.text });
      }
      return next;
    }
    case "tool_proposed":
      return upsertCard(items, {
        callId: ev.callId,
        tool: ev.tool,
        args: ev.arguments,
        status: "proposed",
      });
    case "tool_started":
      return updateCard(items, ev.callId, (c) => ({
        ...c,
        args: ev.arguments ?? c.args,
        status: "running",
        startedAt: Date.now(),
      }));
    case "tool_done":
      return updateCard(items, ev.callId, (c) => ({
        ...c,
        status: ev.ok ? "done" : "error",
        summary: ev.summary,
      }));
    case "tool_rejected":
      return updateCard(items, ev.callId, (c) => ({ ...c, status: "rejected" }));
    case "error":
      // 运行期错误作为持久气泡留在会话流里（比一次性 toast 更有上下文）
      // Runtime errors stay in the conversation as a persistent bubble (more
      // context than a one-off toast).
      return [...items, { kind: "error", text: ev.message }];
    default:
      return items;
  }
}

function upsertCard(items: ChatItem[], card: ToolCardData): ChatItem[] {
  const idx = items.findIndex((i) => i.kind === "tool" && i.card.callId === card.callId);
  if (idx >= 0) {
    const next = items.slice();
    next[idx] = { kind: "tool", card };
    return next;
  }
  return [...items, { kind: "tool", card }];
}

function updateCard(
  items: ChatItem[],
  callId: string,
  f: (c: ToolCardData) => ToolCardData,
): ChatItem[] {
  return items.map((i) =>
    i.kind === "tool" && i.card.callId === callId ? { kind: "tool", card: f(i.card) } : i,
  );
}
