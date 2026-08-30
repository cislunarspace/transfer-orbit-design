// AI 助手的前端封装：Tauri command 调用 + assistant-event 事件类型。
// Frontend wrapper for the AI assistant: Tauri command calls plus assistant-event types.
// 设计依据：docs/adr/0022（定位与策略）、0023（Rust 宿主 agent loop + MCP 拓扑）、
// 0025（会话历史与多会话）、0026（思考等级与思考块）。

/// 思考等级三档（ADR 0026 决策 1）。
export type ThinkingLevel = "off" | "standard" | "deep";

/** 会话元数据（sessions/index.json 的一行，ADR 0025 决策 3） */
export interface SessionMeta {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  /** 本会话思考等级；空串 = 继承全局默认 */
  thinkingLevel: string;
}

export interface AssistantInfo {
  configured: boolean;
  baseUrl: string;
  model: string;
  hasKey: boolean;
  /** 当前会话的持久化历史（OpenAI 消息 + 思考行，用于重启后恢复显示） */
  history: RawMessage[];
  currentSessionId: string;
  /** 会话列表（最近活动倒序） */
  sessions: SessionMeta[];
  /** 当前会话生效的思考等级 */
  thinkingLevel: ThinkingLevel;
  /** 全局默认思考等级（设置面板；新会话继承） */
  defaultThinkingLevel: ThinkingLevel;
}

/** 持久化的思考行（带 kind 标记，与消息行混入同一会话文件，ADR 0025 决策 3） */
export interface ThinkingRow {
  kind: "thinking";
  content: string;
}

/** 持久化的消息行（OpenAI 形状；前端据此重建气泡与工具卡片） */
export interface MessageRow {
  role: "user" | "assistant" | "tool" | "system";
  content?: string | null;
  tool_calls?: { id: string; function: { name: string; arguments: string } }[];
  tool_call_id?: string;
}

export type RawMessage = MessageRow | ThinkingRow;

export type AssistantEventPayload =
  | { kind: "delta"; text: string }
  | { kind: "thinking"; text: string }
  | { kind: "tool_proposed"; callId: string; tool: string; arguments: unknown }
  | { kind: "tool_started"; callId: string; tool: string; arguments: unknown }
  | {
      kind: "tool_done";
      callId: string;
      tool: string;
      ok: boolean;
      summary: { status?: string; recordId?: string; error?: { message?: string } };
    }
  | { kind: "tool_rejected"; callId: string; tool: string }
  | { kind: "message_done"; usage?: { total_tokens?: number } | null }
  | { kind: "error"; message: string };

export async function assistantGetState(): Promise<AssistantInfo> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_get_state");
}

export async function assistantSetConfig(
  baseUrl: string,
  model: string,
  apiKey?: string,
  thinkingLevel?: ThinkingLevel,
): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_set_config", {
    baseUrl,
    model,
    apiKey: apiKey ?? null,
    thinkingLevel: thinkingLevel ?? null,
  });
}

export async function assistantTestConfig(): Promise<string> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_test_config");
}

export interface SelectionContext {
  recordId?: string | null;
  label: string;
  artifactType: string;
  orbitType?: string;
}

export async function assistantSend(
  message: string,
  lang: string,
  selection: SelectionContext | null,
): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_send", { message, lang, selection });
}

export async function assistantConfirmTool(
  callId: string,
  approved: boolean,
  arguments_?: unknown,
): Promise<boolean> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_confirm_tool", { callId, approved, arguments: arguments_ ?? null });
}

export async function assistantClearHistory(): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_clear_history");
}

/** 新建会话并切换过去（受切换门禁）；返回新会话 id（ADR 0025 决策 2）。 */
export async function assistantNewSession(): Promise<string> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_new_session");
}

/** 切换当前会话（受切换门禁）；历史随切换载入。 */
export async function assistantSwitchSession(sessionId: string): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_switch_session", { sessionId });
}

/** 重命名会话（下拉项悬浮操作，ADR 0025 决策 4）。 */
export async function assistantRenameSession(sessionId: string, title: string): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_rename_session", { sessionId, title });
}

/** 删除会话（前端二次确认；后端另有切换门禁兜底）。 */
export async function assistantDeleteSession(sessionId: string): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_delete_session", { sessionId });
}

/** 设当前会话的思考等级（输入区旁三档单选，ADR 0026 决策 1）。 */
export async function assistantSetThinkingLevel(level: ThinkingLevel): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_set_thinking_level", { level });
}

/** 订阅助手事件流；返回退订函数。 */
/** Subscribe to the assistant event stream; returns the unlisten function. */
export async function onAssistantEvent(
  cb: (payload: AssistantEventPayload) => void,
): Promise<() => void> {
  const { listen } = await import("@tauri-apps/api/event");
  return listen<AssistantEventPayload>("assistant-event", (ev) => cb(ev.payload));
}
