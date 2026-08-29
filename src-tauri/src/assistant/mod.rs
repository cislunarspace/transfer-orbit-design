//! AI 助手 agent loop：LLM 对话循环与工具调用编排（本仓 ADR 0022/0023）。
//!
//! 一轮发送的流程：
//! 1. 组装三层系统提示（角色边界 / 工具使用规则 / 现取的轨道库摘要与当前
//!    选择），连同持久化的会话历史一起发给 LLM（SSE 流式，增量推前端）；
//! 2. LLM 提议工具调用时：只读工具（白名单 [`READ_ONLY_TOOLS`]）直接执行；
//!    其余工具发出 `tool_proposed` 事件并挂起，等用户经
//!    `assistant_confirm_tool` 确认/改参/拒绝（ADR 0022 决策 4）；
//! 3. 工具结果经 [`summary`] 投影后进上下文（大轨迹数据不进，只带
//!    record_id 与诊断摘要），错误原文回灌供模型自纠（决策 8）；
//! 4. 最多 [`MAX_ROUNDS`] 轮后收尾（防失控循环）。
//!
//! 验证链挂点（ADR 0023 决策 4）：[`check_call`] / [`check_result`] 是
//! 可插拔检查链的两个钩子，模式三场景层的物理可行性验证器将来挂在这里。
//!
//! 并发：同一时刻只跑一轮对话（`running` 门禁）；MCP 调用本身可并发
//! （mcp-serve 线程池），但串行更利于用户逐条确认，v1 保持串行。

pub mod llm;
pub mod prompt;
pub mod store;
pub mod summary;

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};

use serde_json::{json, Value};

use crate::mcp::{call_tool_with_retry, list_tools_with_retry, McpState};

/// 前端监听的事件名。
pub const ASSISTANT_EVENT: &str = "assistant-event";

/// 一轮发送最多允许的 LLM 往返轮数（含工具自纠），防失控循环。
const MAX_ROUNDS: usize = 10;

/// 只读工具白名单（ADR 0022 决策 4）：免确认直接执行。
/// 来源：e2m2e facade 工具清单（5.8.x）中不运行数值计算、不改变状态的
/// 仅有两个 catalog 查询。fail-closed：不在名单里的一律要确认。
const READ_ONLY_TOOLS: &[&str] = &["catalog_query", "catalog_get"];

/// 事件发射器（setup 时注入 AppHandle 包装；测试注入 fake）。
pub type AssistantEmitter = Arc<dyn Fn(&Value) + Send + Sync>;
static EMITTER: OnceLock<AssistantEmitter> = OnceLock::new();

pub fn set_emitter(e: AssistantEmitter) {
    let _ = EMITTER.set(e);
}

fn emit(payload: Value) {
    if let Some(emit) = EMITTER.get() {
        emit(&payload);
    }
}

/// 用户对一次工具调用提议的决定。
pub struct ConfirmDecision {
    pub approved: bool,
    /// 用户改过的参数（None = 用 LLM 原参数）。
    pub arguments: Option<Value>,
}

/// 助手状态：会话历史（与持久化同源）、工具清单缓存、待确认调用、
/// 单并发门禁。
pub struct AssistantState {
    history: std::sync::Mutex<Vec<Value>>,
    tools_cache: std::sync::Mutex<Option<Vec<Value>>>,
    pending: Mutex<HashMap<String, tokio::sync::oneshot::Sender<ConfirmDecision>>>,
    running: AtomicBool,
}

impl AssistantState {
    pub fn new() -> Self {
        Self {
            history: Mutex::new(Vec::new()),
            tools_cache: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
            running: AtomicBool::new(false),
        }
    }

    /// 当前会话历史（assistant_get_state 的数据源；懒加载落盘文件）。
    pub fn history(&self) -> Vec<Value> {
        let mut guard = self.history.lock().expect("history lock");
        if guard.is_empty() {
            *guard = store::load_session();
        }
        guard.clone()
    }

    /// 清空会话（内存 + 落盘）。
    pub fn clear(&self) {
        self.history.lock().expect("history lock").clear();
        store::clear_session();
    }

