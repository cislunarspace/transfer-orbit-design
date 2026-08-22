//! SidecarHandle 对真实 e2m2e serve-stdio 子进程的集成测试。
//!
//! 依赖：本仓库 uv 环境（`uv run e2m2e serve-stdio` 可用）。CI 无 Python
//! 环境时用 `--skip sidecar` 跳过（见文件尾 filter）。

use serde_json::json;
use tokio::sync::mpsc;

use tod_tauri::sidecar::{FrameArray, SidecarHandle};

async fn spawn() -> SidecarHandle {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    SidecarHandle::spawn(&["uv", "run", "e2m2e", "serve-stdio"], Some(repo_root))
        .expect("拉起 sidecar 失败（uv 环境可用？）")
}

#[tokio::test]
async fn family_generation_over_real_process() {
    let handle = spawn().await;
    let (progress_tx, mut progress_rx) = mpsc::unbounded_channel();
    handle.subscribe_progress(progress_tx);

    let result = handle
        .request(
            "orbit_family_generation",
            &json!({"orbit_type": "HALO", "libration_point": 1, "max_amplitude_km": 5000, "n_orbits": 3}),
            Some("f32"),
        )
        .await
        .expect("请求失败");

    assert_eq!(result.status, "ok", "错误：{:#?}", result.error);
    assert_eq!(result.frames.len(), 3);
    for f in &result.frames {
        assert_eq!(f.shape(), &[1, 6]);
        assert!(matches!(f, FrameArray::F32 { .. }));
    }
    assert_eq!(result.data["generated_members"], 3);
    assert!(result.data["record_id"].as_str().is_some());

    // progress 事件应已到达（任务开始行）
    let ev = progress_rx.try_recv().expect("应有 progress 事件");
    assert_eq!(ev["status"], "progress");

    handle.shutdown().await.unwrap();
}

#[tokio::test]
async fn unknown_tool_returns_error_envelope() {
    let handle = spawn().await;
    let result = handle.request("nope", &json!({}), None).await.unwrap();
    assert_eq!(result.status, "error");
    assert_eq!(result.error.as_ref().unwrap()["code"], "UNKNOWN_TOOL");
    handle.shutdown().await.unwrap();
}

#[tokio::test]
async fn sequential_requests_reuse_process() {
    let handle = spawn().await;
    for i in 0..2 {
        let result = handle
            .request(
                "orbit_family_generation",
                &json!({"orbit_type": "HALO", "libration_point": 1, "max_amplitude_km": 5000.0 + i as f64, "n_orbits": 2}),
                Some("f32"),
            )
            .await
            .unwrap();
        assert_eq!(result.status, "ok", "第 {i} 个请求失败");
        assert_eq!(result.frames.len(), 2);
    }
    handle.shutdown().await.unwrap();
}
