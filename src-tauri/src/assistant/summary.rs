//! 工具结果入 LLM 上下文前的摘要/投影层（本仓 ADR 0023 决策 5）。
//!
//! MCP 是纯文本通道：轨迹数组等大体量数据若原样进上下文，一次工具调用
//! 就能烧掉整个窗口。规则：
//! - 已知大字段（states/times/frames/arrays/position_km/trajectory 等）整体
//!   替换为占位说明——轨迹已入轨道库，详情用 catalog_get 按需取；
//! - 任意数组超长截断、字符串超长截断、嵌套超深截断；
//! - 轨道状态/数值一律保留原始数值与量纲字段（态势文本化契约：量纲、
//!   历元、来源记录 id 不丢）。

use serde_json::{json, Value};

/// 整体省略的已知大字段名（轨迹/帧数据：详情走 catalog_get 按需取）。
const OMITTED_KEYS: &[&str] = &[
    "states",
    "times",
    "frames",
    "arrays",
    "position_km",
    "trajectory",
    "trajectory_times",
    "trajectories",
    "members",
    "orbits",
    "epochs",
    "binary_frames",
];

const MAX_ARRAY_LEN: usize = 20;
const MAX_STRING_LEN: usize = 2000;
const MAX_DEPTH: usize = 8;

/// 把 MCP tools/call 返回的信封文本投影为进 LLM 上下文的紧凑 Value。
/// 文本非 JSON 时原样截断返回（错误信息也可能不是 JSON）。
pub fn project_for_llm(envelope_text: &str) -> Value {
    match serde_json::from_str::<Value>(envelope_text) {
        Ok(v) => project(&v, 0),
        Err(_) => Value::String(truncate_string(envelope_text)),
    }
}

/// 供前端工具卡片展示的短摘要（状态 + 关键标量，供"已入轨道库"链接；
/// 宿主情景工具的 scenario_file 同样透传供应用情景按钮；族生成
/// （e2m2e 5.9.3 一轨一记录）的 family_id 单独透传——它是生成批次而非
/// 单条记录 id，不触发入树登记。
pub fn card_summary(envelope_text: &str) -> Value {
    let Ok(v) = serde_json::from_str::<Value>(envelope_text) else {
        return json!({"status": "unknown"});
    };
    let status = v.get("status").cloned().unwrap_or(json!("unknown"));
    let data = v.get("data").cloned().unwrap_or(Value::Null);
    let record_id = data.get("record_id").cloned();
    let family_id = data.get("family_id").cloned();
    let scenario_file = data.get("scenario_file").cloned();
    let error = v.get("error").cloned();
    let mut out = json!({ "status": status });
    if let Some(r) = record_id {
        out["recordId"] = r;
    }
    if let Some(f) = family_id {
        out["familyId"] = f;
    }
    if let Some(s) = scenario_file {
        out["scenarioFile"] = s;
    }
    if let Some(e) = error {
        out["error"] = e;
    }
    out
}

fn project(v: &Value, depth: usize) -> Value {
    if depth >= MAX_DEPTH {
        return json!("…（嵌套过深已省略）");
    }
    match v {
        Value::Object(map) => {
            let mut out = serde_json::Map::new();
            for (k, val) in map {
                if OMITTED_KEYS.contains(&k.as_str()) {
                    let len = val.as_array().map(|a| a.len());
                    out.insert(
                        k.clone(),
                        json!({"_omitted": true, "length": len, "note": "轨迹/大数组数据已入轨道库，不进上下文；需要时用 catalog_get 按 record_id 查看"}),
                    );
                } else {
                    out.insert(k.clone(), project(val, depth + 1));
                }
            }
            Value::Object(out)
        }
        Value::Array(arr) => {
            let mut out: Vec<Value> = arr.iter().take(MAX_ARRAY_LEN).map(|x| project(x, depth + 1)).collect();
            if arr.len() > MAX_ARRAY_LEN {
                out.push(json!(format!("…（共 {} 项，其余省略）", arr.len())));
            }
            Value::Array(out)
        }
        Value::String(s) => Value::String(truncate_string(s)),
        other => other.clone(),
    }
}

fn truncate_string(s: &str) -> String {
    if s.chars().count() <= MAX_STRING_LEN {
        return s.to_string();
    }
    let head: String = s.chars().take(MAX_STRING_LEN).collect();
    format!("{head}…（已截断）")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn big_trajectory_fields_are_omitted_with_note() {
        let envelope = json!({
            "status": "ok",
            "data": {
                "record_id": "rec-001",
                "states": vec![vec![1.0, 2.0, 3.0]; 500],
                "period": 2.5
            }
        });
        let projected = project_for_llm(&envelope.to_string());
        assert_eq!(projected["data"]["record_id"], "rec-001");
        assert_eq!(projected["data"]["period"], 2.5);
        assert_eq!(projected["data"]["states"]["_omitted"], true);
        assert_eq!(projected["data"]["states"]["length"], 500);
    }

    #[test]
    fn long_arrays_and_strings_are_truncated() {
        let v = json!({"items": (0..100).collect::<Vec<i32>>(), "text": "x".repeat(5000)});
        let p = project(&v, 0);
        let items = p["items"].as_array().unwrap();
        assert_eq!(items.len(), MAX_ARRAY_LEN + 1);
        assert!(p["text"].as_str().unwrap().ends_with("（已截断）"));
    }

    #[test]
    fn non_json_text_passes_through_truncated() {
        let p = project_for_llm("plain error text");
        assert_eq!(p, Value::String("plain error text".into()));
    }

    #[test]
    fn card_summary_extracts_record_id() {
        let envelope = json!({"status": "ok", "data": {"record_id": "r-9", "states": [1, 2, 3]}});
        let s = card_summary(&envelope.to_string());
        assert_eq!(s["status"], "ok");
        assert_eq!(s["recordId"], "r-9");
        assert!(s.get("data").is_none(), "卡片摘要不带大字段");
    }

    #[test]
    fn card_summary_extracts_family_id_for_family_runs() {
        // 族生成（e2m2e 5.9.3 一轨一记录）回执是 family_id（生成批次），
        // 不是单条记录 id——单独透传，不冒充 recordId
        let envelope = json!({"status": "ok", "data": {"family_id": "fam-a1"}});
        let s = card_summary(&envelope.to_string());
        assert_eq!(s["familyId"], "fam-a1");
        assert!(s.get("recordId").is_none());
    }

    #[test]
    fn transfer_contract_keeps_state_frame_but_omits_trajectory_arrays() {
        // e2m2e 5.8.9+/5.9.0 转移契约（ADR 0040）：trajectory/trajectory_times
        // 是大数组，省略；state_frame 是小标注，透传供模型解读数据系。
        let envelope = json!({
            "status": "ok",
            "data": {
                "record_id": "t-1",
                "transfer_type": "hmn",
                "state_frame": "synodic_barycentric_km",
                "trajectory": vec![vec![1.0; 6]; 200],
                "trajectory_times": vec![0.0f64; 200],
            }
        });
        let p = project_for_llm(&envelope.to_string());
        assert_eq!(p["data"]["trajectory"]["_omitted"], true);
        assert_eq!(p["data"]["trajectory_times"]["_omitted"], true);
        assert_eq!(p["data"]["state_frame"], "synodic_barycentric_km");
        assert_eq!(p["data"]["transfer_type"], "hmn");
    }
}
