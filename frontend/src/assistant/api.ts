// AI 助手的前端封装：Tauri command 调用 + assistant-event 事件类型。
// Frontend wrapper for the AI assistant: Tauri command calls plus assistant-event types.
// 设计依据：docs/adr/0022（定位与策略）、0023（Rust 宿主 agent loop + MCP 拓扑）。

export interface AssistantInfo {
  configured: boolean;
  baseUrl: string;
  model: string;
  hasKey: boolean;
  /** 持久化会话（OpenAI 消息形状，用于重启后恢复显示） */
  history: RawMessage[];
}

/** 持久化的原始消息（OpenAI 形状；前端据此重建气泡与工具卡片） */
export interface RawMessage {
  role: "user" | "assistant" | "tool" | "system";
  content?: string | null;
  tool_calls?: { id: string; function: { name: string; arguments: string } }[];
  tool_call_id?: string;
}

export type AssistantEventPayload =
  | { kind: "delta"; text: string }
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
): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("assistant_set_config", { baseUrl, model, apiKey: apiKey ?? null });
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

/** 订阅助手事件流；返回退订函数。 */
/** Subscribe to the assistant event stream; returns the unlisten function. */
export async function onAssistantEvent(
  cb: (payload: AssistantEventPayload) => void,
): Promise<() => void> {
  const { listen } = await import("@tauri-apps/api/event");
  return listen<AssistantEventPayload>("assistant-event", (ev) => cb(ev.payload));
}
