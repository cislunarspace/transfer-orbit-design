//! AI 助手 agent loop：LLM 对话循环与工具调用编排（本仓 ADR 0022/0023，
//! 多会话与思考等级 ADR 0025/0026）。
//!
//! 一轮发送的流程：
//! 1. 组装三层系统提示（角色边界 / 工具使用规则 / 现取的轨道库摘要与当前
//!    选择），连同当前会话的历史一起发给 LLM（SSE 流式，增量推前端；
//!    思考增量单列一种事件）；
//! 2. LLM 提议工具调用时：只读工具（白名单 [`READ_ONLY_TOOLS`]）直接执行；
//!    其余工具发出 `tool_proposed` 事件并挂起，等用户经
//!    `assistant_confirm_tool` 确认/改参/拒绝（ADR 0022 决策 4）；
//! 3. 工具结果经 [`summary`] 投影后进上下文（大轨迹数据不进，只带
//!    record_id 与诊断摘要），错误原文回灌供模型自纠（决策 8）；
//! 4. 最多 [`MAX_ROUNDS`] 轮后收尾（防失控循环）。
//!
//! 多会话（ADR 0025）：内存只保持当前会话的 history/pending，切换/新建/
//! 删除当前会话受 [`AssistantState::busy`] 门禁——有进行中回复或未决确认
//! 时拒绝（mcp-serve 不可取消，装死只会留假状态）。
//!
//! 思考块（ADR 0026）：SSE 思考增量实时推前端；段落结束时作为带 kind
//! 标记的行落盘（展示层存全量），构造 API 请求时剥除（回放净化，决策 5）。
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

/// 会话结构操作被门禁拦下时的提示（ADR 0025 决策 5）。
const BUSY_MSG: &str = "有回复进行中或工具确认未决，请等待完成后再切换会话";

/// 启动时无任何会话记录使用的缺省会话 id（ADR 0023 决策 7 的 v1 约定）。
const DEFAULT_SESSION: &str = "default";

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

/// 助手状态：当前会话 id 与其历史（与持久化同源）、工具清单缓存、
/// 待确认调用、单并发门禁。
pub struct AssistantState {
    /// 当前会话（None = 尚未解析，首次访问取最近活动的会话）。
    session_id: std::sync::Mutex<Option<String>>,
    history: std::sync::Mutex<Vec<Value>>,
    tools_cache: std::sync::Mutex<Option<Vec<Value>>>,
    pending: Mutex<HashMap<String, tokio::sync::oneshot::Sender<ConfirmDecision>>>,
    running: AtomicBool,
}

impl AssistantState {
    pub fn new() -> Self {
        Self {
            session_id: Mutex::new(None),
            history: Mutex::new(Vec::new()),
            tools_cache: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
            running: AtomicBool::new(false),
        }
    }

    /// 当前会话 id（懒解析：首次访问取最近活动的会话，无则 default——
    /// 与旧单会话用户的 default.jsonl 迁移衔接）。
    pub fn current_session(&self) -> String {
        let mut slot = self.session_id.lock().expect("session lock");
        if let Some(id) = slot.as_deref() {
            return id.to_string();
        }
        let id = store::load_sessions()
            .first()
            .map(|m| m.id.clone())
            .unwrap_or_else(|| DEFAULT_SESSION.to_string());
        *slot = Some(id.clone());
        id
    }

    /// 当前会话历史（assistant_get_state 的数据源；懒加载落盘文件，
    /// 含消息行与思考行）。
    pub fn history(&self) -> Vec<Value> {
        self.ensure_history_loaded();
        self.history.lock().expect("history lock").clone()
    }

    fn ensure_history_loaded(&self) {
        let mut guard = self.history.lock().expect("history lock");
        if guard.is_empty() {
            let id = self.current_session();
            *guard = store::load_session_rows(&id);
        }
    }

    /// 门禁判定（ADR 0025 决策 5）：有进行中的回复轮次或未决确认时，
    /// 禁止切换/新建/删除会话。
    fn busy(&self) -> bool {
        self.running.load(Ordering::SeqCst)
            || !self.pending.lock().expect("pending lock").is_empty()
    }

