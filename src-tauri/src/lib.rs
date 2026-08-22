//! tod Tauri 应用：sidecar 状态 + 命令注册。

pub mod cmd;
pub mod project;
pub mod sidecar;
pub mod state;

use project::ProjectState;
use state::SidecarState;
use tauri::{Emitter, Manager};

pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            // 开发期：仓库根下 uv 拉起（分发期换成打包产物路径）
            let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
            SidecarState::configure(
                vec![
                    "uv".into(),
                    "run".into(),
                    "e2m2e".into(),
                    "serve-stdio".into(),
                ],
                Some(repo_root.to_string_lossy().into_owned()),
            );
            // 进度事件 → 前端窗口
            let handle = app.handle().clone();
            state::set_progress_emitter(std::sync::Arc::new(move |ev: &serde_json::Value| {
                let _ = handle.emit(cmd::PROGRESS_EVENT, ev);
            }));
            app.manage(SidecarState::new());
            app.manage(ProjectState::new());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            cmd::generate_family,
            cmd::list_artifacts,
            cmd::remove_artifact,
            cmd::get_artifact,
            cmd::catalog_query
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
