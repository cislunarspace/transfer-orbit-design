# 0017. Linux 桌面版本分发（AppImage 与 DEB 双形态打包）

- 日期: 2026-08-24
- 状态: 提议 (Accepted)

## 上下文

自 v4.0.0 迁移至 Tauri 桌面应用后，CI 仅构建 Windows NSIS 安装器（.exe）。Linux 用户需要免安装的即开即用版本（直接运行）以及面向 Debian/Ubuntu 体系的标准安装包。

## 决策

1. **分发包形态**：
   - **AppImage**：真正的免安装单文件独立运行格式（内嵌 WebKitGTK 运行时桥接与 PyInstaller 打包的 Linux ELF sidecar 单文件，赋予执行权限后双击即可运行）。
   - **.deb**：Ubuntu / Debian 标准系统包（支持系统应用菜单与包管理器管理）。
   - 沿用 `packaging/tauri.release.conf.json` 分发配置，将 targets 统一设为 `["nsis", "appimage", "deb"]`。

2. **构建平台与 glibc 兼容性基线**：
   - Linux 构建运行在 `ubuntu-22.04` runner 上，编译出的二进制依赖 `glibc >= 2.35`，覆盖 Ubuntu 22.04/24.04、Debian 12、Fedora 37+、Arch 等绝大多数主流现代 Linux 桌面。

3. **sidecar 与资源随包契约**：
   - PyInstaller 运行在 Linux 环境，利用 `packaging/tod_sidecar.spec` 构建出单文件 ELF 二进制 `dist/tod-sidecar`。
   - Tauri resource 将小内核（`kernels/`）与 `tod-sidecar` 复制到 `src-tauri/binaries/tod-sidecar` 随 AppImage / deb 打包。
   - 运行时由 Tauri 壳在 `resource_dir` 下拉起 sidecar，星历大内核沿用用户数据目录（`~/.local/share/tod/kernels`）按需解析。

4. **CI Release 工作流更新**：
   - 在 `.github/workflows/release.yml` 中新增 `build-linux` 独立 job（并行于 `build-windows`）。
   - 自动将构建产物（`*.AppImage`, `*.deb`）直传 GitHub Release 资产。

## 结果

- Linux 用户获得了开箱即用（AppImage）与包管理器安装（deb）的完整支持。
- 全平台分发链路（Windows + Linux）完全对称且自动化。
