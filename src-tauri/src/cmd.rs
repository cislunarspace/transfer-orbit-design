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
    /// 重采样后的 (n, 6) 位置轨迹（一维数组，n×3，仅 xyz——画布只需位置）。
    pub positions: Vec<f32>,
    pub point_count: usize,
    pub times: Vec<f64>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FamilyResponse {
    pub record_id: String,
    pub family_type: String,
    pub generated_members: u64,
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
            members: vec![],
            error: result.error,
        });
    }
    // 帧序 = data.orbits 成员序；每帧 (1, 6) 初态（ADR 0035 首版画布契约）。
    // period/mu 未随响应下发（e2m2e #525），轨迹重采样暂不可用——先回传
    // 初态本身（单点），#525 落地后切整条轨迹。
    let orbits = result.data["orbits"].as_array().cloned().unwrap_or_default();
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
            let positions = initial.chunks_exact(6).flat_map(|s| [s[0], s[1], s[2]]).collect();
            let times = orbit["times"].as_array().cloned().unwrap_or_default()
                .iter().filter_map(|t| t.as_f64()).collect();
            FamilyMember { positions, point_count: initial.len() / 6, times }
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
