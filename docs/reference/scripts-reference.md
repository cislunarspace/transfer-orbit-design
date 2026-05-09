---
sidebar_position: 4
---

# 脚本参考

## DRO 轨道脚本

### generate_dro_family.py

使用微分修正和自然延拓生成远距离逆行轨道族。

```bash
uv run python -m tod.pipelines.dro.generate.generate_dro_family
```

**输出**：`output/dro/` 中的 JSON 文件

**关键参数**：
- `--x0`：种子轨道初始 x 坐标（默认 0.79188556619742）
- `--vy0`：初始 y 速度（默认 0.53682）
- `--period`：初始周期猜测（默认 3.472526005624708）
- `--param-min` / `--param-max`：延拓参数范围（默认 0.141886 ~ 0.9）
- `--step-size`：延拓步长（默认 0.005）

### generate_31_dro_orbit.py

生成单个 3:1 DRO 轨道。

```bash
uv run python -m tod.pipelines.dro.generate.generate_31_dro_orbit
```

**关键参数**：
- `--x0`：初始 x 坐标（默认 1.1202）
- `--vy0`：初始 vy 速度（默认 -0.4618）
- `--period`：目标周期（默认 2.095）

### plot_dro_family.py

绘制带有 Jacobi 常数和稳定性着色的 DRO 族。

```bash
uv run python -m tod.pipelines.dro.plot.plot_dro_family
```

**关键参数**：
- `--json-file`：轨道族 JSON 文件路径

**输出**：PNG 图表，显示 2D XY 投影、Jacobi 常数、稳定性指数、种子轨道 3D 轨迹

## RO 轨道脚本

### generate_31_ro_orbit.py

生成单个 3:1 共振轨道（固定周期微分修正）。

```bash
uv run python -m tod.pipelines.ro.generate.generate_31_ro_orbit
```

**关键参数**：
- `--x0`（默认 -0.8805）、`--vy0`（默认 0.3921）、`--period`

### generate_31_ro_family.py

生成 3:1 共振轨道族。

```bash
uv run python -m tod.pipelines.ro.generate.generate_31_ro_family
```

**关键参数**：
- `--x0`（默认 -0.8805）、`--vy0`（默认 0.3921）、`--period`
- `--param-min` / `--param-max`：延拓范围（默认 -0.8905 ~ -0.8305）
- `--step-size`（默认 0.001）

### generate_32_ro_family.py

生成 3:2 共振轨道族。

```bash
uv run python -m tod.pipelines.ro.generate.generate_32_ro_family
```

**关键参数**：
- `--x0`（默认 -1.1453）、`--vy0`（默认 0.4633）、`--period`
- `--param-min` / `--param-max`（默认 -1.2 ~ -0.8）
- `--step-size`（默认 0.005）

### plot_31_ro_family.py / plot_32_ro_family.py

可视化 RO 轨道族。

```bash
uv run python -m tod.pipelines.ro.plot.plot_31_ro_family [--json-file path] [--start N] [--end N]
uv run python -m tod.pipelines.ro.plot.plot_32_ro_family [--json-file path] [--start N] [--end N]
```

## 3D 轨道脚本（RRO/ARO）

### generate_rro_family.py

生成反射共振轨道族（RRO），从 3:2 RO 分岔。

```bash
uv run python -m tod.pipelines.ro.generate.generate_rro_family --ro-file <path> --target-x0 -1.1318
```

**关键参数**：
- `--ro-file`：3:2 RO 轨道 JSON 文件路径
- `--target-x0`：分岔点 x0（默认 -1.1318）
- `--z-max`：最大 z 幅值（默认 0.5）
- `--step-size`（默认 0.01）

### generate_aro_family.py

生成轴向共振轨道族（ARO），从 3:2 RO 分岔。

```bash
uv run python -m tod.pipelines.ro.generate.generate_aro_family --ro-file <path> --target-x0 -1.0878
```

**关键参数**：
- `--ro-file`：3:2 RO 轨道 JSON 文件路径
- `--target-x0`：分岔点 x0（默认 -1.0878）
- `--z0`：固定 z0（默认 0.1999）
- `--vy0`、`--period`：初始猜测
- `--x-min` / `--x-max`：延拓范围（默认 -1.2 ~ -0.9）

