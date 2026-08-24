//! transfer-orbit-design Tauri 应用：sidecar 状态 + 命令注册。

pub mod cmd;
pub mod project;
pub mod sidecar;
pub mod state;

use project::ProjectState;
use state::SidecarState;
use tauri::{Emitter, Manager};

/// 分发期 sidecar 可执行文件名（resources/binaries/ 下，Windows 带后缀）。
#[cfg(windows)]
pub const SIDECAR_EXE: &str = "transfer-orbit-design-sidecar.exe";
#[cfg(not(windows))]
pub const SIDECAR_EXE: &str = "transfer-orbit-design-sidecar";

/// 开发期拉起配置：仓库根下 uv 拉起 e2m2e CLI（serve-stdio）。
pub fn dev_sidecar_command(repo_root: &std::path::Path) -> (Vec<String>, Option<String>) {
    (
        vec!["uv".into(), "run".into(), "e2m2e".into(), "serve-stdio".into()],
        Some(repo_root.to_string_lossy().into_owned()),
    )
}

/// 分发期拉起配置：resources/binaries 内的打包 sidecar，cwd 指 resource
/// 根，e2m2e Config 的 kernels/、catalog/ 按 cwd 相对解析（安装目录内
/// resources 已带 kernels/，catalog/ 运行时创建；两个路径均可被
/// SPICE_KERNEL_DIR / E2M2E_CATALOG_DIR 环境变量覆盖）。
pub fn packaged_sidecar_command(resource_dir: &std::path::Path) -> (Vec<String>, Option<String>) {
    let exe = resource_dir.join("binaries").join(SIDECAR_EXE);
    (
        vec![exe.to_string_lossy().into_owned()],
        Some(resource_dir.to_string_lossy().into_owned()),
    )
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            // 开发期（cargo tauri dev，debug 构建）：仓库根下 uv 拉起；
            // 分发期（release 构建）：resources/binaries 内的打包 sidecar。
            let (command, cwd) = if cfg!(debug_assertions) {
                let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
                dev_sidecar_command(repo_root)
            } else {
                let resource_dir = app.path().resource_dir()?;
                packaged_sidecar_command(&resource_dir)
            };
            SidecarState::configure(command, cwd);
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
            cmd::run_tool,
            cmd::generate_family,
            cmd::list_artifacts,
            cmd::remove_artifact,
            cmd::get_artifact,
            cmd::catalog_query
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packaged_command_points_at_resource_binaries_with_resource_cwd() {
        let root = std::path::Path::new("/opt/transfer-orbit-design");
        let (cmd, cwd) = packaged_sidecar_command(root);
        let expected = root.join("binaries").join(SIDECAR_EXE);
        assert_eq!(cmd, vec![expected.to_string_lossy().into_owned()]);
        assert_eq!(cwd.as_deref(), Some("/opt/transfer-orbit-design"));
    }

    #[test]
    fn dev_command_spawns_uv_with_repo_cwd() {
        let root = std::path::Path::new("/repo");
        let (cmd, cwd) = dev_sidecar_command(root);
        assert_eq!(cmd, vec!["uv", "run", "e2m2e", "serve-stdio"]);
        assert_eq!(cwd.as_deref(), Some("/repo"));
    }
}