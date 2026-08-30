//! OpenAI 兼容协议的 LLM client（SSE 流式；本仓 ADR 0022 决策 5 /
//! ADR 0023 决策 1，思考等级映射 ADR 0026 决策 2/3）。
//!
//! 只实现 agent loop 需要的最小面：`POST {base_url}/chat/completions`
//! （stream=true, tools, stream_options.include_usage, 思考参数按 provider
//! 方言并入）。Anthropic 原生协议等后续协议经同一调用点替换/扩展（client
//! 抽象即本模块）。

use serde_json::{json, Value};

/// 思考等级三档（ADR 0026 决策 1）：关 / 标准 / 深度。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ThinkingLevel {
    Off,
    #[default]
    Standard,
    Deep,
}

impl ThinkingLevel {
    /// 严格解析：仅认三个合法值，其余 None（用于校验用户输入/IPC 参数）。
    pub fn try_parse(s: &str) -> Option<Self> {
        match s {
            "off" => Some(Self::Off),
            "standard" => Some(Self::Standard),
            "deep" => Some(Self::Deep),
            _ => None,
        }
    }

    /// 宽松解析：空缺/未知一律归标准档（用于读配置默认值）。
    pub fn parse(s: &str) -> Self {
        Self::try_parse(s).unwrap_or_default()
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Standard => "standard",
            Self::Deep => "deep",
        }
    }
}

/// 模型服务平台（按 base_url 判定，判定不到走兑底，ADR 0026 决策 2）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provider {
    DeepSeek,
    /// 通义/百炼（DashScope 兼容模式）
    DashScope,
    Kimi,
    /// Ollama / LM Studio / 未识别平台：只发 OpenAI 风格 reasoning_effort
    Generic,
}

/// 按 base_url 子串判定平台（映射表的判定列，勿改）。
pub fn detect_provider(base_url: &str) -> Provider {
    let url = base_url.to_ascii_lowercase();
    if url.contains("api.deepseek.com") {
        Provider::DeepSeek
    } else if url.contains("dashscope.aliyuncs.com") {
        Provider::DashScope
    } else if url.contains("api.moonshot.cn") {
        Provider::Kimi
    } else {
        Provider::Generic
    }
}

/// 档位 → 各家协议参数（并入请求体的对象）。数值与档位语义是 ADR 0026
/// 决策 2 拍板的映射表，勿改。纪律：标准档不发强度参数（只开思考，用
/// 服务端默认强度）；只有开关的 provider（Kimi）标准与深度如实合并。
pub fn thinking_params(provider: Provider, level: ThinkingLevel) -> Value {
    match (provider, level) {
        (Provider::DeepSeek, ThinkingLevel::Off) => json!({"thinking": {"type": "disabled"}}),
        (Provider::DeepSeek, ThinkingLevel::Standard) => json!({"thinking": {"type": "enabled"}}),
        (Provider::DeepSeek, ThinkingLevel::Deep) => {
            json!({"thinking": {"type": "enabled"}, "reasoning_effort": "high"})
        }
        (Provider::DashScope, ThinkingLevel::Off) => json!({"enable_thinking": false}),
        (Provider::DashScope, ThinkingLevel::Standard) => json!({"enable_thinking": true}),
        (Provider::DashScope, ThinkingLevel::Deep) => {
            json!({"enable_thinking": true, "thinking_budget": 16384})
        }
        (Provider::Kimi, ThinkingLevel::Off) => json!({"thinking": {"type": "disabled"}}),
        (Provider::Kimi, ThinkingLevel::Standard) | (Provider::Kimi, ThinkingLevel::Deep) => {
            json!({"thinking": {"type": "enabled"}})
        }
        (Provider::Generic, ThinkingLevel::Off) => json!({"reasoning_effort": "none"}),
        (Provider::Generic, ThinkingLevel::Standard) => json!({"reasoning_effort": "low"}),
        (Provider::Generic, ThinkingLevel::Deep) => json!({"reasoning_effort": "high"}),
    }
}