### plot_rro_family.py / plot_aro_family.py

可视化 3D 轨道族。

```bash
uv run python -m tod.pipelines.ro.plot.plot_rro_family [--json-file path] [--start N] [--end N]
uv run python -m tod.pipelines.ro.plot.plot_aro_family [--json-file path] [--start N] [--end N]
```

## Halo 轨道脚本

### generate_halo_orbit.py

使用 Richardson 三阶近似作为初始猜测，再通过微分修正生成精确的 Halo 周期轨道。

```bash
uv run python -m tod.pipelines.halo.generate.generate_halo_orbit [--libration-point 1] [--amplitude-z 0.23] [--halo-class 0]
```

**关键参数**：
- `--libration-point`：平动点（1=L1, 2=L2）
- `--amplitude-z`：Z 方向振幅（无量纲）
- `--halo-class`：0=北 Halo, 1=南 Halo
- `--period`、`--x0`、`--vy0`：初始猜测
- `--max-iterations`（默认 150）、`--tolerance`（默认 1e-6）

### generate_halo_family.py

从 Richardson 三阶近似种子轨道出发，使用伪弧长延拓生成 Halo 轨道族。

```bash
uv run python -m tod.pipelines.halo.generate.generate_halo_family [--libration-point 1] [--amplitude-z 0.23]
```

**关键参数**：
- `--n-orbits`：延拓轨道数量（默认 20）
- `--step-size`：正向步长（默认 0.0045）
- `--step-size-negative`：负向步长（默认 0.009）

### plot_halo_orbit.py

可视化单个 Halo 轨道数据（2D/3D 视图及周期-稳定性参数图）。

```bash
uv run python -m tod.pipelines.halo.plot.plot_halo_orbit [--json-file path] [--start N] [--end N]
```

### plot_halo_family.py

可视化 Halo 轨道族。

```bash
uv run python -m tod.pipelines.halo.plot.plot_halo_family <path/to/family.json>
uv run python -m tod.pipelines.halo.plot.plot_halo_family --latest
uv run python -m tod.pipelines.halo.plot.plot_halo_family --latest --no-show
```

**参数**：
- 位置参数：JSON 文件路径
- `--latest`：自动查找最新的 `halo_*_family_*.json`
- `--no-show`：保存 PNG 而不打开窗口
- `--start` / `--end`：轨道索引范围

## 转移设计脚本

### DRO→RO 转移

#### grid_search_dro_to_ro.py

网格搜索 DRO 到 RO 的可行转移轨迹：

```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.grid_search_dro_to_ro [--dro-file path] [--ro-file path]
```

**搜索变量**：出发点位置、切向速度比 alpha（0.5 ~ 2.5）

**关键参数**：
- `--dro-file` / `--ro-file`：轨道文件路径（GUI 也支持通过环境变量 `DRO_FILE` / `RO_FILE` 传入）
- `--n-departure`（默认 200）、`--n-alpha`（默认 100）
- `--alpha-min` / `--alpha-max`：alpha 搜索范围
- `--max-transfer-time`：最大转移时间
- `--intersection-threshold`、`--min-distance`、`--earth-radius`、`--moon-radius`

#### optimize_dro_to_ro.py

对网格搜索结果进行 NLP 优化（SLSQP 最小化总 Δv）：

```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.optimize_dro_to_ro --search-file <path> --dro-file <path> --ro-file <path>
```

**决策变量**：`y = {α, T, t_ins}`，**目标函数**：`J(y) = Δv₁ + Δv₂`

**关键参数**：
- `--search-file`：网格搜索结果 JSON
- `--nlp-maxiter`（默认 100）、`--nlp-ftol`（默认 1e-8）
- `--top-k`、`--max-cases`、`--n-workers`：并行控制
- `--velocity-angle-tol`：速度方向容差（默认 0.05 弧度）

### DRO→GEO 转移

#### grid_search_dro_to_geo.py

网格搜索 DRO 到 GEO 的可行转移轨迹，目标为 GEO 球面而非 RO 轨道：

```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.grid_search_dro_to_geo [--dro-file path]
```