    /// 切换会话：显式载入目标会话的落盘历史（回放净化的思考行随行载入，
    /// 展示用；进 API 上下文前再剥除）。
    pub fn switch_session(&self, session_id: &str) -> anyhow::Result<()> {
        if self.busy() {
            anyhow::bail!(BUSY_MSG);
        }
        if !store::load_sessions().iter().any(|m| m.id == session_id) {
            anyhow::bail!("会话不存在：{session_id}");
        }
        *self.session_id.lock().expect("session lock") = Some(session_id.to_string());
        *self.history.lock().expect("history lock") = store::load_session_rows(session_id);
        Ok(())
    }

    /// 新建会话（思考等级继承全局默认，ADR 0026 决策 1）并切换过去。
    pub fn new_session(&self) -> anyhow::Result<String> {
        if self.busy() {
            anyhow::bail!(BUSY_MSG);
        }
        let default_level =
            llm::ThinkingLevel::parse(&store::load_model_config().thinking_level)
                .as_str()
                .to_string();
        let meta = store::create_session_entry(&default_level)
            .ok_or_else(|| anyhow::anyhow!("无用户配置目录，无法新建会话"))?;
        *self.session_id.lock().expect("session lock") = Some(meta.id.clone());
        self.history.lock().expect("history lock").clear();
        Ok(meta.id)
    }

    /// 删除会话。删当前会话受门禁；删后回到"未选"态，下次访问懒解析为
    /// 最近会话（无则 default）。
    pub fn delete_session(&self, session_id: &str) -> anyhow::Result<()> {
        let current = self.current_session();
        if session_id == current && self.busy() {
            anyhow::bail!(BUSY_MSG);
        }
        store::delete_session_entry(session_id);
        if session_id == current {
            *self.session_id.lock().expect("session lock") = None;
            self.history.lock().expect("history lock").clear();
        }
        Ok(())
    }

    pub fn rename_session(&self, session_id: &str, title: &str) -> anyhow::Result<()> {
        store::rename_session_entry(session_id, title)
    }

    /// 设当前会话的思考等级（严格校验，ADR 0026 决策 1：档位随会话记住）。
    pub fn set_thinking_level(&self, level: &str) -> anyhow::Result<()> {
        let parsed = llm::ThinkingLevel::try_parse(level)
            .ok_or_else(|| anyhow::anyhow!("未知思考等级：{level}"))?;
        store::set_session_thinking_level(&self.current_session(), parsed.as_str())
    }

    /// 当前会话生效的思考等级：会话自己的档位优先，空则继承全局默认。
    fn effective_level(&self) -> llm::ThinkingLevel {
        let id = self.current_session();
        let raw = store::load_sessions()
            .into_iter()
            .find(|m| m.id == id)
            .map(|m| m.thinking_level)
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| store::load_model_config().thinking_level);
        llm::ThinkingLevel::parse(&raw)
    }

    /// 清空当前会话（"清空重开"按钮）：内存 + 落盘文件一起清，保留会话本身。
    pub fn clear(&self) {
        self.history.lock().expect("history lock").clear();
        let id = self.current_session();
        store::clear_session_rows(&id);
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
        self.ensure_history_loaded();
        self.push_history(user_msg.clone());
        let mut messages = self.context_messages(system, user_msg);
        let level = self.effective_level();

        for _round in 0..MAX_ROUNDS {
            // 思考增量：实时推前端；段落结束时由 sink 落盘（Drop 兜底：
            // 流中途出错也不丢已收到的思考段）
            let mut think = ThinkingSink { state: self, buf: String::new(), saw_content: false };
            let reply = llm::chat_stream(&llm_cfg, &messages, &tools, level, |delta| match delta {
                llm::StreamDelta::Content(t) => {
                    think.saw_content = true;
                    emit(json!({"kind": "delta", "text": t}));
                }
                llm::StreamDelta::Thinking(t) => {
                    think.accept(t);
                    emit(json!({"kind": "thinking", "text": t}));
                }
            })
            .await?;
            think.flush();

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

        // 进度订阅：call_tool 带 progressToken（e2m2e 5.9.0+ 发
        // notifications/progress），转发为 tool_progress 事件——工具卡片
        // 由"只转圈"升级为真进度（分数 + 可读消息）。
        let progress_call_id = tc.id.clone();
        let progress_sink: crate::mcp::ProgressSink =
            std::sync::Arc::new(move |fraction, message| {
                emit(json!({"kind": "tool_progress", "callId": progress_call_id,
                            "progress": fraction, "message": message}));
            });
        let outcome = call_tool_with_retry(mcp, &tc.name, args, Some(progress_sink)).await;
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
        let outcome = call_tool_with_retry(mcp, "catalog_query", json!({}), None).await;
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
        let id = self.current_session();
        store::append_session_row(&id, &msg);
    }

    /// 思考段入历史与落盘（带 kind 标记的行，ADR 0025 决策 3 / 0026 决策 5）。
    fn push_thinking(&self, text: &str) {
        let row = json!({"kind": "thinking", "content": text});
        self.history.lock().expect("history lock").push(row.clone());
        let id = self.current_session();
        store::append_session_row(&id, &row);
    }

    /// 组装本次请求的完整上下文：系统提示 + 截断后的历史（对齐到 user
    /// 边界，不拆散 assistant tool_calls 与其 tool 结果的配对）。
    /// 回放净化（ADR 0025 决策 1 / 0026 决策 5）：思考行剥除——多数
    /// provider 协议明确要求思考块不回放；tool 消息本身已是写时投影摘要，
    /// 悬空 record_id 由此天然降级，不依赖 catalog 现状。
    fn context_messages(&self, system: String, user_msg: Value) -> Vec<Value> {
        let history = self.history();
        // user_msg 刚 push 进 history，末位即是；历史截断时保留它
        let keep_from = truncate_index(&history, 50);
        let mut messages = vec![json!({"role": "system", "content": system})];
        messages.extend(history[keep_from..].iter().filter(|r| !is_thinking_row(r)).cloned());
        debug_assert_eq!(messages.last(), Some(&user_msg));
        messages
    }
}

