//! Tauri commands - 前端经 IPC 调用的函数。

use serde::Serialize;
use tauri::{Manager, State};

/// 星历内核状态：目录/文件清单/可用性（前端设置面板展示）。
/// 文件名单与 e2m2e kernel_dir_usable 保持一致（任一 .bsp + 任一 .tls）。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EphemerisStatus {
    pub kernel_dir: Option<String>,
    pub files: Vec<String>,
    pub ephemeris_ready: bool,
    pub leapsecond_ready: bool,
    pub usable: bool,
}

const EPHEMERIS_KERNELS: [&str; 5] = ["de440.bsp", "de440s.bsp", "de435.bsp", "de438.bsp", "de430.bsp"];
const LEAPSECOND_KERNELS: [&str; 2] = ["naif0011.tls", "naif0012.tls"];

fn build_ephemeris_status(dir: Option<std::path::PathBuf>) -> EphemerisStatus {
    let Some(dir) = dir else {
        return EphemerisStatus { kernel_dir: None, files: vec![], ephemeris_ready: false, leapsecond_ready: false, usable: false };
    };
    let files: Vec<String> = std::fs::read_dir(&dir)
        .map(|rd| {
            rd.filter_map(|e| e.ok())
                .filter_map(|e| e.file_name().into_string().ok())
                .filter(|n| !n.starts_with('.'))
                .collect()
        })
        .unwrap_or_default();
    let ephemeris_ready = EPHEMERIS_KERNELS.iter().any(|k| files.iter().any(|f| f == k));
    let leapsecond_ready = LEAPSECOND_KERNELS.iter().any(|k| files.iter().any(|f| f == k));
    EphemerisStatus {
        kernel_dir: Some(dir.to_string_lossy().into_owned()),
        usable: ephemeris_ready && leapsecond_ready,
        files,
        ephemeris_ready,
        leapsecond_ready,
    }
}

/// 星历配置状态（自动配置：数据随 git/安装包分发，正常情况永远就绪）。
#[tauri::command]
pub async fn ephemeris_status(app: tauri::AppHandle) -> Result<EphemerisStatus, String> {
    let resource_dir = app.path().resource_dir().ok();
    let dir = if cfg!(debug_assertions) {
        crate::resolve_kernel_dir(None)
    } else {
        crate::resolve_kernel_dir(resource_dir.as_deref())
    };
    Ok(build_ephemeris_status(dir))
}

use crate::project::{ArtifactSummary, ProjectState};
use crate::state::{request_with_retry, SidecarState};

/// 进度事件名（前端 listen 用）。
pub const PROGRESS_EVENT: &str = "sidecar-progress";