**关键参数**：
- `--geo-threshold`：GEO 相交距离阈值
- 其他参数与 `grid_search_dro_to_ro.py` 类似

#### optimize_dro_to_geo.py

优化 DRO→GEO 转移轨道：

```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.optimize_dro_to_geo --search-file <path> --dro-file <path>
```

**关键参数**：
- `--t-min` / `--t-max`：转移时间范围（默认 0.5 ~ 30.0）
- 其他 NLP 参数与 `optimize_dro_to_ro.py` 类似

### GEO→DRO 转移

#### grid_search_geo_to_dro.py

从 GEO 出发搜索到 DRO 的可行转移轨迹：

```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.grid_search_geo_to_dro [--dro-file path]
```

**关键参数**：
- `--n-departure`：GEO 出发点数（默认 10）
- `--n-alpha`（默认 200）、`--alpha-min`（默认 1.0）、`--alpha-max`（默认 1.5）
- `--max-transfer-time`（默认约 28.72）
- `--geo-n-points`：GEO 轨道采样点数（默认 1000）

#### optimize_geo_to_dro.py

GEO→DRO 转移 NLP 优化：

```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.optimize_geo_to_dro --search-file <path> --dro-file <path>
```

**关键参数**：
- `--t-min` / `--t-max`（默认 5.0 ~ 60.0）
- `--t-ins-min` / `--t-ins-max`：DRO 插入时间范围（默认 0.0 ~ 10.0）
- `--velocity-angle-tol`：速度平行性容差（度）

#### validate_geo_to_dro.py

验证 GEO→DRO 转移轨道搜索可行性（调试用）：

```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.validate_geo_to_dro
```

### LEO→DRO 转移

#### grid_search_leo_to_dro.py

从 LEO 出发搜索到 DRO 的可行转移轨迹：

```bash
uv run python -m tod.pipelines.transfer.leo_to_dro.grid_search_leo_to_dro [--dro-file path]
```

**关键参数**：
- `--alpha-min`（默认 1.2）、`--alpha-max`（默认 2.0）
- `--max-transfer-time`（默认 80.0）
- `--leo-n-points`：LEO 轨道采样点数（默认 500）

#### optimize_leo_to_dro.py

LEO→DRO 转移 NLP 优化：

```bash
uv run python -m tod.pipelines.transfer.leo_to_dro.optimize_leo_to_dro --search-file <path> --dro-file <path>
```

**关键参数**：与 `optimize_geo_to_dro.py` 类似，`--t-max` 默认 80.0

### 可视化脚本

#### plot_search_results_dro_to_ro.py

可视化 DRO-RO 网格搜索结果：

```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_search_results_dro_to_ro <results.json> [--orbit] [--time-dv] [--idx N]
```

**参数**：
- `--orbit`：绘制 3D 转移轨道图
- `--time-dv`：绘制转移时间 vs Δv 散点图
- `--idx <int|best|random|all|best:N>`：选择绘制的可行解
- `--max-points`（默认 50000）、`--seed`、`--save`、`--n-workers`

#### plot_search_results_dro_to_geo.py

可视化 DRO-GEO 网格搜索结果（参数同上，额外支持 `--interactive` 交互式浏览）。

```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo <results.json> [--orbit] [--time-dv] [--idx N]
```

#### plot_search_results_geo_to_dro.py

可视化 GEO-DRO 网格搜索结果：

```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_search_results_geo_to_dro [--time-dv] [--orbit] [--interactive] [--idx best:10]
```

#### plot_optimize_result_dro_to_ro.py

可视化 DRO-RO NLP 优化结果：

```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_optimize_result_dro_to_ro [--orbit] [--time-dv] [--idx best]
```

#### plot_optimize_result_geo_to_dro.py

可视化 GEO-DRO NLP 优化结果：

```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro [--orbit] [--time-dv] [--interactive] [--idx best:5]
```

**特有参数**：`--max-pos-err`（最大位置误差 km，默认 100.0）

## 星历修正脚本

### correct_dro_to_ephemeris.py

使用多重打靶法将 CR3BP DRO 修正为星历模型下的轨道：

```bash
uv run python -m tod.pipelines.ephemeris.correct.correct_dro_to_ephemeris [--dro-file path]
```

