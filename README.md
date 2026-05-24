# Transfer Orbit Design

Transfer Orbit Design 是一组面向地月空间轨道设计的脚本和 GUI 工具，用于复现并扩展 Cui et al. (2025) 中的 DRO↔RO 两脉冲转移研究。仓库本身以脚本编排、参数管理、结果保存和可视化为主，核心动力学、修正器、延拓器和转移算法由本地 sibling 仓库 `e2m2e` 提供。

## 功能全景

| 类别 | 能力 | 典型输出 |
|------|------|----------|
| CR3BP 轨道生成 | 3:1 DRO、3:1/3:2 RO、3D RRO、3D ARO、Halo 轨道和轨道族 | `output/dro/`、`output/ro/`、`output/halo/` 下的 JSON/CSV |
| 转移搜索 | DRO→RO、DRO→GEO、GEO→DRO、LEO→DRO 网格搜索 | `search_results_*.json` |
| 转移优化 | 基于网格搜索结果执行 NLP 优化，最小化两脉冲或插入代价 | `optimization_results_*.json` |
| 星历转换 | 将 CR3BP DRO/Halo 轨道或轨道族修正到真实星历模型 | `output/ephemeris/` 下的修正结果 JSON |
| 绘图与检查 | 轨道族全局视图、稳定性图、搜索/优化结果图、单轨道检查器 | Matplotlib 窗口或保存图片 |
| GUI | 以图形界面组织脚本、参数、输出目录和运行日志 | 桌面交互界面 |

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

GUI 会按“生成 / 星历转换 / 转移 / 绘图”组织脚本，并根据 `tod/gui/scripts/` 中的注册信息展示参数、帮助文本和输出目录。

### CLI

先生成基准轨道，再运行转移或绘图脚本。所有命令建议在仓库根目录执行。

```bash
# 生成 3:1 DRO 单轨道和 DRO 轨道族
uv run python -m tod.generates.cr3bp.dro.generate_31_dro_orbit
uv run python -m tod.generates.cr3bp.dro.generate_dro_family

# 生成 RO / Halo 轨道族
uv run python -m tod.generates.cr3bp.ro.generate_31_ro_family
uv run python -m tod.generates.cr3bp.ro.generate_32_ro_family
uv run python -m tod.generates.cr3bp.halo.generate_halo_family

# DRO → RO 转移：先网格搜索，再 NLP 优化
uv run python -m tod.transfers.dro_to_ro.grid_search_dro_to_ro
uv run python -m tod.transfers.dro_to_ro.optimize_dro_to_ro

# 星历修正示例
uv run python -m tod.generates.ephemeris.correct_dro_to_ephemeris \
  --input-file output/dro/dro_31_<timestamp>.json \
  --reference-epoch 2026-01-01T00:00:00
```

部分转移脚本仍含硬编码输入路径；运行前请检查对应脚本顶部或 `main()` 附近的默认文件路径，并替换为本地已生成的 JSON 文件。

## 脚本清单

| 类别 | 脚本 | 功能 |
|------|------|------|
| DRO 生成 | `tod.generates.cr3bp.dro.generate_31_dro_orbit` | 固定周期微分修正生成单条 3:1 DRO |
| DRO 生成 | `tod.generates.cr3bp.dro.generate_dro_family` | 从种子 DRO 出发自然延拓生成轨道族 |
| RO 生成 | `tod.generates.cr3bp.ro.generate_31_ro_orbit` | 生成单条 3:1 共振轨道 |
| RO 生成 | `tod.generates.cr3bp.ro.generate_31_ro_family` | 生成 3:1 RO 轨道族 |
| RO 生成 | `tod.generates.cr3bp.ro.generate_32_ro_family` | 生成 3:2 RO 轨道族 |
| RO 生成 | `tod.generates.cr3bp.ro.generate_rro_family` | 生成 3D RRO 轨道族 |
| RO 生成 | `tod.generates.cr3bp.ro.generate_aro_family` | 生成 3D ARO 轨道族 |
| Halo 生成 | `tod.generates.cr3bp.halo.generate_halo_orbit` | Richardson 三阶近似 + 微分修正生成 Halo 单轨道 |
| Halo 生成 | `tod.generates.cr3bp.halo.generate_halo_family` | 生成 Halo 轨道族，支持自然/伪弧长延拓 |
| DRO→RO | `tod.transfers.dro_to_ro.grid_search_dro_to_ro` | 搜索 DRO 出发、RO 到达的两脉冲候选 |
| DRO→RO | `tod.transfers.dro_to_ro.optimize_dro_to_ro` | 对候选转移执行 NLP 优化 |
| DRO→GEO | `tod.transfers.dro_to_geo.grid_search_dro_to_geo` | 搜索 DRO 到 GEO 球面的转移窗口 |
| DRO→GEO | `tod.transfers.dro_to_geo.optimize_dro_to_geo` | 优化 DRO 到 GEO 的插入轨迹 |
| GEO→DRO | `tod.transfers.geo_to_dro.grid_search_geo_to_dro` | 搜索 GEO 出发到 DRO 的候选转移 |
| GEO→DRO | `tod.transfers.geo_to_dro.optimize_geo_to_dro` | 优化 GEO 到 DRO 的转移结果 |
| LEO→DRO | `tod.transfers.leo_to_dro.grid_search_leo_to_dro` | 搜索 LEO 出发到 DRO 的转移窗口 |
| LEO→DRO | `tod.transfers.leo_to_dro.optimize_leo_to_dro` | 优化 LEO 到 DRO 的转移结果 |
| 星历转换 | `tod.generates.ephemeris.correct_dro_to_ephemeris` | 多重打靶修正单条 DRO 到星历模型 |
| 星历转换 | `tod.generates.ephemeris.homotopy_dro_to_ephemeris` | 通过 homotopy λ-continuation 修正 DRO |
| 星历转换 | `tod.generates.ephemeris.compare_ephemeris_methods` | 对比直接多重打靶与 homotopy 方法 |
| 绘图 | `tod.plot.*` | 绘制轨道族、转移搜索结果、优化结果和星历修正结果 |

## 输出数据

轨道与转移结果主要保存为 JSON。常见键包括：

- `states`：状态历史，CR3BP 中通常为无量纲 `[x, y, z, vx, vy, vz]`。
- `times`：与状态对应的时间数组。
- `period`：轨道周期或传播时长。
- `orbit_type`：轨道类型标识，例如 `DRO`、`RO`、`Halo`。
- `metadata`：脚本配置、延拓步数、误差统计等辅助信息。

`output/*/family.json` 是最近一次生成的快捷副本，会被覆盖；长期引用请使用带时间戳的文件名。

## 目录结构

```text
tod/
  commons/      常量、路径和通用工具
  generates/    CR3BP 轨道生成与 CR3BP→星历转换脚本
  transfers/    DRO/RO/GEO/LEO 转移搜索和优化脚本
  plot/         轨道、轨道族、搜索结果和优化结果绘图脚本
  gui/          PyQt6 GUI、脚本注册、参数面板和运行管理
docs/
  source/       Sphinx 文档源文件
  PRD/          产品/功能设计文档
  development.md 开发与文档规范
output/         运行脚本后按需创建的结果目录
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