/// 连接超时（流建立后不设总时限：长推理响应可达分钟级，靠逐块空闲
/// 超时兜底挂死）。
const CONNECT_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(30);
/// 流式响应的逐块空闲超时：超过此时长没有任何字节到达视为挂死。
const IDLE_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(180);

#[derive(Debug, Clone)]
pub struct LlmConfig {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
}

/// 一次助手回复的汇聚结果：正文 + 工具调用 + token 用量。
#[derive(Debug, Default)]
pub struct AssistantReply {
    pub text: String,
    pub tool_calls: Vec<ToolCall>,
    pub usage: Option<Value>,
}

/// OpenAI 工具调用（arguments 为 JSON 文本，由服务端流式分片送达）。
#[derive(Debug, Clone)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub arguments: String,
}

/// MCP Tool → OpenAI function 定义（inputSchema 原样作为 parameters——
/// 与前端 toolSchemas 同源，都是 Pydantic 导出的标准 JSON Schema）。
pub fn mcp_tool_to_openai(tool: &Value) -> Option<Value> {
    let name = tool.get("name")?.as_str()?;
    let description = tool
        .get("description")
        .and_then(Value::as_str)
        .unwrap_or("");
    let parameters = tool
        .get("inputSchema")
        .cloned()
        .unwrap_or_else(|| json!({"type": "object", "properties": {}}));
    Some(json!({
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }))
}