需要 SPICE 内核文件（`de440.bsp`, `naif0012.tls`）。设置 `SPICE_KERNEL_DIR` 环境变量或默认使用 `../e2m2e/kernels/`。

### homotopy_dro_to_ephemeris.py

使用同伦 λ-延拓方法将 CR3BP DRO 修正为星历模型下的轨道：

```bash
uv run python -m tod.pipelines.ephemeris.correct.homotopy_dro_to_ephemeris [--dro-file path]
```

### compare_ephemeris_methods.py

对比多重打靶法和同伦法的修正效果：

```bash
uv run python -m tod.pipelines.ephemeris.compare.compare_ephemeris_methods
```

### plot_ephemeris_correction.py

可视化星历修正前后对比（会合坐标系 + J2000 惯性系）：

```bash
uv run python -m tod.pipelines.ephemeris.plot.plot_ephemeris_correction [--dro-file path] [--ephemeris-file path]
```

## 轨道检查脚本

### plot_single_orbit.py

加载并绘制单个 `Orbit` 对象的 2D 和 3D 视图。

```bash
uv run python -m tod.pipelines.inspection.plot_single_orbit --json-file <path>
```

### plot_interactive_orbit_inspector.py

交互式轨道逐条检查工具，用于调试和质量检查。

```bash
uv run python -m tod.pipelines.inspection.plot_interactive_orbit_inspector --json-file <path> [--plane xy] [--show-3d]
```

**交互操作**：
- `Enter`：绘制下一条轨道
- `q`：退出
- `s`：跳过 N 条轨道
- `j`：跳转到指定索引

## GUI

### main.py

PyQt6 桌面应用，用于浏览和运行脚本。支持按模块分组（DRO、RO、Halo、Transfer、Ephemeris、Inspection），可同时运行多个脚本并显示结构化输出。

```bash
python -m tod.pipelines.gui.main
```

**功能**：
- 带参数控件的脚本运行（`env_params` 文件下拉框、`cli_params` 输入框）
- 多任务并行执行（每个任务独立 JobCard）
- ANSI 输出解析、stderr 高亮、时间戳

## 工具模块

### utils/constants.py

物理常数（归一化单位）：

| 常数 | 值 | 说明 |
|------|-----|------|
| MU | 1.21506683e-2 | 地月质量比（无量纲） |
| M_SUN | 3.28900541e5 | 太阳质量比（无量纲，BR4BP） |
| OMEGA_SUN | 9.25195985e-1 | 太阳角速度（无量纲，BR4BP） |
| RHO | 3.88811143e2 | 太阳距离比（无量纲，BR4BP） |
| DU | 3.84405e5 | 距离单位 (km) |
| TU | 4.34811305 | 时间单位 (天) |
| VU | 1023.23281 | 速度单位 (m/s) |
| T_MOON | 2π | 月球轨道周期 (TU) |
| FAMILY_FILENAME | "family.json" | 标准轨道族文件名 |

### utils/common.py

共享常数（从 constants.py re-export）和文件辅助函数：
- `ensure_output_dir()`：创建输出目录
- `get_latest_family_file()`：查找最新的输出文件
- `load_or_compute()`：加载已有文件或重新计算
- `save_family_to_file()`：保存轨道族数据

### utils/geo.py

GEO 轨道工具（DRO→GEO 转移用）：
- `R_GEO`：GEO 轨道半径（归一化）
- `V_CIRCULAR_GEO`：GEO 圆轨道速度（归一化）
- `EARTH_CENTER`：地心坐标 `(-MU, 0, 0)`
- `geo_circular_velocity_rotating()`：计算旋转系下 GEO 圆轨道速度
- `detect_geo_sphere_crossing()`：检测轨迹 GEO 球面穿越
- `find_closest_approach_to_geo()`：找最接近 GEO 的点
- `compute_geo_dv2()`：计算 GEO 插入 delta-v
- `compute_departure_velocity()`：切向速度缩放
- `check_collision()`：碰撞检测

### utils/leo.py

LEO 轨道工具（LEO→DRO 转移用）：
- `R_LEO`：LEO 轨道半径（归一化）
- `V_CIRCULAR_LEO`：LEO 圆轨道速度（归一化）