    /// 是否已配置可用（设置面板与空态引导的判定）。
    pub fn configured(&self) -> bool {
        store::load_model_config().is_complete() && store::load_api_key().is_some()
    }

    /// 解决一次挂起的工具确认（assistant_confirm_tool 命令的落点）。
    /// 返回 false 表示该 call_id 没有挂起的等待（已超时/重复点击）。
    pub fn resolve_confirm(&self, call_id: &str, decision: ConfirmDecision) -> bool {
        if let Some(tx) = self.pending.lock().expect("pending lock").remove(call_id) {
            let _ = tx.send(decision);
            true
        } else {
            false
        }
    }

    /// 发送一条用户消息并跑完整轮 agent loop（流式经事件推送）。
    ///
    /// 单并发：上一轮没跑完时拒绝新发送（前端应已禁用输入，这里是兜底）。
    pub async fn send(
        &self,
        mcp: &McpState,
        message: &str,
        lang: &str,
        selection: Option<Value>,
    ) -> anyhow::Result<()> {
        if self.running.swap(true, Ordering::SeqCst) {
            anyhow::bail!("上一轮对话仍在进行");
        }
        let result = self.run(mcp, message, lang, selection).await;
        self.running.store(false, Ordering::SeqCst);
        if let Err(e) = &result {
            emit(json!({"kind": "error", "message": e.to_string()}));
        }
        result
    }

    async fn run(
        &self,
        mcp: &McpState,
        message: &str,
        lang: &str,
        selection: Option<Value>,
    ) -> anyhow::Result<()> {
        let cfg = store::load_model_config();
        let api_key = store::load_api_key();
        if !cfg.is_complete() || api_key.is_none() {
            anyhow::bail!("模型服务未配置：请先在设置面板 AI 助手分区填写 base URL、模型名与 API key");
        }
        let llm_cfg = llm::LlmConfig {
            base_url: cfg.base_url,
            api_key: api_key.expect("上方已检查"),
            model: cfg.model,
        };

        // 工具清单（首次拉取后缓存；MCP→OpenAI 格式转换在同一处做）
        let tools = self.cached_tools(mcp).await?;

        // 态势层：轨道库摘要现取（只读工具，失败降级为提示，不阻断对话）
        let catalog_summary = self.catalog_summary(mcp).await;
        let selection_text = selection.as_ref().map(|v| compact_json(v));
        let now_utc = now_utc_text();
        let system = prompt::system_prompt(lang, &catalog_summary, selection_text.as_deref(), &now_utc);

        let user_msg = json!({"role": "user", "content": message});
        self.push_history(user_msg.clone());
        let mut messages = self.context_messages(system, user_msg);

        for _round in 0..MAX_ROUNDS {
            let reply = llm::chat_stream(&llm_cfg, &messages, &tools, |delta| {
                emit(json!({"kind": "delta", "text": delta}));
            })
            .await?;

            // 助手消息入历史（OpenAI 形状：content + 可选 tool_calls）
            let mut assistant_msg = json!({"role": "assistant", "content": reply.text});
            if !reply.tool_calls.is_empty() {
                assistant_msg["tool_calls"] = Value::Array(
                    reply
                        .tool_calls
                        .iter()
                        .map(|tc| {
                            json!({
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": tc.arguments},
                            })
                        })
                        .collect(),
                );
            }
            self.push_history(assistant_msg.clone());
            messages.push(assistant_msg);

            if reply.tool_calls.is_empty() {
                emit(json!({"kind": "message_done", "usage": reply.usage}));
                return Ok(());
            }

            for tc in &reply.tool_calls {
                let tool_msg = self.execute_call(mcp, tc).await;
                self.push_history(tool_msg.clone());
                messages.push(tool_msg);
            }
        }
        anyhow::bail!("对话轮数超过上限（{MAX_ROUNDS}），已中止；请缩小任务范围或分步提问")
    }