/// 流式增量：正文与思考（思考增量与 delta 并列，ADR 0026 决策 3）。
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum StreamDelta<'a> {
    Content(&'a str),
    Thinking(&'a str),
}

/// 流式对话补全。`on_delta` 收正文/思考增量（用于前端流式渲染与思考行
/// 落盘）；返回汇聚后的完整回复（含工具调用）。
pub async fn chat_stream(
    cfg: &LlmConfig,
    messages: &[Value],
    tools: &[Value],
    level: ThinkingLevel,
    mut on_delta: impl FnMut(StreamDelta<'_>),
) -> anyhow::Result<AssistantReply> {
    let url = format!("{}/chat/completions", cfg.base_url.trim_end_matches('/'));
    let client = reqwest::Client::builder()
        .connect_timeout(CONNECT_TIMEOUT)
        .build()?;
    let mut body = json!({
        "model": cfg.model,
        "messages": messages,
        "stream": true,
        "stream_options": {"include_usage": true},
    });
    if !tools.is_empty() {
        body["tools"] = Value::Array(tools.to_vec());
    }
    // 思考参数按 provider 方言并入（映射不到的字段不覆盖已有键）
    if let Some(extra) = thinking_params(detect_provider(&cfg.base_url), level).as_object() {
        for (k, v) in extra {
            body[k.as_str()] = v.clone();
        }
    }

    let resp = client
        .post(&url)
        .bearer_auth(&cfg.api_key)
        .json(&body)
        .send()
        .await
        .map_err(|e| anyhow::anyhow!("连接模型服务失败：{e}"))?;
    let status = resp.status();
    if !status.is_success() {
        let text = resp.text().await.unwrap_or_default();
        let detail = serde_json::from_str::<Value>(&text)
            .ok()
            .and_then(|v| v.pointer("/error/message").and_then(Value::as_str).map(String::from))
            .unwrap_or(text);
        let hint = match status.as_u16() {
            401 | 403 => "API key 无效或无权限",
            404 => "base URL 或模型名可能有误（404）",
            429 => "请求过频或额度不足（429）",
            _ => "模型服务返回错误",
        };
        anyhow::bail!("{hint}（HTTP {status}）：{detail}");
    }

    let mut reply = AssistantReply::default();
    let mut partial: Vec<(Option<String>, Option<String>, String)> = Vec::new(); // 按 index 汇聚工具调用分片
    let mut sse_line_buf = String::new();

    let mut resp = resp;
    loop {
        let chunk = match tokio::time::timeout(IDLE_TIMEOUT, resp.chunk()).await {
            Ok(Ok(Some(bytes))) => bytes,
            Ok(Ok(None)) => break, // 流结束
            Ok(Err(e)) => anyhow::bail!("流式读取失败：{e}"),
            Err(_) => anyhow::bail!("模型服务响应超时（{} 秒无数据）", IDLE_TIMEOUT.as_secs()),
        };
        sse_line_buf.push_str(&String::from_utf8_lossy(&chunk));
        // SSE 以行为单位：只处理完整行，残行留缓冲
        while let Some(pos) = sse_line_buf.find('\n') {
            let line = sse_line_buf[..pos].trim_end_matches('\r').to_string();
            sse_line_buf.drain(..=pos);
            handle_sse_line(&line, &mut reply, &mut partial, &mut on_delta)?;
        }
    }
    if !sse_line_buf.trim().is_empty() {
        handle_sse_line(sse_line_buf.trim(), &mut reply, &mut partial, &mut on_delta)?;
    }

    reply.tool_calls = partial
        .into_iter()
        .filter_map(|(id, name, arguments)| {
            Some(ToolCall {
                id: id?,
                name: name?,
                arguments,
            })
        })
        .collect();
    Ok(reply)
}

/// 处理一行 SSE。非 data 行（注释/事件名）忽略；[DONE] 结束。
fn handle_sse_line(
    line: &str,
    reply: &mut AssistantReply,
    partial: &mut Vec<(Option<String>, Option<String>, String)>,
    on_delta: &mut impl FnMut(StreamDelta<'_>),
) -> anyhow::Result<()> {
    let Some(data) = line.strip_prefix("data:") else { return Ok(()) };
    let data = data.trim();
    if data.is_empty() || data == "[DONE]" {
        return Ok(());
    }
    let v: Value = match serde_json::from_str(data) {
        Ok(v) => v,
        Err(_) => return Ok(()), // 无法解析的分片跳过（不致命）
    };
    // token 用量（include_usage：末块 choices 为空、usage 单独到达）
    if let Some(usage) = v.get("usage") {
        if !usage.is_null() {
            reply.usage = Some(usage.clone());
        }
    }
    let Some(choice) = v.get("choices").and_then(Value::as_array).and_then(|c| c.first()) else {
        return Ok(());
    };
    let Some(delta) = choice.get("delta") else { return Ok(()) };
    // 思考增量按方言解析（ADR 0026 决策 3）：DeepSeek/通义回
    // reasoning_content；MiniMax 回 reasoning_details（字符串或 {text} 数组）。
    if let Some(t) = delta.get("reasoning_content").and_then(Value::as_str) {
        if !t.is_empty() {
            on_delta(StreamDelta::Thinking(t));
        }
    }
    match delta.get("reasoning_details") {
        Some(Value::String(s)) if !s.is_empty() => on_delta(StreamDelta::Thinking(s)),
        Some(Value::Array(items)) => {
            for it in items {
                if let Some(t) = it.get("text").and_then(Value::as_str) {
                    if !t.is_empty() {
                        on_delta(StreamDelta::Thinking(t));
                    }
                }
            }
        }
        _ => {}
    }
    if let Some(text) = delta.get("content").and_then(Value::as_str) {
        if !text.is_empty() {
            reply.text.push_str(text);
            on_delta(StreamDelta::Content(text));
        }
    }
    if let Some(calls) = delta.get("tool_calls").and_then(Value::as_array) {
        for call in calls {
            let index = call.get("index").and_then(Value::as_u64).unwrap_or(0) as usize;
            while partial.len() <= index {
                partial.push((None, None, String::new()));
            }
            let slot = &mut partial[index];
            if let Some(id) = call.get("id").and_then(Value::as_str) {
                slot.0 = Some(id.to_string());
            }
            if let Some(func) = call.get("function") {
                if let Some(name) = func.get("name").and_then(Value::as_str) {
                    slot.1 = Some(name.to_string());
                }
                if let Some(args) = func.get("arguments").and_then(Value::as_str) {
                    slot.2.push_str(args);
                }
            }
        }
    }
    Ok(())
}

/// 探活：GET {base_url}/models（OpenAI 兼容端点均支持）。返回模型数。
pub async fn test_connection(cfg: &LlmConfig) -> anyhow::Result<usize> {
    let url = format!("{}/models", cfg.base_url.trim_end_matches('/'));
    let client = reqwest::Client::builder()
        .connect_timeout(CONNECT_TIMEOUT)
        .build()?;
    let resp = client
        .get(&url)
        .bearer_auth(&cfg.api_key)
        .send()
        .await
        .map_err(|e| anyhow::anyhow!("连接模型服务失败：{e}"))?;
    let status = resp.status();
    if !status.is_success() {
        let text = resp.text().await.unwrap_or_default();
        let hint = match status.as_u16() {
            401 | 403 => "API key 无效或无权限",
            404 => "base URL 有误（404）",
            _ => "模型服务返回错误",
        };
        anyhow::bail!("{hint}（HTTP {status}）：{}", text.chars().take(300).collect::<String>());
    }
    let v: Value = resp.json().await.unwrap_or(Value::Null);
    Ok(v.get("data").and_then(Value::as_array).map(Vec::len).unwrap_or(0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mcp_tool_converts_to_openai_function() {
        let mcp_tool = json!({
            "name": "catalog_query",
            "description": "查询轨道库",
            "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
        });
        let f = mcp_tool_to_openai(&mcp_tool).unwrap();
        assert_eq!(f["type"], "function");
        assert_eq!(f["function"]["name"], "catalog_query");
        assert_eq!(f["function"]["parameters"]["properties"]["record_id"]["type"], "string");
    }

    #[test]
    fn provider_detection_follows_base_url() {
        assert_eq!(
            detect_provider("https://api.deepseek.com"),
            Provider::DeepSeek
        );
        assert_eq!(
            detect_provider("https://api.deepseek.com/v1"),
            Provider::DeepSeek
        );
        assert_eq!(
            detect_provider("https://dashscope.aliyuncs.com/compatible-mode/v1"),
            Provider::DashScope
        );
        assert_eq!(
            detect_provider("https://api.moonshot.cn/v1"),
            Provider::Kimi
        );
        assert_eq!(
            detect_provider("http://localhost:11434/v1"),
            Provider::Generic
        );
        assert_eq!(
            detect_provider("https://api.openai.com/v1"),
            Provider::Generic
        );
    }

    #[test]
    fn thinking_params_follow_adr_mapping_table() {
        // 数值为 ADR 0026 决策 2 的映射表，逐格对照
        let cases = [
            (
                Provider::DeepSeek,
                ThinkingLevel::Off,
                json!({"thinking": {"type": "disabled"}}),
            ),
            (
                Provider::DeepSeek,
                ThinkingLevel::Standard,
                json!({"thinking": {"type": "enabled"}}),
            ),
            (
                Provider::DeepSeek,
                ThinkingLevel::Deep,
                json!({"thinking": {"type": "enabled"}, "reasoning_effort": "high"}),
            ),
            (
                Provider::DashScope,
                ThinkingLevel::Off,
                json!({"enable_thinking": false}),
            ),
            (
                Provider::DashScope,
                ThinkingLevel::Standard,
                json!({"enable_thinking": true}),
            ),
            (
                Provider::DashScope,
                ThinkingLevel::Deep,
                json!({"enable_thinking": true, "thinking_budget": 16384}),
            ),
            (
                Provider::Kimi,
                ThinkingLevel::Off,
                json!({"thinking": {"type": "disabled"}}),
            ),
            (
                Provider::Kimi,
                ThinkingLevel::Standard,
                json!({"thinking": {"type": "enabled"}}),
            ),
            (
                Provider::Kimi,
                ThinkingLevel::Deep,
                json!({"thinking": {"type": "enabled"}}),
            ),
            (
                Provider::Generic,
                ThinkingLevel::Off,
                json!({"reasoning_effort": "none"}),
            ),
            (
                Provider::Generic,
                ThinkingLevel::Standard,
                json!({"reasoning_effort": "low"}),
            ),
            (
                Provider::Generic,
                ThinkingLevel::Deep,
                json!({"reasoning_effort": "high"}),
            ),
        ];
        for (p, level, want) in cases {
            assert_eq!(thinking_params(p, level), want, "{p:?} × {level:?}");
        }
    }

    #[test]
    fn thinking_level_parses_strict_and_loose() {
        assert_eq!(ThinkingLevel::try_parse("off"), Some(ThinkingLevel::Off));
        assert_eq!(ThinkingLevel::try_parse("deep"), Some(ThinkingLevel::Deep));
        assert_eq!(ThinkingLevel::try_parse("bogus"), None);
        assert_eq!(
            ThinkingLevel::parse(""),
            ThinkingLevel::Standard,
            "空值归标准档"
        );
        assert_eq!(ThinkingLevel::parse("bogus"), ThinkingLevel::Standard);
    }

    #[test]
    fn sse_line_accumulates_text_and_tool_call_fragments() {
        let mut reply = AssistantReply::default();
        let mut partial = Vec::new();
        let mut deltas = String::new();
        let mut on_delta = |d: StreamDelta<'_>| match d {
            StreamDelta::Content(s) => deltas.push_str(s),
            StreamDelta::Thinking(_) => {}
        };

        handle_sse_line(
            r#"data: {"choices":[{"delta":{"content":"正在"}}]}"#,
            &mut reply,
            &mut partial,
            &mut on_delta,
        )
        .unwrap();
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"catalog_query","arguments":"{\"rec"}}]}}]}"#,
            &mut reply, &mut partial, &mut on_delta,
        ).unwrap();
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ord_id\":\"r1\"}"}}]}}]}"#,
            &mut reply, &mut partial, &mut on_delta,
        ).unwrap();
        handle_sse_line(
            r#"data: {"choices":[],"usage":{"total_tokens":42}}"#,
            &mut reply,
            &mut partial,
            &mut on_delta,
        )
        .unwrap();
        handle_sse_line("data: [DONE]", &mut reply, &mut partial, &mut on_delta).unwrap();

        assert_eq!(reply.text, "正在");
        assert_eq!(deltas, "正在");
        assert_eq!(partial.len(), 1);
        assert_eq!(partial[0].0.as_deref(), Some("call_1"));
        assert_eq!(partial[0].1.as_deref(), Some("catalog_query"));
        assert_eq!(partial[0].2, r#"{"record_id":"r1"}"#);
        assert_eq!(reply.usage.as_ref().unwrap()["total_tokens"], 42);
    }

    #[test]
    fn sse_line_parses_thinking_deltas_by_dialect() {
        let mut reply = AssistantReply::default();
        let mut partial = Vec::new();
        let mut thinking = String::new();
        let mut content = String::new();
        let mut on_delta = |d: StreamDelta<'_>| match d {
            StreamDelta::Content(s) => content.push_str(s),
            StreamDelta::Thinking(s) => thinking.push_str(s),
        };

        // DeepSeek/通义方言：reasoning_content
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"reasoning_content":"先分析轨道族"}}]}"#,
            &mut reply,
            &mut partial,
            &mut on_delta,
        )
        .unwrap();
        // MiniMax 方言：reasoning_details 字符串
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"reasoning_details":"再算雅可比"}}]}"#,
            &mut reply,
            &mut partial,
            &mut on_delta,
        )
        .unwrap();
        // MiniMax 方言：reasoning_details {text} 数组
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"reasoning_details":[{"text":"，"},{"text":"再验证"}]}}]}"#,
            &mut reply, &mut partial, &mut on_delta,
        ).unwrap();
        // 正文不受影响
        handle_sse_line(
            r#"data: {"choices":[{"delta":{"content":"结论如下"}}]}"#,
            &mut reply,
            &mut partial,
            &mut on_delta,
        )
        .unwrap();

        assert_eq!(thinking, "先分析轨道族再算雅可比，再验证");
        assert_eq!(content, "结论如下");
    }

    #[test]
    fn non_data_lines_are_ignored() {
        let mut reply = AssistantReply::default();
        let mut partial = Vec::new();
        let mut noop = |_: StreamDelta<'_>| {};
        handle_sse_line(": comment", &mut reply, &mut partial, &mut noop).unwrap();
        handle_sse_line("event: message", &mut reply, &mut partial, &mut noop).unwrap();
        assert!(reply.text.is_empty());
    }
}
