# Transfer Orbit Design

Transfer Orbit Design 是一组面向地月空间轨道设计的脚本和 GUI 工具，用于复现并扩展 Cui et al. (2025) 中的 DRO↔RO 两脉冲转移研究。仓库本身以脚本编排、参数管理、结果保存和可视化为主，核心动力学、修正器、延拓器和转移算法由本地 sibling 仓库 `e2m2e` 提供。

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

推荐使用 Python 3.13；项目要求 Python `>=3.11`。

```bash
conda create -n orbit-py313 python=3.13
conda activate orbit-py313
uv sync
```

`uv sync` 会安装本项目并从 `../e2m2e` 以 editable 方式安装核心算法依赖。若两个仓库不是 sibling 目录，请先调整 `pyproject.toml` 中的 `tool.uv.sources.e2m2e` 路径。

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

GUI 会按”生成 / 星历转换 / 转移 / 绘图”组织脚本，并根据 `tod/gui/scripts/` 中的注册信息展示参数、帮助文本和输出目录。

**语言切换**：GUI 支持 `zh`（中文，默认）和 `en`（英文）界面语言。修改 `gui_defaults.json` 中的 `”language”` 配置项后重启生效。缺失翻译时自动回退到中文。

### CLI

先生成基准轨道，再运行转移或绘图脚本。所有命令建议在仓库根目录执行。

```bash
# DRO / DPO / Halo
uv run python -m tod.generates.cr3bp.dro.generate_31_dro_orbit
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

# 星历修正示例（单轨道）
uv run python -m tod.generates.ephemeris.dro.correct_dro_to_ephemeris \
  --input-file output/dro/dro_31_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00

uv run python -m tod.generates.ephemeris.halo.correct_halo_to_ephemeris \
  --input-file output/halo/halo_family_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00
```

部分转移脚本仍含硬编码输入路径；运行前请检查对应脚本顶部或 `main()` 附近的默认文件路径，并替换为本地已生成的 JSON 文件。

## 脚本清单

### 轨道生成（CR3BP）

每个轨道族提供**单轨道生成**（固定周期微分修正）和**轨道族延拓**（自然延拓）两个脚本。

| 轨道族 | 单轨道脚本 | 轨道族脚本 | 说明 |
|--------|-----------|-----------|------|
| DRO | `tod.generates.cr3bp.dro.generate_31_dro_orbit` | `tod.generates.cr3bp.dro.generate_dro_family` | 次天体逆行轨道 |
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

> **已弃用**：旧的 RO 脚本（`tod.generates.cr3bp.ro.generate_31_ro_orbit`、`generate_31_ro_family`、`generate_32_ro_family`、`generate_rro_family`、`generate_aro_family`）及其独立绘图脚本已移至 `deprecated/` 目录，由 Resonant 族统一替代。

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
| DRO | `tod.generates.ephemeris.dro.correct_dro_to_ephemeris` | `tod.generates.ephemeris.dro.correct_dro_family_to_ephemeris` | 多重打靶修正到星历模型 |
| Halo | `tod.generates.ephemeris.halo.correct_halo_to_ephemeris` | `tod.generates.ephemeris.halo.correct_halo_family_to_ephemeris` | 多重打靶修正到星历模型 |
| 对比 | `tod.generates.ephemeris.compare_ephemeris_methods` | — | 对比直接多重打靶与 homotopy 方法 |

> 星历转换脚本还支持 `homotopy_dro_to_ephemeris`（DRO 单轨道的 homotopy λ-continuation 方法）。所有转换脚本通过 `--method` 参数选择算法，默认 `two_level`。

### 绘图

| 类别 | 脚本 | 功能 |
|------|------|------|
| DRO | `tod.plot.dro.plot_dro_family` | DRO 轨道族全局视图 |
| Halo | `tod.plot.halo.plot_halo_family` | Halo 轨道族 2D/3D 视图，支持按步长采样 |
| 星历 | `tod.plot.ephemeris.plot_ephemeris_correction` | DRO 星历修正结果对比图 |
| 星历 | `tod.plot.ephemeris.plot_halo_ephemeris_correction` | Halo 星历修正结果对比图 |
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
                    resonant）
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

## 文档与开发

- 开发规范：[`docs/development.md`](docs/development.md)
- 领域术语：[`CONTEXT.md`](CONTEXT.md) 与 [`docs/domain.md`](docs/domain.md)
- 本地 HTML 文档：

```bash
uv run --extra docs python -m sphinx -b html docs/source docs/build/html
```

## 许可证

当前仓库未声明开源许可证。复用前请联系维护者确认授权范围。