/// 思考行判定：会话文件里带 kind:"thinking" 标记的行（消息行无 kind）。
fn is_thinking_row(row: &Value) -> bool {
    row.get("kind").and_then(Value::as_str) == Some("thinking")
}

/// 思考增量汇聚器：正文出现后再来的思考增量开新块；块结束时整段作为
/// 一行思考记录落盘（展示层存全量，回放由 context 过滤，ADR 0026 决策 3/5）。
struct ThinkingSink<'a> {
    state: &'a AssistantState,
    buf: String,
    saw_content: bool,
}

impl ThinkingSink<'_> {
    fn accept(&mut self, t: &str) {
        if self.saw_content {
            self.flush(); // 正文之后再来的思考：结束上一段、开新块
            self.saw_content = false;
        }
        self.buf.push_str(t);
    }

    fn flush(&mut self) {
        if self.buf.is_empty() {
            return;
        }
        let text = std::mem::take(&mut self.buf);
        self.state.push_thinking(&text);
    }
}

impl Drop for ThinkingSink<'_> {
    fn drop(&mut self) {
        self.flush();
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

    #[test]
    fn replay_strips_thinking_rows_but_keeps_pairing() {
        // 回放净化：思考行剥除；夹在 assistant(tool_calls) 与 tool 结果
        // 之间的思考行不影响配对完整
        let history = vec![
            json!({"role": "user", "content": "q"}),
            json!({"kind": "thinking", "content": "想一想"}),
            json!({"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"}}]}),
            json!({"kind": "thinking", "content": "看结果"}),
            json!({"role": "tool", "tool_call_id": "c1", "content": "{}"}),
            json!({"role": "assistant", "content": "答"}),
        ];
        let stripped: Vec<Value> = history.iter().filter(|r| !is_thinking_row(r)).cloned().collect();
        assert_eq!(stripped.len(), 4);
        assert!(stripped.iter().all(|r| !is_thinking_row(r)));
        // 配对完整：截断点从 stripped 上对齐 user 边界后，tool_calls 与 tool 仍在同窗
        let idx = truncate_index(&stripped, 50);
        assert_eq!(idx, 0);
        let roles: Vec<&str> = stripped[idx..].iter().filter_map(|r| r.get("role").and_then(Value::as_str)).collect();
        assert_eq!(roles, vec!["user", "assistant", "tool", "assistant"]);
    }

    #[test]
    fn truncation_skips_thinking_rows_to_find_user_boundary() {
        let mut history: Vec<Value> = vec![];
        for i in 0..30 {
            history.push(json!({"role": "user", "content": format!("m{i}")}));
            history.push(json!({"kind": "thinking", "content": "t"}));
            history.push(json!({"role": "assistant", "content": "a"}));
        }
        let idx = truncate_index(&history, 50);
        assert_eq!(history[idx].get("role").and_then(Value::as_str), Some("user"), "截断点必须落在 user 消息上，思考行不能充当边界");
        assert!(history.len() - idx <= 50);
    }
}
