// 会话显示模型：把持久化的 OpenAI 形状历史重建为气泡 + 工具卡片，
// 以及 live 事件流的增量归并。纯函数，便于单测。

import type { AssistantEventPayload, RawMessage } from "./api";
import type { ToolCardData } from "./ToolCardView";

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "thinking"; text: string }
  | { kind: "error"; text: string }
  | { kind: "interrupted" }
  | { kind: "tool"; card: ToolCardData };

// 后端 tool 消息文本的前缀约定（assistant/mod.rs），重启恢复时据此判定卡片终态。
const REJECT_PREFIX = "用户拒绝了本次工具调用";
const INTERRUPT_PREFIX = "用户中断了本轮对话";
const CHECK_REFUSE_PREFIX = "调用被验证链拒绝";
const BAD_JSON_PREFIX = "工具参数不是合法 JSON";

function parseArgs(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

/** 重启恢复：持久化历史 → 气泡、思考块与工具卡片序列。 */
export function restoreItems(history: RawMessage[]): ChatItem[] {
  const items: ChatItem[] = [];
  const cardByCallId = new Map<string, ToolCardData>();

  for (const msg of history) {
    // 思考行（ADR 0025 决策 3 存储混入）：按原位重建思考块（默认折叠由视图层管）；
    // 中断界限行（#453）同理原位重建
    if ("kind" in msg) {
      if (msg.kind === "thinking") {
        items.push({ kind: "thinking", text: msg.content ?? "" });
      } else if (msg.kind === "interrupted") {
        items.push({ kind: "interrupted" });
      }
      continue;
    }
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
      } else if (content.startsWith(INTERRUPT_PREFIX)) {
        // 中断占位（#453）：工具因停止请求未执行，终态为失败并说明原因
        card.status = "error";
        card.summary = { error: { message: content } };
      } else if (content.startsWith(CHECK_REFUSE_PREFIX) || content.startsWith(BAD_JSON_PREFIX)) {
        card.status = "error";
        card.summary = { error: { message: content } };
      } else {
        const parsed = tryParse(content);
        const status = parsed?.status;
        const recordId = parsed?.data?.record_id ?? parsed?.record_id;
        // 族生成（e2m2e 5.9.3 一轨一记录）的回执是 family_id（生成批次），
        // 不是单条记录 id——单独携带，不冒充 recordId 触发入树登记
        const familyId = parsed?.data?.family_id;
        const scenarioFile = parsed?.data?.scenario_file;
        const errMsg = parsed?.error?.message;
        card.status = status === "ok" ? "done" : "error";
        card.summary = {
          status: typeof status === "string" ? status : undefined,
          recordId: typeof recordId === "string" ? recordId : undefined,
          familyId: typeof familyId === "string" ? familyId : undefined,
          scenarioFile: typeof scenarioFile === "string" ? scenarioFile : undefined,
          error: errMsg ? { message: errMsg } : undefined,
        };
      }
    }
  }
  // 恢复后仍停在 proposed 的卡片 = 重启打断的等待确认，标记为失败以免误导
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
    case "thinking": {
      // 思考增量归并进末尾思考块；前面有正文/工具事件时开新块
      // （后端按段落切分，这里只做同块归并，ADR 0026 决策 3/4）
      const next = items.slice();
      const last = next[next.length - 1];
      if (last && last.kind === "thinking") {
        next[next.length - 1] = { kind: "thinking", text: last.text + ev.text };
      } else {
        next.push({ kind: "thinking", text: ev.text });
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
    case "tool_progress":
      // 真进度（progressToken 通知）：刷新运行中卡片的分数与消息；
      // 事件不持久化，回放时卡片回到不定态耗时显示
      return updateCard(items, ev.callId, (c) => ({
        ...c,
        progress: ev.progress,
        progressMessage: ev.message ?? undefined,
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
      return [...items, { kind: "error", text: ev.message }];
    case "interrupted":
      // 中断不是错误（#453）：用户主动停止，界限标记留存在会话流里
      return [...items, { kind: "interrupted" }];
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
