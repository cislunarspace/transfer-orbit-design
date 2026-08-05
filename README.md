# transfer-orbit-design — 地月空间轨道设计 GUI 与脚本工具集

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/cislunarspace/transfer-orbit-design?style=flat)](https://github.com/cislunarspace/transfer-orbit-design/stargazers)
[![Issues](https://img.shields.io/github/issues/cislunarspace/transfer-orbit-design)](https://github.com/cislunarspace/transfer-orbit-design/issues)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

中文 | [English](README.en.md)

transfer-orbit-design 是 e2m2e 的 **GUI 前端与脚本工具集**。e2m2e 提供地月空间轨道设计所需的动力学模型、修正器、延拓器与转移算法；本仓库把它们封装成可视化桌面应用与可复现脚本。它不实现算法，只做三件事——调用（经 e2m2e Facade API 发起计算）、管理（以 Project/Artifact 组织全部计算产物）、呈现（内嵌画布可视化结果）。用户不需要接触算法内部，通过“选工件 → 选操作 → 看结果”的三步交互，即可完成轨道设计、轨道保持与结果检查。

## 安装

### 克隆 e2m2e 依赖库

核心算法依赖 `e2m2e`，它在 `pyproject.toml` 中被配置为本地路径依赖（`../e2m2e`），`uv sync` 不会自动拉取，需要先手动克隆到与本仓库同级的目录：

```bash
cd ..
git clone https://github.com/cislunarspace/e2m2e.git
cd transfer-orbit-design
```

无需在 e2m2e 目录里单独安装，下一步的 `uv sync` 会以 editable 模式装好它。

### uv（推荐）

项目要求 Python `>=3.13`，仓库已通过 `.python-version` 固定。在仓库根目录执行：

```bash
uv sync
```

`uv sync` 一次完成：准备 Python 3.13 解释器、创建虚拟环境、安装全部 PyPI 依赖、以 editable 模式安装 `../e2m2e` 与本项目。若两个仓库不在同级目录，请先修改 `pyproject.toml` 中的 `tool.uv.sources.e2m2e` 路径。

### 打包版（Windows 便携包 + SPICE kernels）

从 GitHub Releases 下载 `TransferOrbitDesign-windows.zip`，解压即用，无需配置环境变量。另从 [`spice-data-v1`](https://github.com/cislunarspace/transfer-orbit-design/releases/tag/spice-data-v1) release 下载 `spice-kernels.zip`，解压到 `TransferOrbitDesign.exe` 所在目录（得到 `kernels/` 子目录），应用启动时会自动探测；显式设置 `SPICE_KERNEL_DIR` 环境变量仍然优先。该 release 还附带 MICE 工具包（供 MATLAB 等完整开发使用），运行本应用不需要。

### SPICE 内核

星历动力学需要 NASA SPICE 内核文件，放在 `kernels/` 目录或 `$SPICE_KERNEL_DIR` 指定的路径。必需的九个内核：`de430.bsp`、`de440s.bsp`、`earth_latest_high_prec.bpc`、`SPICEEarthPredictedKernel.bpc`、`SPICELunaCurrentKernel.bpc`、`SPICELunaFrameKernel.tf`、`naif0011.tls`、`naif0012.tls`、`pck00010.tpc`。推荐从 [e2m2e 的 `kernels-v1` release](https://github.com/cislunarspace/e2m2e/releases) 下载打包好的全部必需内核（国内可访问）；[NASA NAIF](https://naif.jpl.nasa.gov/naif/data.html) 为备用来源。

## 快速开始

### GUI

```bash
uv run python -m src.app.main
```

或使用已安装的控制台入口：

```bash
uv run transfer-orbit-design-v2
```

启动时 GUI 自动扫描 `output/` 目录，把历史运行结果重建为项目树中的 Artifact。界面为三栏布局：左侧项目树、中间可视化画布 + 日志标签页、右侧工具选择器 + 参数面板 + 运行按钮。

一次完整的轨道设计操作流：

1. 在右侧工具选择器中选「轨道设计」。
2. 轨道类型选 DRO，填写振幅（km）、相位（0~1）、起始历元、维持时间与输出步长。
3. 点击运行。计算在后台线程执行，日志面板逐条输出进度。
4. 完成后结果以 `output/dro/dro_<ts>.json` + `.npz` 双文件落盘，轨道随即叠加显示在画布上。
5. 工具栏可切换 3D / XY / XZ / YZ 投影，开关地月天体与 L1–L5 平动点标注；Ctrl+点击项目树可多选轨道叠加对比。

轨道保持：在项目树中右键轨道 → 选择「轨道保持」，以该轨道星历为输入做蒙特卡洛仿真，结果写入 `output/ephemeris/`。

### 脚本与 CLI

需要 CR3BP 轨道生成、转移搜索与优化、星历修正、绘图等脚本工作流时，见 [Sphinx 文档](https://cislunarspace.github.io/transfer-orbit-design/zh/) 中的脚本索引与 API 参考。旧的 `tod/` 目录仍保留这套脚本。

## 使命与进度

地月空间轨道设计既要求算法算得准，也要求工具用得上。e2m2e 建设地月方向的算法工具集基础设施——动力学建模、轨道族生成、转移设计；transfer-orbit-design 则把这些能力带到人机交互层面：可视化桌面应用、参数管理、结果落盘与检查。两者分工是，e2m2e 管“算”，本仓库管“用”。整体架构设计见 [docs/architecture/architecture.md](docs/architecture/architecture.md)，逐项架构决策见 [docs/adr/](docs/adr/)。

| 能力 | 实现状态 | 说明 |
|------|---------|------|
| 轨道设计（DRO/NRHO/Halo/Lissajous/L4/L5） | 已实现 | 参数面板由 Pydantic 模型自动生成，结果 JSON+NPZ 双文件落盘 |
| 轨道保持（蒙特卡洛） | 已实现 | 以选中轨道星历为输入，输出受控星历与 Δv 统计 |
| 多轨道可视化 | 已实现 | 3D/XY/XZ/YZ 投影、地月/L1–L5 标注、多轨道叠加 |
| Artifact 持久化闭环 | 已实现 | 启动扫描 `output/` 重建 Project，数组 NPZ 懒加载 |
| CLI 脚本工作流 | 已实现（遗留） | `tod/` 下的脚本，见 Sphinx 文档 |
| 轨道族生成 / 稳定性分析 | 规划中 | 工具下拉灰显占位 |

## 文档

在线文档：<https://cislunarspace.github.io/transfer-orbit-design/zh/>

本地构建：

```bash
uv sync --extra docs
uv run sphinx-build -b html -D language=zh docs/source docs/build/html
```

## 测试与代码规范

```bash
uv run pytest tests/ -m "not spice"
uv run ruff check .
uv run pyright
```

## 贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## License

[Apache 2.0](LICENSE)
