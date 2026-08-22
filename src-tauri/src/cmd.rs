//! Tauri commands — 前端经 IPC 调用的函数。

use serde::Serialize;
use tauri::State;

use crate::project::{ArtifactSummary, ProjectState};
use crate::state::{request_with_retry, SidecarState};

/// 进度事件名（前端 listen 用）。
pub const PROGRESS_EVENT: &str = "sidecar-progress";

/// 族生成响应（camelCase 给前端）。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FamilyMember {
    /// 成员状态（一维 n×6：xyz vx vy vz）——前端传播整条轨迹需要完整状态。
    pub states: Vec<f32>,
    pub times: Vec<f64>,
    pub period: Option<f64>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FamilyResponse {
    pub record_id: String,
    pub family_type: String,
    pub generated_members: u64,
    pub mu: Option<f64>,
    pub members: Vec<FamilyMember>,
    /// 错误信封（e2m2e 结构化错误原样透传）。
    pub error: Option<serde_json::Value>,
}

/// 生成轨道族（首个打通的工具；参数结构与 FamilyGenerationRequest 对齐）。
#[tauri::command]
pub async fn generate_family(
    state: State<'_, SidecarState>,
    project: State<'_, ProjectState>,
    arguments: serde_json::Value,
) -> Result<FamilyResponse, String> {
    let result = request_with_retry(&state, "orbit_family_generation", arguments, Some("f32"))
        .await
        .map_err(|e| e.to_string())?;
    if result.status != "ok" {
        return Ok(FamilyResponse {
            record_id: String::new(),
            family_type: String::new(),
            generated_members: 0,
            mu: None,
            members: vec![],
            error: result.error,
        });
    }
    // 帧序 = data.orbits 成员序；每帧 (1, 6) 初态 + period/mu 标量（e2m2e
    // ≥5.8.5，#525）。轨迹重采样在前端 CR3BP 传播器做（与 CSV 原型同源）。
    let orbits = result.data["orbits"].as_array().cloned().unwrap_or_default();
    let mu = result.data["mu"].as_f64();
    let members = result
        .frames
        .iter()
        .zip(orbits.iter())
        .map(|(frame, orbit)| {
            let initial = match frame {
                crate::sidecar::FrameArray::F32 { data, .. } => data,
                // binary_dtype=f32 是本命令固定的，出现 f64 是协议违约
                crate::sidecar::FrameArray::F64 { .. } => unreachable!("f32 请求收到 f64 帧"),
            };
            let states = initial.to_vec();
            let times = orbit["times"].as_array().cloned().unwrap_or_default()
                .iter().filter_map(|t| t.as_f64()).collect();
            FamilyMember {
                states,
                times,
                period: orbit["period"].as_f64(),
            }
        })
        .collect();
    let record_id = result.data["record_id"].as_str().unwrap_or("").to_string();
    let family_type = result.data["family_type"].as_str().unwrap_or("").to_string();
    let generated = result.data["generated_members"].as_u64().unwrap_or(0);
    // 入项目（摘要想入容器；帧不入库，随本次响应交付前端）
    if !record_id.is_empty() {
        project.add(ArtifactSummary {
            artifact_id: String::new(),
            artifact_type: "family".into(),
            label: format!("{family_type} 族（{generated} 成员）"),
            orbit_type: family_type.clone(),
            source_tool: "orbit_family_generation".into(),
            record_id: Some(record_id.clone()),
            created_at: chrono_iso_now(),
        }).await;
    }
    Ok(FamilyResponse {
        record_id,
        family_type,
        generated_members: generated,
        mu,
        members,
        error: None,
    })
}

fn chrono_iso_now() -> String {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs().to_string())
        .unwrap_or_default()
}

/// 项目树选中 → 画布联动：按 record_id 从 catalog 拉取产物。
///
/// 帧序 = `data.arrays` 里 None 占位键的顺序（ADR 0035，#526）；族记录
/// 是 `cr3bp/members/NNNN/states|times` 交替，states 帧为 (n, 6) 或 (1, 6)。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactData {
    pub record_id: String,
    pub orbit_family: String,
    pub member_count: u64,
    /// 每成员 (n, 6) 状态（仅 xyz 压缩为 n×3）。
    pub members: Vec<Vec<f32>>,
    pub error: Option<serde_json::Value>,
}

#[tauri::command]
pub async fn get_artifact(
    state: State<'_, SidecarState>,
    record_id: String,
) -> Result<ArtifactData, String> {
    let result = request_with_retry(
        &state,
        "catalog_get",
        serde_json::json!({"record_id": record_id}),
        Some("f32"),
    )
    .await
    .map_err(|e| e.to_string())?;
    if result.status != "ok" {
        return Ok(ArtifactData {
            record_id,
            orbit_family: String::new(),
            member_count: 0,
            members: vec![],
            error: result.error,
        });
    }
    // 帧序 = arrays 中 None 占位键顺序；states 键配对同序 times 键，
    // states 帧出 xyz，times 帧只用于确认形状（时间值画布暂不用）。
    let arrays = result.data["arrays"].as_object().cloned().unwrap_or_default();
    let state_keys: Vec<&String> = arrays
        .iter()
        .filter(|(k, v)| v.is_null() && k.ends_with("/states"))
        .map(|(k, _)| k)
        .collect();
    let mut members = Vec::with_capacity(state_keys.len());
    // 帧游标：frames 全序列表里找对应的 states 帧。占位键顺序即帧序，
    // 用索引直接算：states 键在全部 None 键里的位置 = 对应帧下标。
    let none_keys: Vec<&String> = arrays.iter().filter(|(_, v)| v.is_null()).map(|(k, _)| k).collect();
    for key in &state_keys {
        let idx = none_keys.iter().position(|k| *k == *key).expect("占位键必在序列");
        let frame = &result.frames[idx];
        if let crate::sidecar::FrameArray::F32 { data, .. } = frame {
            members.push(data.chunks_exact(6).flat_map(|s| [s[0], s[1], s[2]]).collect());
        }
    }
    Ok(ArtifactData {
        record_id: result.data["record_id"].as_str().unwrap_or("").to_string(),
        orbit_family: result.data["orbit_family"].as_str().unwrap_or("").to_string(),
        member_count: result.data["member_count"].as_u64().unwrap_or(0),
        members,
        error: None,
    })
}

#[tauri::command]
pub async fn catalog_query(
    state: State<'_, SidecarState>,
    arguments: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let result = request_with_retry(&state, "catalog_query", arguments, None)
        .await
        .map_err(|e| e.to_string())?;
    if result.status != "ok" {
        return Ok(serde_json::json!({"records": [], "message": result.error
            .and_then(|e| e.get("message").cloned()).unwrap_or_default()}));
    }
    Ok(serde_json::json!({
        "records": result.data["records"].clone(),
        "message": result.data["message"].clone(),
    }))
}

/// 项目内 Artifact 摘要列表（项目树数据源）。
#[tauri::command]
pub async fn list_artifacts(
    state: State<'_, ProjectState>,
) -> Result<Vec<ArtifactSummary>, String> {
    Ok(state.list().await)
}

/// 从项目中移除一个 Artifact。
#[tauri::command]
pub async fn remove_artifact(
    state: State<'_, ProjectState>,
    artifact_id: String,
) -> Result<bool, String> {
    Ok(state.remove(&artifact_id).await)
}
