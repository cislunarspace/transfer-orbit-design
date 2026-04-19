# Transfer Orbit Design — DRO to RO Two-Impulse Transfer

## 项目概述

本项目旨在复现以下论文的研究成果：

> **Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits**  
> Shuhao Cui, Yue Wang, Ruikang Zhang, Hao Zhang, Yang Gao  
> *Journal of Guidance, Control, and Dynamics*, Vol. 48, No. 6, June 2025  
> DOI: [10.2514/1.G008582](https://doi.org/10.2514/1.G008582)

## 环境配置（克隆后必做）

在仓库根目录执行一次（Windows / Linux / macOS 相同）：

```bash
uv sync
```

`requirements.txt` 末尾的 `-e .` 会把本仓库以**可编辑包**形式安装，使任意工作目录下运行脚本时 `from scripts.utils...` 都能正确导入，无需再改 `PYTHONPATH` 或 `sys.path`。

随后按注释安装本地依赖库 **e2m2e**（例如 `pip install -e /path/to/e2m2e`）。

## 使用方法

### 生成 DRO/RO 轨道

首次使用需先安装依赖：

```bash
uv sync
pip install -e /path/to/e2m2e  # 本地 e2m2e 依赖库
```

生成单个 3:1 DRO 轨道：

```bash
uv run python scripts/dro/generate_31_dro_orbit.py
```

输出示例：
```
目标 轨 道 : 3:1 DRO
初 始 状 态 : x0=1.1202, vy0=-0.4618
目标 周 期 : 2.0950 TU (9.11 days)
...
[ok] 成 功 找 到  3:1 DRO 轨 道 !
  保 存 至 : output/dro/dro_31_3857117998.json
```

生成 DRO 族、RO 族：

```bash
uv run python scripts/dro/generate_dro_family.py
uv run python scripts/ro/generate_31_ro_family.py
uv run python scripts/ro/generate_32_ro_family.py
```

该论文研究了地月系统中从远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移轨道设计问题。由于 DRO 和 RO 均为稳定轨道，无法利用不稳定流形结构，论文提出了一种"搜索-优化"两步法来设计转移轨道，并在 CR3BP、BR4BP 和星历模型中分别进行了计算与验证。

## 快速开始

### 环境要求

```bash
# Python环境: orbit-py313 (conda)
conda create -n orbit-py313 python=3.13
conda activate orbit-py313

# 安装依赖
uv sync
pip install -e /path/to/e2m2e  # 本地 e2m2e 依赖库
```

### 执行网格搜索

```bash
# 1. 准备轨道数据文件 (JSON格式)
#    - 3:1 DRO: output/dro/dro_31_*.json
#    - 3:1 RO: output/ro/ro_31_*.json

# 2. 执行网格搜索 (使用论文Table 3参数)
uv run python scripts/transfer/grid_search_dro_to_ro.py

# 输出: output/transfer/search_results_*.json
```

### NLP 优化阶段

```bash
# 对网格搜索结果进行 NLP 优化
uv run python scripts/transfer/optimize_dro_to_ro.py

# 输出: output/transfer/optimization_results_*.json
```

### 可视化搜索结果

```bash
# 可视化网格搜索结果（散点图、转移轨迹）
uv run python scripts/transfer/plot_search_results.py <results.json>

# 可选参数：
#   --time-dv     绘制转移时间 vs delta-v 散点图
#   --orbit       绘制 3D 转移轨道图
#   --idx <N>     指定绘制第 N 个可行解（best/random/all/best:N）
#   --save <path> 保存图片而非显示
```

### 轨道数据格式

```json
{
  "states": [[x, y, z, vx, vy, vz], ...],
  "times": [t0, t1, ...],
  "period": 6.283,
  "orbit_type": "DRO"
}
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

## 当前代码架构

核心算法代码位于 `e2m2e` 项目中，`transfer-orbit-design/scripts/` 包含各阶段的任务脚本。

### e2m2e 核心库（`e2m2e/e2m2e/`）

```
e2m2e/
├── algorithms/          # 算法模块
│   ├── continuation.py          # 自然参数延拓 / 伪弧长延拓
│   ├── differential_correction.py  # 微分修正算法
│   └── stability.py             # 单值矩阵特征值分析
├── core/               # 核心模块
│   ├── dynamics.py               # CR3BP/BR4BP 动力学
│   ├── orbit.py                  # Orbit / OrbitFamily 数据结构
│   └── system.py                 # CR3BP 系统参数管理
├── transfer/           # 转移轨道设计
│   ├── transfer_base.py          # 转移基类
│   ├── transfer_optimization.py  # NLP 优化器
│   └── transfer_search.py        # 网格搜索
└── visualization/      # 可视化
    ├── config.py               # PlotConfig 绘图配置
    ├── base.py                 # BasePlotter 基类
    ├── family.py               # FamilyPlotter 轨道族绘图
    ├── transfer.py             # TransferPlotter 转移绘图
    ├── stability.py            # 稳定性可视化
    └── plotting.py             # 向后兼容 shim
```

### transfer-orbit-design 任务脚本（`scripts/`）

| 脚本 | 功能 |
|------|------|
| **DRO 轨道** | |
| `dro/generate_dro_family.py` | 生成 DRO 族 |
| `dro/generate_31_dro_orbit.py` | 生成单个 3:1 DRO |
| `dro/plot_dro_family.py` | DRO 族可视化 |
| **RO 轨道** | |
| `ro/generate_31_ro_orbit.py` | 生成单个 3:1 RO |
| `ro/generate_31_ro_family.py` | 生成 3:1 RO 族 |
| `ro/generate_32_ro_family.py` | 生成 3:2 RO 族 |
| `ro/plot_31_ro_family.py` | 3:1 RO 族可视化 |
| `ro/plot_32_ro_family.py` | 3:2 RO 族可视化 |
| **3D 轨道（RRO/ARO）** | |
| `ro/generate_rro_family.py` | 生成 RRO 族 |
| `ro/generate_aro_family.py` | 生成 ARO 族 |
| `ro/plot_rro_family.py` | RRO 族可视化 |
| `ro/plot_aro_family.py` | ARO 族可视化 |
| **Halo 轨道** | |
| `halo/generate_halo_orbit.py` | 生成单个 Halo 轨道（Richardson 三阶近似 + 微分修正） |
| `halo/generate_halo_family.py` | 生成 Halo 轨道族（伪弧长延拓） |
| `halo/plot_halo_orbit.py` | 单个 Halo 轨道可视化 |
| `halo/plot_halo_family.py` | Halo 轨道族可视化 |
| **转移设计** | |
| `transfer/grid_search_dro_to_ro.py` | 网格搜索 DRO→RO 转移轨道 |
| `transfer/optimize_dro_to_ro.py` | DRO→RO NLP 优化 |
| `transfer/plot_search_results.py` | DRO→RO 搜索结果可视化 |
| `transfer/plot_optimize_result.py` | DRO→RO 优化结果可视化 |
| `transfer/grid_search_dro_to_geo.py` | 网格搜索 DRO→GEO 转移轨道 |
| `transfer/optimize_dro_to_geo.py` | DRO→GEO NLP 优化 |
| `transfer/plot_search_results_geo.py` | DRO→GEO 搜索结果可视化 |
| `transfer/grid_search_geo_to_dro.py` | 网格搜索 GEO→DRO 转移轨道 |
| `transfer/optimize_geo_to_dro.py` | GEO→DRO NLP 优化 |
| `transfer/plot_search_results_geo_to_dro.py` | GEO→DRO 搜索结果可视化 |
| `transfer/plot_optimize_result_geo_to_dro.py` | GEO→DRO 优化结果可视化 |
| `transfer/grid_search_leo_to_dro.py` | 网格搜索 LEO→DRO 转移轨道 |
| `transfer/optimize_leo_to_dro.py` | LEO→DRO NLP 优化 |
| `transfer/validate_geo_to_dro.py` | 验证 GEO→DRO 搜索可行性 |
| **星历修正** | |
| `ephemeris/correct_dro_to_ephemeris.py` | 多重打靶法星历修正 |
| `ephemeris/homotopy_dro_to_ephemeris.py` | 同伦法星历修正 |
| `ephemeris/compare_ephemeris_methods.py` | 修正方法对比 |
| `ephemeris/plot_ephemeris_correction.py` | 星历修正可视化 |
| **轨道检查** | |
| `inspection/plot_single_orbit.py` | 单轨道可视化（2D/3D） |
| `inspection/plot_interactive_orbit_inspector.py` | 交互式轨道逐条检查 |
| **GUI** | |
| `gui/main.py` | PyQt6 桌面应用（浏览和运行脚本） |

### 输出目录

- `output/dro/`：DRO 轨道数据
- `output/ro/`：RO/RRO/ARO 轨道数据
- `output/halo/`：Halo 轨道数据
- `output/transfer/`：转移搜索与优化结果
- `output/ephemeris/`：星历修正结果

## 参考文献

[1] Szebehely V G. Theory of orbit: the restricted problem of three bodies[M]. Place of publication not identified: Academic Press, 1967.

[2] Cui S, Wang Y, Zhang R, et al. Two-impulse transfers from lunar distant retrograde orbits to resonant orbits[J]. Journal Of Guidance, Control, And Dynamics, 2025, 48(6): 1348-1365.
