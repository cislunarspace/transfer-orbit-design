# Transfer Orbit Design

[![Release](https://img.shields.io/github/v/release/cislunarspace/transfer-orbit-design?label=release)](https://github.com/cislunarspace/transfer-orbit-design/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/cislunarspace/transfer-orbit-design/ci.yml?branch=master&label=CI)](https://github.com/cislunarspace/transfer-orbit-design/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/cislunarspace/transfer-orbit-design?style=flat)](https://github.com/cislunarspace/transfer-orbit-design/stargazers)
[![Issues](https://img.shields.io/github/issues/cislunarspace/transfer-orbit-design)](https://github.com/cislunarspace/transfer-orbit-design/issues)
[![Last commit](https://img.shields.io/github/last-commit/cislunarspace/transfer-orbit-design/master)](https://github.com/cislunarspace/transfer-orbit-design/commits/master)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Transfer Orbit Design 是一组面向地月空间轨道设计的脚本和 GUI 工具，提供 CR3BP 周期轨道族生成、DRO↔RO/GEO/LEO 转移搜索与优化、CR3BP 到星历模型的修正，以及配套的绘图与图形界面。本仓库负责脚本编排、参数管理、结果保存和可视化；动力学、修正器、延拓器和转移算法由同级目录下的 `e2m2e` 仓库提供。

> 本工具服务于地月空间发展的三大技术方向：**在轨机动**、**在轨服务**、**地月技术**。当前版本聚焦“在轨机动”方向的轨道设计基础能力，并以此为基座向其余两个方向扩展。背景、能力对应关系与后续路线图见文末「[使命与路线图](#使命与路线图)」。

## 功能全景

| 类别 | 能力 | 典型输出 |
|------|------|----------|
| CR3BP 轨道生成 | 12 类周期轨道族：DRO、DPO、Halo、Lyapunov、Vertical、Axial、Butterfly、SPO、LPO、Tadpole、Horseshoe、Resonant（3:1/3:2/2:1） | `output/<orbit-type>/` 下的 JSON/CSV |
| 转移搜索 | DRO→RO、DRO→GEO、GEO→DRO、LEO→DRO 网格搜索 | `search_results_*.json` |
| 转移优化 | 基于网格搜索结果执行 NLP 优化，最小化两脉冲或插入代价 | `optimization_results_*.json` |
| 星历转换 | 将 CR3BP DRO/Halo 轨道或轨道族修正到真实星历模型 | `output/ephemeris/` 下的修正结果 JSON |
| 绘图与检查 | 轨道族全局视图、稳定性图、搜索/优化结果图、单轨道检查器 | Matplotlib 窗口或保存图片 |
| GUI | 图形界面组织脚本、参数、输出目录和运行日志；支持 zh/en 中英文切换 | 桌面交互界面 |

## 安装

### 1. 克隆 e2m2e 依赖库

本项目的核心算法依赖 `e2m2e`，它在 `pyproject.toml` 中被配置为本地路径依赖（`../e2m2e`），因此 `uv sync` 不会自动从远程拉取，需要先手动克隆到与本仓库同级的目录：

```bash
cd ..
git clone https://github.com/cislunarspace/e2m2e.git
cd transfer-orbit-design
```

无需在 e2m2e 目录里单独安装，下一步的 `uv sync` 会以 editable 模式装好它。

### 2. 安装本项目

项目要求 Python `>=3.13`，仓库已通过 `.python-version` 固定为 3.13。在仓库根目录执行：

```bash
uv sync
```

`uv sync` 会一次完成：准备 Python 3.13 解释器、创建虚拟环境、安装全部 PyPI 依赖、以 editable 模式从 `../e2m2e` 安装核心算法库，并以 editable 模式安装本项目。若两个仓库不在同级目录，请先修改 `pyproject.toml` 中的 `tool.uv.sources.e2m2e` 路径。

星历转换脚本还需要 SPICE kernels：

```bash
export SPICE_KERNEL_DIR=../e2m2e/kernels
# 目录中应包含 de440.bsp 和 naif0012.tls
```

## 快速入门

### GUI

```bash
uv run python -m tod.gui.main
```

GUI 会按“生成 / 星历转换 / 转移 / 绘图”组织脚本，并根据 `tod/gui/scripts/` 中的注册信息展示参数、帮助文本和输出目录。

**语言切换**：GUI 支持 `zh`（中文，默认）和 `en`（英文）两种界面语言。修改 `gui_defaults.json` 中的 `"language"` 配置项后重启生效；缺失的翻译条目自动回退到中文。

### CLI

先生成基准轨道，再运行转移或绘图脚本。命令都在仓库根目录执行。

```bash
# DRO / DPO / Halo
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit --jacobi 3.1
uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit --seed-id earth-moon_dro:000001
uv run python -m tod.generates.cr3bp.dro.generate_dro_family
uv run python -m tod.generates.cr3bp.dpo.generate_dpo_orbit
uv run python -m tod.generates.cr3bp.dpo.generate_dpo_family
uv run python -m tod.generates.cr3bp.halo.generate_halo_family

# 平动点轨道族
uv run python -m tod.generates.cr3bp.lyapunov.generate_lyapunov_family
uv run python -m tod.generates.cr3bp.vertical.generate_vertical_family
uv run python -m tod.generates.cr3bp.axial.generate_axial_family

# 三角平动点轨道族
uv run python -m tod.generates.cr3bp.spo.generate_spo_family
uv run python -m tod.generates.cr3bp.lpo.generate_lpo_family
uv run python -m tod.generates.cr3bp.tadpole.generate_tadpole_family
uv run python -m tod.generates.cr3bp.horseshoe.generate_horseshoe_family

# 特殊拓扑轨道族
uv run python -m tod.generates.cr3bp.butterfly.generate_butterfly_family
uv run python -m tod.generates.cr3bp.resonant.generate_resonant_family --ratio 3:1

# 转移：先网格搜索，再 NLP 优化
uv run python -m tod.transfers.dro_to_ro.grid_search_dro_to_ro
uv run python -m tod.transfers.dro_to_ro.optimize_dro_to_ro

# 星历修正示例（单轨道，支持 DRO 和 Halo）
uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris \
  --input-file output/dro/dro_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00 \
  --orbit-type dro

uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris \
  --input-file output/halo/halo_family_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00 \
  --orbit-type halo
```

部分转移脚本仍带有硬编码的输入路径。运行前请检查脚本顶部或 `main()` 附近的默认文件路径，改成本地已生成的 JSON 文件。

## 脚本清单

### 轨道生成（CR3BP）

DRO 单轨生成入口已从旧的 3:1 专用脚本改名为 `generate_dro_orbit`。manual 路径继续支持 `--x0/--vy0/--period` 并执行固定周期微分修正；catalog 路径可通过 `--jacobi` 或 `--seed-id` 从 `data/cr3bp_data/normalized` 选择完整 6 维 seed 并直接传播保存。若 normalized catalog 缺失，脚本默认从 `data/cr3bp_data/raw` 自动生成；传入 `--no-auto-build-catalog` 可禁用自动生成。单轨输出命名为 `output/dro/dro_<timestamp>.json`；`dro_31_family_*` 等 DRO family artifact 不受单轨改名影响。

每个轨道族提供**单轨道生成**（固定周期微分修正）和**轨道族延拓**（自然延拓）两个脚本。

| 轨道族 | 单轨道脚本 | 轨道族脚本 | 说明 |
|--------|-----------|-----------|------|
| DRO | `tod.generates.cr3bp.dro.generate_dro_orbit` | `tod.generates.cr3bp.dro.generate_dro_family` | 次天体逆行轨道 |
| DPO | `tod.generates.cr3bp.dpo.generate_dpo_orbit` | `tod.generates.cr3bp.dpo.generate_dpo_family` | 次天体顺行轨道 |
| Halo | `tod.generates.cr3bp.halo.generate_halo_orbit` | `tod.generates.cr3bp.halo.generate_halo_family` | 三维周期轨道，支持自然/伪弧长延拓 |
| Lyapunov | `tod.generates.cr3bp.lyapunov.generate_lyapunov_orbit` | `tod.generates.cr3bp.lyapunov.generate_lyapunov_family` | 平面周期轨道，沿共线平动点主轴振荡 |
| Vertical | `tod.generates.cr3bp.vertical.generate_vertical_orbit` | `tod.generates.cr3bp.vertical.generate_vertical_family` | 垂直方向振荡的周期轨道 |
| Axial | `tod.generates.cr3bp.axial.generate_axial_orbit` | `tod.generates.cr3bp.axial.generate_axial_family` | 沿平动点轴向的周期轨道 |
| Butterfly | `tod.generates.cr3bp.butterfly.generate_butterfly_orbit` | `tod.generates.cr3bp.butterfly.generate_butterfly_family` | 连接两个共线平动点的对称轨道 |
| SPO | `tod.generates.cr3bp.spo.generate_spo_orbit` | `tod.generates.cr3bp.spo.generate_spo_family` | 三角平动点短周期轨道 |
| LPO | `tod.generates.cr3bp.lpo.generate_lpo_orbit` | `tod.generates.cr3bp.lpo.generate_lpo_family` | 三角平动点长周期轨道 |
| Tadpole | `tod.generates.cr3bp.tadpole.generate_tadpole_orbit` | `tod.generates.cr3bp.tadpole.generate_tadpole_family` | 围绕单个三角平动点的蝌蚪形轨道 |
| Horseshoe | `tod.generates.cr3bp.horseshoe.generate_horseshoe_orbit` | `tod.generates.cr3bp.horseshoe.generate_horseshoe_family` | 跨越两个三角平动点的马蹄形轨道 |
| Resonant | `tod.generates.cr3bp.resonant.generate_resonant_orbit` | `tod.generates.cr3bp.resonant.generate_resonant_family` | m:n 共振周期轨道，通过 `--ratio` 选择 3:1 / 3:2 / 2:1 |

### 转移搜索与优化

| 转移方向 | 搜索脚本 | 优化脚本 | 说明 |
|---------|---------|---------|------|
| DRO → RO | `tod.transfers.dro_to_ro.grid_search_dro_to_ro` | `tod.transfers.dro_to_ro.optimize_dro_to_ro` | 两脉冲候选搜索 + NLP 优化 |
| DRO → GEO | `tod.transfers.dro_to_geo.grid_search_dro_to_geo` | `tod.transfers.dro_to_geo.optimize_dro_to_geo` | GEO 球面插入窗口搜索 + 优化 |
| GEO → DRO | `tod.transfers.geo_to_dro.grid_search_geo_to_dro` | `tod.transfers.geo_to_dro.optimize_geo_to_dro` | GEO 出发到 DRO 的搜索 + 优化 |
| GEO → DRO | — | `tod.transfers.geo_to_dro.validate_geo_to_dro` | 验证 GEO→DRO 转移结果 |
| LEO → DRO | `tod.transfers.leo_to_dro.grid_search_leo_to_dro` | `tod.transfers.leo_to_dro.optimize_leo_to_dro` | LEO 出发到 DRO 的搜索 + 优化 |

### 星历转换

| 目标 | 单轨道 | 轨道族 | 说明 |
|------|--------|--------|------|
| 通用 | `tod.generates.ephemeris.correct_orbit_to_ephemeris` | — | 统一入口，支持 DRO/Halo 及多方法选择 |
| DRO | — | `tod.generates.ephemeris.dro.correct_dro_family_to_ephemeris` | 轨道族多重打靶修正到星历模型 |
| Halo | — | `tod.generates.ephemeris.halo.correct_halo_family_to_ephemeris` | 轨道族多重打靶修正到星历模型 |

> `correct_orbit_to_ephemeris` 通过 `--orbit-type`（`dro`/`halo`）和 `--method`（`standard`/`two_level`/`homotopy`）选择轨道类型与修正方法。`--output-prefix` 自动生成 `{prefix}_{method}_tol{tol}.json`。输出包含计时与地心距统计。所有转换方法通过 `--method` 参数选择，默认 `two_level`。

### 绘图

| 类别 | 脚本 | 功能 |
|------|------|------|
| DRO | `tod.plot.dro.plot_dro_family` | DRO 轨道族全局视图 |
| Halo | `tod.plot.halo.plot_halo_family` | Halo 轨道族 2D/3D 视图，支持按步长采样 |
| 星历 | `tod.plot.ephemeris.plot_ephemeris_correction` | 星历修正结果对比图 |
| 检查 | `tod.plot.inspection.plot_single_orbit` | 单轨道检查器 |
| 检查 | `tod.plot.inspection.plot_interactive_orbit_inspector` | 交互式轨道检查器 |
| 转移 | `tod.plot.transfer.dro_to_ro.plot_search_results_dro_to_ro` | DRO→RO 搜索结果可视化 |
| 转移 | `tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro` | DRO→RO 优化结果可视化 |
| 转移 | `tod.plot.transfer.dro_to_geo.*` | DRO→GEO 搜索/优化结果可视化 |
| 转移 | `tod.plot.transfer.geo_to_dro.*` | GEO→DRO 搜索/优化结果可视化 |
| 转移 | `tod.plot.transfer.leo_to_dro.*` | LEO→DRO 搜索/优化结果可视化 |

> 各轨道族的绘图脚本遵循统一的 `FamilyPlotOrchestrator` 架构。部分旧轨道族（RO 系列）的独立绘图脚本已整合到 orchestrator 中。

## 输出数据

轨道与转移结果主要保存为 JSON。常见键包括：

- `states`：状态历史，CR3BP 中通常为无量纲 `[x, y, z, vx, vy, vz]`。
- `times`：与状态对应的时间数组。
- `period`：轨道周期或传播时长。
- `orbit_type`：轨道类型标识，如 `DRO`、`DPO`、`Halo`、`Lyapunov`、`Vertical`、`Axial`、`Butterfly`、`SPO`、`LPO`、`Tadpole`、`Horseshoe`、`Resonant`。
- `metadata`：脚本配置、延拓步数、误差统计等辅助信息。

`output/*/family.json` 是最近一次生成的快捷副本，会被覆盖；长期引用请使用带时间戳的文件名。

## 目录结构

```text
tod/
  commons/        常量、路径和通用工具
  generates/      CR3BP 轨道生成与 CR3BP→星历转换脚本
    cr3bp/          各轨道族生成（dro, dpo, halo, lyapunov, vertical,
                    axial, butterfly, spo, lpo, tadpole, horseshoe,
                    resonant, ...）
    ephemeris/      DRO/Halo 星历转换（单轨道与轨道族）
  transfers/      DRO/Resonant/GEO/LEO 转移搜索和优化脚本
  plot/           轨道、轨道族、搜索结果和优化结果绘图脚本
  gui/            PyQt6 GUI、脚本注册、参数面板、运行管理、主题与国际化
docs/
  source/         Sphinx 文档源文件
  PRD/            产品/功能设计文档
  adr/            架构决策记录
  development.md  开发与文档规范
output/           运行脚本后按需创建的结果目录
```

## 使命与路线图

### 使命背景

Transfer Orbit Design 面向地月空间发展需求，围绕三个技术方向展开：**在轨机动**、**在轨服务**、**地月技术**。它的定位是为这三个方向提供可复现、可扩展的轨道设计与分析基座。当前版本已在“在轨机动”方向落地核心能力，其余两个方向按路线图逐步推进。

状态标识：✅ 已实现　🚧 开发中　📐 规划中

### 一、在轨机动　✅ 已实现

这一方向的目标是大幅提升轨道机动能力。软件在其中的作用，是用 CR3BP 低能量轨道与转移设计**支撑**这一目标，而不是由软件本身完成机动——后者是任务层面的工程目标。

当前已实现的能力对应到本仓库的脚本：

- **周期轨道族生成**：12 类 CR3BP 周期轨道族（DRO、DPO、Halo、Lyapunov、Vertical、Axial、Butterfly、SPO、LPO、Tadpole、Horseshoe、Resonant），可作为转移设计的出发/目标轨道。见[轨道生成（CR3BP）](#轨道生成cr3bp)。
- **转移搜索与优化**：DRO→RO、DRO→GEO、GEO→DRO、LEO→DRO 的两脉冲网格搜索与 NLP 优化，最小化 Δv 或插入代价，为低能耗转移设计提供候选解。见[转移搜索与优化](#转移搜索与优化)。
- **星历修正**：将 CR3BP 设计结果多重打靶修正到真实星历模型，缩小设计与工程实现的差距。见[星历转换](#星历转换)。

### 二、在轨服务　📐 规划中

目标方向：航天器在轨加注、维修与快速替换。计划覆盖：

- 交会接近段的轨迹设计
- 在轨加注、服务任务的窗口与机动序列规划
- 服务航天器与目标航天器的协同轨道设计

> 当前版本尚无对应实现，列入后续路线图。

### 三、地月技术　📐 规划中

目标方向：支撑深空域感知与行动，突破地月空间态势表征、轨道编目、导航、通信与控制等技术。计划覆盖：

- 地月空间态势表征与可观测性分析
- 轨道编目与目标关联
- 面向导航、通信、控制的轨道支撑设计

> 当前版本尚无对应实现，列入后续路线图。

### 对标与定位

Transfer Orbit Design 与 STK Cislunar Orbit Design (CODE)、NASA General Mission Analysis Tool (GMAT)、普渡大学 Adaptive Trajectory Design (ATD) 同属地月空间轨道设计领域，方法论基础一致：CR3BP/BR4BP 动力学、微分修正、自然与伪弧长延拓、星历多重打靶修正。与这几个成熟平台相比，本工具的侧重点是轻量和开源：用可读的脚本和可复现的流水线组织轨道生成、转移搜索与星历修正，便于按需裁剪、二次开发，或嵌入更大的任务设计流程，而不追求功能上的对等。

## 文档与开发

- 开发规范：[`docs/development.md`](docs/development.md)
- 领域术语：[`CONTEXT.md`](CONTEXT.md) 与 [`docs/domain.md`](docs/domain.md)
- 本地 HTML 文档：

```bash
uv run --extra docs python -m sphinx -b html docs/source docs/build/html
```

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 授权。你可以自由使用、修改和分发本软件，但需保留版权与许可声明，并遵守许可证中的专利授权与商标条款。详见仓库根目录的 [`LICENSE`](LICENSE) 文件。