    /// 执行一次工具调用：只读直接跑；其余挂起等确认。返回进上下文的
    /// tool 消息（OpenAI 形状）。
    async fn execute_call(&self, mcp: &McpState, tc: &llm::ToolCall) -> Value {
        // LLM 给的 arguments 是 JSON 文本；坏 JSON 直接回灌错误让模型自纠
        let args: Value = match serde_json::from_str(&tc.arguments) {
            Ok(v) => v,
            Err(e) => {
                emit(json!({"kind": "tool_done", "callId": tc.id, "tool": tc.name,
                            "ok": false, "summary": {"status": "error"}}));
                return tool_message(&tc.id, &format!("工具参数不是合法 JSON：{e}。请修正参数后重试同一工具。"));
            }
        };

        let approved_args = if is_read_only(&tc.name) {
            emit(json!({"kind": "tool_started", "callId": tc.id, "tool": tc.name, "arguments": args}));
            Some(args)
        } else {
            emit(json!({"kind": "tool_proposed", "callId": tc.id, "tool": tc.name, "arguments": args}));
            match self.wait_confirm(&tc.id).await {
                ConfirmDecision { approved: true, arguments } => {
                    let final_args = arguments.unwrap_or(args);
                    emit(json!({"kind": "tool_started", "callId": tc.id, "tool": tc.name, "arguments": final_args}));
                    Some(final_args)
                }
                ConfirmDecision { approved: false, .. } => {
                    emit(json!({"kind": "tool_rejected", "callId": tc.id, "tool": tc.name}));
                    return tool_message(&tc.id, "用户拒绝了本次工具调用，未执行。请尊重用户决定，改换方案或询问原因。");
                }
            }
        };
        let Some(args) = approved_args else { unreachable!("分支已全覆盖") };

        // 验证链挂点（ADR 0023 决策 4）：调用前检查
        if let Err(reason) = check_call(&tc.name, &args) {
            emit(json!({"kind": "tool_done", "callId": tc.id, "tool": tc.name,
                        "ok": false, "summary": {"status": "error", "error": {"message": reason}}}));
            return tool_message(&tc.id, &format!("调用被验证链拒绝：{reason}"));
        }

        let outcome = call_tool_with_retry(mcp, &tc.name, args).await;
        let (ok, text) = match outcome {
            Ok(out) => (!out.is_error, out.text),
            Err(e) => (false, format!("工具调用失败：{e}")),
        };

        // 验证链挂点：结果检查（当前只投影摘要；物理可行性验证器后补）
        let projected = check_result(&tc.name, &text);
        let summary = summary::card_summary(&text);
        emit(json!({"kind": "tool_done", "callId": tc.id, "tool": tc.name,
                    "ok": ok, "summary": summary}));
        tool_message(&tc.id, &serde_json::to_string(&projected).unwrap_or_else(|_| text.clone()))
    }

    async fn wait_confirm(&self, call_id: &str) -> ConfirmDecision {
        let (tx, rx) = tokio::sync::oneshot::channel();
        self.pending
            .lock()
            .expect("pending lock")
            .insert(call_id.to_string(), tx);
        // 无超时：确认是用户动作，可以等任意久（app 退出时循环随之消失）
        rx.await.unwrap_or(ConfirmDecision { approved: false, arguments: None })
    }

    async fn cached_tools(&self, mcp: &McpState) -> anyhow::Result<Vec<Value>> {
        if let Some(tools) = self.tools_cache.lock().expect("tools lock").clone() {
            return Ok(tools);
        }
        let mcp_tools = list_tools_with_retry(mcp).await?;
        let tools: Vec<Value> = mcp_tools.iter().filter_map(llm::mcp_tool_to_openai).collect();
        if tools.is_empty() {
            anyhow::bail!("mcp-serve 未暴露任何工具（e2m2e 工具清单为空）");
        }
        *self.tools_cache.lock().expect("tools lock") = Some(tools.clone());
        Ok(tools)
    }

