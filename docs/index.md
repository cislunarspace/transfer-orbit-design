---
sidebar_position: 1
---

# 转移轨道设计 - 技术文档

本文档涵盖 transfer-orbit-design 项目，该项目复现了 Cui 等人（2025）关于从月球远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移研究。

## 文档结构

### 设计文档（`design/`）— 与脚本对应

| 文档 | 对应脚本 | 描述 |
|------|----------|------|
| [DRO 生成](design/dro-generation.md) | `dro/generate_dro_family.py`, `dro/plot_dro_family.py` | 远距离逆行轨道族生成 |
| [RO 生成](design/ro-generation.md) | `ro/generate_31_ro_family.py`, `ro/generate_32_ro_family.py`, `ro/plot_*_ro_family.py` | 共振轨道族生成 |
| [RRO/ARO 生成](design/rro-aro-generation.md) | `ro/generate_rro_family.py`, `ro/generate_aro_family.py`, `ro/plot_rro_family.py`, `ro/plot_aro_family.py` | 3D 共振轨道生成 |
| [DRO-RO 转移](design/dro-ro-transfer.md) | `transfer/grid_search_dro_to_ro.py`, `transfer/optimize_dro_to_ro.py`, `transfer/plot_search_results.py`, `transfer/plot_optimize_result.py` | 两脉冲转移设计 |
| DRO→GEO 转移 | `transfer/grid_search_dro_to_geo.py`, `transfer/optimize_dro_to_geo.py`, `transfer/plot_search_results_geo.py` | DRO 到 GEO 转移设计 |
| GEO→DRO 转移 | `transfer/grid_search_geo_to_dro.py`, `transfer/optimize_geo_to_dro.py`, `transfer/plot_search_results_geo_to_dro.py` | GEO 到 DRO 转移设计 |
| LEO→DRO 转移 | `transfer/grid_search_leo_to_dro.py`, `transfer/optimize_leo_to_dro.py` | LEO 到 DRO 转移设计 |
| 星历修正 | `ephemeris/correct_dro_to_ephemeris.py`, `ephemeris/homotopy_dro_to_ephemeris.py`, `ephemeris/compare_ephemeris_methods.py`, `ephemeris/plot_ephemeris_correction.py` | CR3BP → 星历模型修正 |
| Halo 轨道 | `halo/generate_halo_orbit.py`, `halo/generate_halo_family.py`, `halo/plot_halo_orbit.py`, `halo/plot_halo_family.py` | Halo 轨道生成与可视化 |
| 轨道检查 | `inspection/plot_single_orbit.py`, `inspection/plot_interactive_orbit_inspector.py` | 单轨道与交互式轨道可视化 |

### 算法说明（`algorithms/`）

| 文档 | 描述 |
|------|------|
| [可行解判定](algorithms/feasible-candidate-criteria.md) | 网格搜索结果 `_is_feasible` 的阈值与逻辑 |
| [网格搜索与轨迹优化](algorithms/grid-search-trajectory-optimization.md) | 搜索-优化两步法的算法设计 |

### 理论基础（`theory/`）

| 文档 | 描述 |
|------|------|
| [CR3BP 理论](theory/cr3bp-theory.md) | 圆型限制性三体问题基础 |
| [微分修正](theory/differential-correction.md) | 周期轨道修正方法 |
| [参数延拓](theory/continuation-method.md) | 自然/伪弧长延拓生成轨道族 |

### 指南（`guides/`）

| 文档 | 描述 |
|------|------|
| [系统概述](guides/system-overview.md) | 项目架构、依赖和安装 |
| [开发指南](guides/development-guide.md) | e2m2e 依赖管理、IDE 配置 |
| GUI 使用 | PyQt6 桌面应用，浏览和运行脚本（`scripts/gui/main.py`） |

### 参考（`reference/`）

| 文档 | 描述 |
|------|------|
| [API 参考](reference/api-reference.md) | e2m2e 库 API 文档 |
| [脚本参考](reference/scripts-reference.md) | 所有脚本详细参数说明 |

### 项目计划

任务计划位于仓库根目录 `plan/` 目录。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 安装本地 e2m2e 依赖库（需要先克隆 e2m2e 仓库）
pip install -e /path/to/e2m2e

# 生成 DRO 族
python scripts/dro/generate_dro_family.py

# 生成单个 3:1 DRO 轨道
python scripts/dro/generate_31_dro_orbit.py

# 生成 3:1 RO 族
python scripts/ro/generate_31_ro_family.py

# 生成 3:2 RO 族
python scripts/ro/generate_32_ro_family.py

# 网格搜索转移轨道
python scripts/transfer/grid_search_dro_to_ro.py

# NLP 优化阶段
python scripts/transfer/optimize_dro_to_ro.py

# DRO→GEO 转移管线
python scripts/transfer/grid_search_dro_geo.py
python scripts/transfer/optimize_dro_geo.py

# 星历修正（需要 SPICE 内核）
python scripts/ephemeris/correct_dro_to_ephemeris.py

# 可视化结果
python scripts/dro/plot_dro_family.py
python scripts/ro/plot_31_ro_family.py
python scripts/ro/plot_32_ro_family.py
python scripts/transfer/plot_search_results.py <results.json>
```

## 轨道类型

```
DRO（远距离逆行轨道）
  ├── 2:1 DRO（周期 ~3.47 TU，月球周期的 1/2）
  └── 3:1 DRO（周期 ~2.09 TU，月球周期的 1/3）

RO（共振轨道）
  ├── 3:1 RO（周期 ~6.28 TU）
  └── 3:2 RO（周期 ~12.57 TU）

RRO/ARO（3D 共振轨道）— 当前 Phase 1b 已推迟
  ├── RRO（反射共振轨道，z 振幅 Az=0.2）
  └── ARO（轴向共振轨道，z 振幅 Az=0.2）
```
