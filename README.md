# Transfer Orbit Design — DRO to RO Two-Impulse Transfer

## 项目概述

本项目旨在复现以下论文的研究成果：

> **Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits**  
> Shuhao Cui, Yue Wang, Ruikang Zhang, Hao Zhang, Yang Gao  
> *Journal of Guidance, Control, and Dynamics*, Vol. 48, No. 6, June 2025  
> DOI: [10.2514/1.G008582](https://doi.org/10.2514/1.G008582)

该论文研究了地月系统中从远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移轨道设计问题，并提出了一种"搜索-优化"两步法。除论文核心的 DRO↔RO 转移外，本仓库还扩展了 DRO↔GEO、GEO↔DRO、LEO↔DRO 的转移设计 pipeline。

## 环境配置

在仓库根目录执行一次：

```bash
uv sync
```

这会安装所有 Python 依赖（numpy, scipy, matplotlib, PyQt6, pytest）以及核心算法库 **e2m2e**（通过 git 依赖）。

## 快速开始

### 生成基线轨道

```bash
uv run python scripts/dro/generate/generate_31_dro_orbit.py    # 单个 3:1 DRO
uv run python scripts/dro/generate/generate_dro_family.py       # DRO 族
uv run python scripts/ro/generate/generate_31_ro_orbit.py       # 单个 3:1 RO
uv run python scripts/ro/generate/generate_31_ro_family.py      # 3:1 RO 族
uv run python scripts/ro/generate/generate_32_ro_family.py      # 3:2 RO 族
uv run python scripts/ro/generate/generate_rro_family.py        # 3D RRO 族
uv run python scripts/ro/generate/generate_aro_family.py        # 3D ARO 族
uv run python scripts/halo/generate/generate_halo_orbit.py      # Halo 轨道
uv run python scripts/halo/generate/generate_halo_family.py     # Halo 轨道族
```

### DRO → RO 转移

```bash
# 1. 网格搜索
uv run python scripts/transfer/dro_to_ro/grid_search_dro_to_ro.py

# 2. NLP 优化
uv run python scripts/transfer/dro_to_ro/optimize_dro_to_ro.py

# 3. 可视化
uv run python scripts/transfer/dro_to_ro/plot_search_results_dro_to_ro.py <results.json> [--time-dv] [--orbit] [--idx N]
uv run python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py <results.json>
```

### DRO → GEO 转移

```bash
uv run python scripts/transfer/dro_to_geo/grid_search_dro_to_geo.py
uv run python scripts/transfer/dro_to_geo/optimize_dro_to_geo.py
uv run python scripts/transfer/dro_to_geo/plot_search_results_dro_to_geo.py <results.json>
```

### GEO → DRO 转移

```bash
uv run python scripts/transfer/geo_to_dro/grid_search_geo_to_dro.py
uv run python scripts/transfer/geo_to_dro/optimize_geo_to_dro.py
uv run python scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py <results.json>
uv run python scripts/transfer/geo_to_dro/plot_optimize_result_geo_to_dro.py <results.json>
```

### LEO → DRO 转移

```bash
uv run python scripts/transfer/leo_to_dro/grid_search_leo_to_dro.py
uv run python scripts/transfer/leo_to_dro/optimize_leo_to_dro.py
```

### 星历修正（CR3BP → 星历）

需要 SPICE kernels（`de440.bsp`、`naif0012.tls`）放置在 `e2m2e/kernels/` 或设置 `SPICE_KERNEL_DIR` 环境变量。

```bash
uv run python scripts/ephemeris/correct/correct_dro_to_ephemeris.py    # 多重打靶法
uv run python scripts/ephemeris/correct/homotopy_dro_to_ephemeris.py   # 同伦法
uv run python scripts/ephemeris/compare/compare_ephemeris_methods.py   # 方法对比
```

### 轨道可视化

```bash
uv run python scripts/inspection/plot_single_orbit.py <orbit.json>
uv run python scripts/inspection/plot_interactive_orbit_inspector.py <family.json>
```

### GUI

```bash
uv run python scripts/gui/main.py
```

## 论文核心内容

### 动力学模型

| 模型 | 说明 |
|------|------|
| **CR3BP**（圆型限制性三体问题） | 地月系统基本模型，用于计算基线轨道和初步转移设计 |
| **BR4BP**（双圆限制性四体问题） | 在 CR3BP 基础上加入太阳引力，用于转移轨道精化 |
| **星历模型**（Ephemeris Model） | 基于 DE438 星历的限制性 N 体问题，用于真实场景验证 |

### 基线轨道

- **初始轨道**：2:1 DRO 和 3:1 DRO（周期分别为月球恒星周期的 1/2 和 1/3）
- **终端轨道（平面）**：3:2 RO 和 3:1 RO（精确共振比的轨道）
- **终端轨道（非平面）**：3D 反射共振轨道（RRO）和轴向共振轨道（ARO），z 振幅 $A_z = 0.2$

### 两步转移设计方法

1. **搜索阶段（Search Phase）**
   - 搜索变量：出发点位置、切向速度比 $\alpha$、法向速度比 $\beta$（非平面情况）、太阳初始相位 $\theta_{s0}$（BR4BP）
   - 对搜索变量在设定范围内进行网格化，前向积分获取可行转移轨迹
   - 筛选与终端轨道相交或距离局部最小的轨迹作为初始猜测

2. **优化阶段（Optimization Phase）**
   - 将转移问题转化为非线性规划（NLP）问题
   - 优化变量：$y = \{\alpha, T, t_{ins}\}$（平面 CR3BP 情况）
   - 目标函数：$J(y) = \Delta v_1 + \Delta v_2$（最小化总脉冲）
   - 约束条件：位置连续性、速度方向约束、避免撞击地球和月球
   - 使用序列二次规划（SQP）算法求解

### 三种典型转移类型

| 转移类型 | 特点 | 转移时间 | 燃料消耗 |
|----------|------|----------|----------|
| **直接转移（Direct Transfer）** | 短时间，近似椭圆轨道，不到一圈地球 | < 20 天 | 较高 |
| **月球借力转移（LGA Transfer）** | 利用月球近飞段改变速度方向，多圈调相 | 60–80 天 | 最低 |
| **外部转移（External Transfer）** | 远地点超过 3 倍地月距离；BR4BP 中类似 WSB 转移 | 60–100 天 | 中等 |

### 关键物理参数

| 符号 | 值 | 含义 |
|------|-----|------|
| $\mu$ | $1.21506683 \times 10^{-2}$ | 地月系统质量比 |
| $m_s$ | $3.28900541 \times 10^{5}$ | 太阳无量纲质量 |
| $\omega_s$ | $9.25195985 \times 10^{-1}$ | 太阳无量纲角速度 |
| $\rho$ | $3.88811143 \times 10^{2}$ | 太阳至地月质心无量纲距离 |
| DU | $3.84405 \times 10^{5}$ km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
| VU | 1023.23281 m/s | 速度单位 |

## 代码架构

核心算法代码位于 `e2m2e` 项目中，`transfer-orbit-design/scripts/` 包含各阶段的任务脚本。

### e2m2e 核心库（`e2m2e/e2m2e/`）

```
e2m2e/
├── algorithms/          # 算法模块
│   ├── continuation.py              # 自然参数延拓 / 伪弧长延拓
│   ├── differential_correction.py   # 微分修正算法
│   └── stability.py                 # 单值矩阵特征值分析
├── core/               # 核心模块
│   ├── dynamics.py                  # CR3BP/BR4BP 动力学
│   ├── orbit.py                     # Orbit / OrbitFamily 数据结构
│   └── system.py                    # CR3BP 系统参数管理
├── transfer/           # 转移轨道设计
│   ├── transfer_base.py             # 转移基类
│   ├── transfer_optimization.py     # NLP 优化器
│   └── transfer_search.py           # 网格搜索
└── visualization/      # 可视化
    ├── config.py                    # PlotConfig 绘图配置
    ├── base.py                      # BasePlotter 基类
    ├── family.py                    # FamilyPlotter 轨道族绘图
    ├── transfer.py                  # TransferPlotter 转移绘图
    ├── stability.py                 # 稳定性可视化
    └── plotting.py                  # 向后兼容 shim
```

### transfer-orbit-design 任务脚本（`scripts/`）

```
scripts/
├── utils/              # 共享工具
│   ├── constants.py              # 物理常量（MU, DU, TU, VU 等）
│   ├── common.py                 # 文件 helper + safe_resolve_within 路径安全
│   ├── geo.py                    # GEO 常量与 helper
│   ├── leo.py                    # LEO 常量与 helper
│   ├── optimize_helpers.py       # BLAS 线程控制 + OptimizationProgress
│   └── plot_helpers.py           # 采样等绘图共享工具
├── dro/                # DRO 轨道
│   ├── generate/                 # 生成脚本
│   └── plot/                     # 可视化
├── ro/                 # RO 轨道族（3:1, 3:2, RRO, ARO）
│   ├── generate/                 # 生成脚本
│   └── plot/                     # 可视化
├── halo/               # Halo 轨道
│   ├── generate/                 # 生成脚本
│   └── plot/                     # 可视化
├── transfer/           # 转移搜索 + NLP 优化
│   ├── dro_to_ro/               # DRO → RO
│   ├── dro_to_geo/              # DRO → GEO
│   ├── geo_to_dro/              # GEO → DRO
│   └── leo_to_dro/              # LEO → DRO
├── ephemeris/          # CR3BP → 星历修正
│   ├── correct/                 # 多重打靶 / 同伦法
│   ├── compare/                 # 方法对比
│   └── plot/                    # 可视化
├── inspection/         # Standalone 轨道可视化
└── gui/                # PyQt6 桌面应用
    ├── main.py                   # 入口
    ├── main_window.py            # 主窗口
    ├── script_registry.py        # 脚本注册表
    ├── job_manager.py            # 多进程 Job 管理
    ├── output_panel.py           # 结构化输出面板
    ├── file_discovery.py         # 文件发现
    ├── params_panel.py           # CliWidgetFactory 控件工厂
    ├── settings_dialog.py        # 设置对话框
    └── themes/                   # 主题 QSS 样式表
output/                # 生成数据（gitignored）
tests/                 # pytest 测试
```

### 输出目录

- `output/dro/`：DRO 轨道数据
- `output/ro/`：RO/RRO/ARO 轨道数据
- `output/halo/`：Halo 轨道数据
- `output/transfer/`：转移搜索与优化结果
- `output/ephemeris/`：星历修正结果

## 轨道数据格式

```json
{
  "states": [[x, y, z, vx, vy, vz], ...],
  "times": [t0, t1, ...],
  "period": 6.283,
  "orbit_type": "DRO"
}
```

## Pipeline 顺序

1. 生成基线轨道（DRO, RO）→ JSON 文件至 `output/`
2. 网格搜索出发点和转移参数 → search results JSON
3. NLP 优化可行结果 → optimization results JSON
4. 可视化与分析

## 配置选项

优化脚本 (`optimize_*.py`) 支持以下环境变量：

| 变量 | 说明 |
|------|------|
| `OPTIMIZE_NO_TQDM=1` | 禁用 tqdm 进度条 |
| `OPTIMIZE_BLAS_THREADS_PER_WORKER` | 每 worker BLAS 线程数 |
| `N_WORKERS` | 并行 worker 数 |
| `SEARCH_RESULTS_FILE` | 覆盖搜索结果文件路径 |
| `SPICE_KERNEL_DIR` | SPICE 内核目录 |

## 参考文献

[1] Szebehely V G. Theory of orbit: the restricted problem of three bodies[M]. Place of publication not identified: Academic Press, 1967.

[2] Cui S, Wang Y, Zhang R, et al. Two-impulse transfers from lunar distant retrograde orbits to resonant orbits[J]. Journal Of Guidance, Control, And Dynamics, 2025, 48(6): 1348-1365.
