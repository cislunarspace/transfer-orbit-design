//! AI 助手命令：前端经 IPC 调用（本仓 ADR 0022/0023）。

use serde::Serialize;
use serde_json::Value;
use tauri::State;

use crate::assistant::{llm, store, AssistantState, ConfirmDecision};
use crate::mcp::McpState;

/// 助手总状态（设置面板与边栏空态的数据源）。key 永不返回前端——
/// 只回 has_key 布尔位（ADR 0023 决策 1：key 不进 webview JS 上下文）。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AssistantInfo {
    pub configured: bool,
    pub base_url: String,
    pub model: String,
    pub has_key: bool,
    pub history: Vec<Value>,
    /// 当前会话 id（ADR 0025）
    pub current_session_id: String,
    /// 会话列表（最近活动倒序，ADR 0025 决策 3）
    pub sessions: Vec<store::SessionMeta>,
    /// 当前会话生效的思考等级（off/standard/deep，ADR 0026 决策 1）
    pub thinking_level: String,
    /// 全局默认思考等级（设置面板；新会话继承）
    pub default_thinking_level: String,
}

#[tauri::command]
pub async fn assistant_get_state(state: State<'_, AssistantState>) -> Result<AssistantInfo, String> {
    let cfg = store::load_model_config();
    let sessions = store::load_sessions();
    let current = state.current_session();
    let default_thinking_level = llm::ThinkingLevel::parse(&cfg.thinking_level)
        .as_str()
        .to_string();
    let thinking_level = sessions
        .iter()
        .find(|m| m.id == current)
        .map(|m| m.thinking_level.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default_thinking_level.clone());
    Ok(AssistantInfo {
        configured: state.configured(),
        base_url: cfg.base_url,
        model: cfg.model,
        has_key: store::load_api_key().is_some(),
        history: state.history(),
        current_session_id: current,
        sessions,
        thinking_level,
        default_thinking_level,
    })
}

/// 保存模型服务配置。api_key 传 None/空串表示不动现有 key；
/// thinking_level 传 None 表示不动全局默认思考等级。
#[tauri::command]
pub async fn assistant_set_config(
    base_url: String,
    model: String,
    api_key: Option<String>,
    thinking_level: Option<String>,
) -> Result<(), String> {
    let old = store::load_model_config();
    let mut cfg = store::ModelConfig {
        base_url: base_url.trim().to_string(),
        model: model.trim().to_string(),
        thinking_level: old.thinking_level,
    };
    if let Some(level) = thinking_level {
        let parsed = llm::ThinkingLevel::try_parse(&level)
            .ok_or_else(|| format!("未知思考等级：{level}"))?;
        cfg.thinking_level = parsed.as_str().to_string();
    }
    store::save_model_config(&cfg).map_err(|e| e.to_string())?;
    if let Some(key) = api_key {
        if !key.trim().is_empty() {
            store::save_api_key(key.trim()).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// 测试连接（设置面板的"测试"按钮）：GET /models 探活。
#[tauri::command]
pub async fn assistant_test_config() -> Result<String, String> {
    let cfg = store::load_model_config();
    let key = store::load_api_key();
    if !cfg.is_complete() || key.is_none() {
        return Err("请先完整填写 base URL、模型名与 API key".into());
    }
    let llm_cfg = llm::LlmConfig {
        base_url: cfg.base_url,
        api_key: key.expect("已检查"),
        model: cfg.model,
    };
    let n = llm::test_connection(&llm_cfg).await.map_err(|e| e.to_string())?;
    Ok(format!("连接成功（服务暴露 {n} 个模型）"))
}

/// 发送一条用户消息。整轮 agent loop 在此期间经 `assistant-event`
/// 流式推送；命令在本轮结束时返回（仅早期错误经返回值上抛，运行期
/// 错误走 error 事件）。
#[tauri::command]
pub async fn assistant_send(
    state: State<'_, AssistantState>,
    mcp: State<'_, McpState>,
    message: String,
    lang: String,
    selection: Option<Value>,
) -> Result<(), String> {
    if message.trim().is_empty() {
        return Err("空消息".into());
    }
    state.send(&mcp, &message, &lang, selection).await.map_err(|e| e.to_string())
}

/// 用户确认/拒绝一次工具调用提议；arguments 为用户改过的参数（None =
/// 用 LLM 原参数）。返回 false 表示该调用已不在等待（重复点击等）。
#[tauri::command]
pub async fn assistant_confirm_tool(
    state: State<'_, AssistantState>,
    call_id: String,
    approved: bool,
    arguments: Option<Value>,
) -> Result<bool, String> {
    Ok(state.resolve_confirm(&call_id, ConfirmDecision { approved, arguments }))
}

/// 清空当前会话（"清空重开"）：内存历史 + 落盘文件一起清，保留会话本身。
#[tauri::command]
pub async fn assistant_clear_history(state: State<'_, AssistantState>) -> Result<(), String> {
    state.clear();
    Ok(())
}

/// 新建会话并切换过去（受切换门禁，ADR 0025 决策 5）。返回新会话 id。
#[tauri::command]
pub async fn assistant_new_session(state: State<'_, AssistantState>) -> Result<String, String> {
    state.new_session().map_err(|e| e.to_string())
}

/// 切换当前会话（受切换门禁；目标会话的落盘历史随切换载入）。
#[tauri::command]
pub async fn assistant_switch_session(
    state: State<'_, AssistantState>,
    session_id: String,
) -> Result<(), String> {
    state.switch_session(&session_id).map_err(|e| e.to_string())
}

/// 重命名会话（下拉项悬浮操作，ADR 0025 决策 4）。
#[tauri::command]
pub async fn assistant_rename_session(
    state: State<'_, AssistantState>,
    session_id: String,
    title: String,
) -> Result<(), String> {
    state
        .rename_session(&session_id, &title)
        .map_err(|e| e.to_string())
}

/// 删除会话（二次确认在前端；删当前会话受切换门禁）。
#[tauri::command]
pub async fn assistant_delete_session(
    state: State<'_, AssistantState>,
    session_id: String,
) -> Result<(), String> {
    state.delete_session(&session_id).map_err(|e| e.to_string())
}

/// 设当前会话的思考等级（输入区旁三档单选，ADR 0026 决策 1）。
#[tauri::command]
pub async fn assistant_set_thinking_level(
    state: State<'_, AssistantState>,
    level: String,
) -> Result<(), String> {
    state.set_thinking_level(&level).map_err(|e| e.to_string())
}