/// 族生成响应（camelCase 给前端）。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FamilyMember {
    /// 成员状态（一维 n×6：xyz vx vy vz），前端传播整条轨迹需要完整状态。
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

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FrameResponse {
    pub dtype: &'static str,
    pub shape: Vec<u32>,
    pub data: serde_json::Value,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolResponse {
    pub data: serde_json::Value,
    pub frames: Vec<FrameResponse>,
    pub error: Option<serde_json::Value>,
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactMetadata {
    pub artifact_type: String,
    pub label: String,
    #[serde(default)]
    pub orbit_type: String,
}

/// 通用工具执行通道。sidecar 负责工具分派；Rust 只做协议校验和会话产物登记。
#[tauri::command]
pub async fn run_tool(
    state: State<'_, SidecarState>,
    project: State<'_, ProjectState>,
    tool: String,
    arguments: serde_json::Value,
    binary_dtype: Option<String>,
    artifact: Option<ArtifactMetadata>,
) -> Result<ToolResponse, String> {
    let dtype = binary_dtype.as_deref().map(|v| match v {
        "f32" => Ok("f32"),
        "f64" => Ok("f64"),
        _ => Err(anyhow::anyhow!("binary_dtype 必须是 f32 或 f64")),
    }).transpose().map_err(|e: anyhow::Error| e.to_string())?;
    let result = request_with_retry(&state, &tool, arguments, dtype)
        .await.map_err(|e| e.to_string())?;
    if result.status != "ok" {
        return Ok(ToolResponse { data: result.data, frames: vec![], error: result.error });
    }
    let frames: Vec<FrameResponse> = result.frames.iter().map(|frame| match frame {
        crate::sidecar::FrameArray::F32 { shape, data } => FrameResponse {
            dtype: "f32", shape: shape.clone(), data: serde_json::json!(data),
        },
        crate::sidecar::FrameArray::F64 { shape, data } => FrameResponse {
            dtype: "f64", shape: shape.clone(), data: serde_json::json!(data),
        },
    }).collect();
    if let Some(expected) = dtype {
        let mismatch = frames.iter().any(|f| f.dtype != expected);
        if mismatch {
            return Ok(ToolResponse {
                data: serde_json::Value::Null,
                frames: vec![],
                error: Some(serde_json::json!({
                    "code": "PROTOCOL_VIOLATION",
                    "message": format!("binary_dtype={expected} 请求收到不同 dtype 帧"),
                })),
            });
        }
    }
    if let (Some(meta), Some(record_id)) = (artifact, result.data.get("record_id").and_then(|v| v.as_str())) {
        if !record_id.is_empty() {
            project.add(ArtifactSummary {
                artifact_id: String::new(), artifact_type: meta.artifact_type,
                label: meta.label, orbit_type: meta.orbit_type, source_tool: tool,
                record_id: Some(record_id.to_string()), created_at: unix_seconds_now(),
            }).await;
        }
    }
    Ok(ToolResponse { data: result.data, frames, error: None })
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
    // 帧序 = data.orbits 成员序；每帧 (1, 6) 初态 + period/mu 标量
    // （要求 e2m2e ≥5.8.5）。轨迹重采样在前端 CR3BP 传播器做。
    let orbits = result.data["orbits"].as_array().cloned().unwrap_or_default();
    let mu = result.data["mu"].as_f64();
    // binary_dtype=f32 是本命令固定的，f64 帧是协议违约：结构化拒绝
    if result.frames.iter().any(|f| matches!(f, crate::sidecar::FrameArray::F64 { .. })) {
        return Ok(FamilyResponse {
            record_id: String::new(),
            family_type: String::new(),
            generated_members: 0,
            mu: None,
            members: vec![],
            error: Some(serde_json::json!({
                "code": "PROTOCOL_VIOLATION",
                "message": "binary_dtype=f32 请求收到 f64 帧",
            })),
        });
    }
    let members = result
        .frames
        .iter()
        .zip(orbits.iter())
        .map(|(frame, orbit)| {
            let initial = match frame {
                crate::sidecar::FrameArray::F32 { data, .. } => data,
                crate::sidecar::FrameArray::F64 { .. } => unreachable!("已在上方排除"),
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
            created_at: unix_seconds_now(),
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

/// build_ephemeris_status：任一 .bsp + 任一 .tls 即可用；缺/空目录不可用。
#[cfg(test)]
mod ephemeris_tests {
    use super::*;

    #[test]
    fn status_detects_complete_kernel_dir() {
        let dir = std::env::temp_dir().join("tod-eph-test-complete");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("de440s.bsp"), b"x").unwrap();
        std::fs::write(dir.join("naif0012.tls"), b"x").unwrap();
        let s = build_ephemeris_status(Some(dir.clone()));
        assert!(s.ephemeris_ready && s.leapsecond_ready && s.usable);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn status_missing_bsp_is_not_usable() {
        let dir = std::env::temp_dir().join("tod-eph-test-missing");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("naif0012.tls"), b"x").unwrap();
        let s = build_ephemeris_status(Some(dir.clone()));
        assert!(s.leapsecond_ready && !s.ephemeris_ready && !s.usable);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn status_none_dir_is_not_usable() {
        let s = build_ephemeris_status(None);
        assert!(!s.usable && s.kernel_dir.is_none() && s.files.is_empty());
    }
}

fn unix_seconds_now() -> String {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs().to_string())
        .unwrap_or_default()
}

/// 记录的星历段（eph/ 前缀数组）：会合系无量纲位置 (n,3) 平铺 + UTC 时间
/// 分量（各 (n,)）。键名与 e2m2e EphemerisTable 字段一致（不加 camelCase
/// 改名，与设计响应的 ephemeris dict 同形，前端共用同一解析函数）。
#[derive(Serialize)]
pub struct EphemerisSegment {
    pub synodic_position: Vec<f32>,
    pub year: Vec<f32>,
    pub month: Vec<f32>,
    pub day: Vec<f32>,
    pub hour: Vec<f32>,
    pub minute: Vec<f32>,
    pub second: Vec<f32>,
}

/// 项目树选中 → 画布联动：按 record_id 从 catalog 拉取产物。
///
/// 帧序 = `data.arrays` 里 None 占位键的顺序（e2m2e ADR 0035）；族记录
/// 是 `cr3bp/members/NNNN/states|times` 交替，states 帧为 (n, 6) 或 (1, 6)。
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactData {
    pub record_id: String,
    pub orbit_family: String,
    pub member_count: u64,
    pub mu: Option<f64>,
    /// 每成员完整的状态与元数据（包含 (1, 6) 或 (n, 6) 的 states, period 等）
    pub family_members: Vec<FamilyMember>,
    /// 兼容旧版：每成员提取的 xyz
    pub members: Vec<Vec<f32>>,
    /// 星历段（设计/预报类产物；会合系原生直画，UTC 分量 → et）
    pub ephemeris: Option<EphemerisSegment>,
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
            mu: None,
            family_members: vec![],
            members: vec![],
            ephemeris: None,
            error: result.error,
        });
    }
    // 帧序 = arrays 中 None 占位键顺序；states 键配对同序 times 键，
    let arrays = result.data["arrays"].as_object().cloned().unwrap_or_default();
    let state_keys: Vec<&String> = arrays
        .iter()
        .filter(|(k, v)| v.is_null() && k.ends_with("/states"))
        .map(|(k, _)| k)
        .collect();
    let member_meta_list = result.data["members"].as_array().cloned().unwrap_or_default();
    let mu = result.data["scalars"]["mu"].as_f64();

    let mut members = Vec::with_capacity(state_keys.len());
    let mut family_members = Vec::with_capacity(state_keys.len());

    // 帧游标：frames 全序列表里找对应的 states 帧。占位键顺序即帧序，
    // 用索引直接算：states 键在全部 None 键里的位置 = 对应帧下标。
    let none_keys: Vec<&String> = arrays.iter().filter(|(_, v)| v.is_null()).map(|(k, _)| k).collect();
    for (i, key) in state_keys.iter().enumerate() {
        let idx = none_keys.iter().position(|k| **k == **key).expect("占位键必在序列");
        let frame = &result.frames[idx];
        if let crate::sidecar::FrameArray::F32 { data, .. } = frame {
            members.push(data.chunks_exact(6).flat_map(|s| [s[0], s[1], s[2]]).collect());
            let period = member_meta_list.get(i).and_then(|m| m["period"].as_f64());
            family_members.push(FamilyMember {
                states: data.clone(),
                times: vec![],
                period,
            });
        }
    }
    // 星历段：eph/ 前缀键（会合系位置 + UTC 分量，dtype 契约同为 f32）。
    // 七键齐全且长度对齐才携带——半截数据宁可不上（前端按无星历段处理）。
    let eph_frame = |key: &str| -> Option<Vec<f32>> {
        let idx = none_keys.iter().position(|k| k.as_str() == key)?;
        match result.frames.get(idx) {
            Some(crate::sidecar::FrameArray::F32 { data, .. }) => Some(data.clone()),
            _ => None,
        }
    };
    let ephemeris = (|| {
        let year = eph_frame("eph/year")?;
        let month = eph_frame("eph/month")?;
        let day = eph_frame("eph/day")?;
        let hour = eph_frame("eph/hour")?;
        let minute = eph_frame("eph/minute")?;
        let second = eph_frame("eph/second")?;
        let synodic_position = eph_frame("eph/synodic_position")?;
        let n = year.len();
        if n == 0
            || synodic_position.len() != 3 * n
            || month.len() != n
            || day.len() != n
            || hour.len() != n
            || minute.len() != n
            || second.len() != n
        {
            return None;
        }
        Some(EphemerisSegment {
            synodic_position,
            year,
            month,
            day,
            hour,
            minute,
            second,
        })
    })();
    Ok(ArtifactData {
        record_id: result.data["record_id"].as_str().unwrap_or("").to_string(),
        orbit_family: result.data["orbit_family"].as_str().unwrap_or("").to_string(),
        member_count: result.data["member_count"].as_u64().unwrap_or(0),
        mu,
        family_members,
        members,
        ephemeris,
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

/// 登记 AI 助手经 MCP 运行产出的产物（ADR 0022：AI 产物与手动运行语义
/// 一致，同一项目树）。run_tool/generate_family 之外的登记入口——MCP
/// 链路不过 run_tool，产物 record_id 由前端从工具卡片事件带回。
#[tauri::command]
pub async fn register_artifact(
    state: State<'_, ProjectState>,
    artifact_type: String,
    label: String,
    orbit_type: Option<String>,
    source_tool: String,
    record_id: String,
) -> Result<ArtifactSummary, String> {
    if record_id.is_empty() {
        return Err("record_id 不能为空".into());
    }
    Ok(state.add(ArtifactSummary {
        artifact_id: String::new(),
        artifact_type,
        label,
        orbit_type: orbit_type.unwrap_or_default(),
        source_tool,
        record_id: Some(record_id),
        created_at: unix_seconds_now(),
    }).await)
}