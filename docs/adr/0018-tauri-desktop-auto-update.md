# Tauri 桌面端自动更新架构

为桌面端（Windows / Linux / macOS）提供无缝、可信且安全的版本更新能力。我们决定采用 `@tauri-apps/plugin-updater` 官方更新插件，基于 GitHub Releases 托管安装包与更新清单（`latest.json`），并在 CI/CD 发布工作流中生成 Ed25519 签名与清单。

## Considered Options

- **手写 Python/Sidecar 更新脚本或独立下载器**：跨平台差异大（Windows NSIS vs Linux AppImage/deb 替换机制完全不同），缺少统一的签名校验与进度回调，维护成本高。
- **纯网页重定向（仅弹窗跳转 GitHub 网页手动下载）**：打断用户工作流，体验割裂。
- **Tauri 官方插件 (`@tauri-apps/plugin-updater`)**：与 Tauri v2 深度结合，内置 Ed25519 签名验证、断点与下载进度事件、系统级原生安装器拉起，前端提供统一 JS API。

## Consequences

- 必须在构建流程中配置 updater 签名密钥对（公钥注入 `tauri.conf.json` / `tauri.release.conf.json`，私钥注入 CI Secrets）。
- CI 发布工作流需要在 Windows 与 Linux 各自构建后汇聚产物并生成合法的 `latest.json` 发布清单。
- 前端需提供非阻塞式的启动后台检查、更新就绪弹窗提示以及“关于/设置”的手动检查更新入口。