    /// 轨道库摘要（态势层素材）：catalog_query 取最近记录，投影为紧凑
    /// 清单。失败时返回说明文字——对话不应因摘要不可用而中断。
    async fn catalog_summary(&self, mcp: &McpState) -> String {
        let outcome = call_tool_with_retry(mcp, "catalog_query", json!({})).await;
        match outcome {
            Ok(out) if !out.is_error => {
                let projected = summary::project_for_llm(&out.text);
                compact_json(&projected)
            }
            Ok(out) => format!("（轨道库查询返回错误：{}）", out.text.chars().take(200).collect::<String>()),
            Err(e) => format!("（轨道库摘要不可用：{e}）"),
        }
    }

    fn push_history(&self, msg: Value) {
        self.history.lock().expect("history lock").push(msg.clone());
        store::append_session(&msg);
    }

    /// 组装本次请求的完整上下文：系统提示 + 截断后的历史（对齐到 user
    /// 边界，不拆散 assistant tool_calls 与其 tool 结果的配对）。
    fn context_messages(&self, system: String, user_msg: Value) -> Vec<Value> {
        let history = self.history();
        // user_msg 刚 push 进 history，末位即是；历史截断时保留它
        let keep_from = truncate_index(&history, 50);
        let mut messages = vec![json!({"role": "system", "content": system})];
        messages.extend(history[keep_from..].iter().cloned());
        debug_assert_eq!(messages.last(), Some(&user_msg));
        messages
    }
}

/// 历史截断点：保留最近 `max` 条，且起点必须落在 user 消息上（保证
/// assistant 的 tool_calls 与其 tool 结果不拆对——OpenAI 对孤立 tool
/// 消息直接报错）。从 len-max 向前找下一个 user 边界，截断后不超 max。
fn truncate_index(history: &[Value], max: usize) -> usize {
    if history.len() <= max {
        return 0;
    }
    let mut idx = history.len() - max;
    // 最多走到末位（调用方保证末位是刚 push 的 user 消息，必为边界）
    while idx < history.len() - 1
        && history[idx].get("role").and_then(Value::as_str) != Some("user")
    {
        idx += 1;
    }
    idx
}

/// 只读判定（fail-closed：不在白名单的一律要确认）。
fn is_read_only(tool: &str) -> bool {
    READ_ONLY_TOOLS.contains(&tool)
}

/// 验证链：调用前检查（模式三物理可行性验证器的挂点，当前只做形状检查）。
fn check_call(_tool: &str, args: &Value) -> Result<(), String> {
    if args.is_object() {
        Ok(())
    } else {
        Err("工具参数必须是 JSON 对象".into())
    }
}

/// 验证链：结果检查（当前只做摘要投影，结果一律放行）。
fn check_result(_tool: &str, envelope_text: &str) -> Value {
    summary::project_for_llm(envelope_text)
}

fn tool_message(call_id: &str, content: &str) -> Value {
    json!({"role": "tool", "tool_call_id": call_id, "content": content})
}

fn compact_json(v: &Value) -> String {
    serde_json::to_string(v).unwrap_or_default()
}

fn now_utc_text() -> String {
    // 不引 chrono：秒级时间戳转 ISO 文本交给系统提示的语义即可，
    // 这里直接用 Unix 秒 + 明确标注，避免为显示格式引入依赖。
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("当前 Unix 时间戳 {secs} 秒（UTC）")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn read_only_whitelist_is_fail_closed() {
        assert!(is_read_only("catalog_query"));
        assert!(is_read_only("catalog_get"));
        assert!(!is_read_only("design_orbit"));
        assert!(!is_read_only("catalog_delete"));
        assert!(!is_read_only("future_unknown_tool"), "未知工具必须走确认");
    }

    #[test]
    fn truncation_aligns_to_user_boundary() {
        let mut history: Vec<Value> = vec![];
        for i in 0..60 {
            let role = if i % 3 == 0 { "user" } else { "assistant" };
            history.push(json!({"role": role, "content": format!("m{i}")}));
        }
        let idx = truncate_index(&history, 50);
        assert_eq!(history[idx]["role"], "user", "截断点必须在 user 消息上");
        assert!(history.len() - idx <= 50);
    }

    #[test]
    fn short_history_is_not_truncated() {
        let history = vec![json!({"role": "user", "content": "hi"})];
        assert_eq!(truncate_index(&history, 50), 0);
    }
}
