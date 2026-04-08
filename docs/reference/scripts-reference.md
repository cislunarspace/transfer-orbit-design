# 脚本参考

## DRO 轨道脚本

### generate_dro_family.py

使用微分修正和自然延拓生成远距离逆行轨道族。

```bash
python scripts/dro/generate_dro_family.py
```

**输出**：`output/dro/` 中的 JSON 文件

**关键参数**：
- `x0`：初始 x 位置（默认 ~0.7919）
- `vy0`：初始 y 速度（默认 ~0.5368）
- `param_range`：x0 延拓范围（0.6 到 0.8）
- `step_size`：延拓步长（默认 0.005）

### generate_31_dro_orbit.py

生成单个 3:1 DRO 轨道。

```bash
python scripts/dro/generate_31_dro_orbit.py
```

### plot_dro_family.py

绘制带有 Jacobi 常数和稳定性着色的 DRO 族。

```bash
python scripts/dro/plot_dro_family.py
```

**输出**：PNG 图表，显示：
- 整个族的 2D XY 投影
- Jacobi 常数 vs 轨道索引
- 稳定性指数 vs 轨道索引
- 种子轨道的 3D 轨迹

## RO 轨道脚本

### generate_31_ro_orbit.py

生成单个 3:1 共振轨道（固定周期微分修正）。

```bash
python scripts/ro/generate_31_ro_orbit.py
```

**关键参数**：
- `x0`：-0.8805（论文 Table 2）
- `vy0`：0.3921
- 周期：2π ≈ 6.283 TU

### generate_31_ro_family.py

生成 3:1 共振轨道族。

```bash
python scripts/ro/generate_31_ro_family.py
```

**关键参数**：
- `x0_range`：(-1.0, -0.7)
- `period`：2π ≈ 6.283 TU

### generate_32_ro_family.py

生成 3:2 共振轨道族。

```bash
python scripts/ro/generate_32_ro_family.py
```

**关键参数**：
- `x0_range`：(-1.2, -0.8)
- `period`：4π ≈ 12.566 TU

### plot_31_ro_family.py / plot_32_ro_family.py

可视化 RO 轨道族。

```bash
python scripts/ro/plot_31_ro_family.py
python scripts/ro/plot_32_ro_family.py
```

**绘制范围控制**：在脚本顶部设置 `PLOT_START_IDX` 和 `PLOT_END_IDX` 变量，可控制绘制轨道的索引范围。

## 3D 轨道脚本（RRO/ARO）

### generate_rro_family.py

生成反射共振轨道族（RRO）。

```bash
python scripts/ro/generate_rro_family.py
```

### generate_aro_family.py

生成轴向共振轨道族（ARO）。

```bash
python scripts/ro/generate_aro_family.py
```

### plot_rro_family.py / plot_aro_family.py

可视化 3D 轨道族。

```bash
python scripts/ro/plot_rro_family.py
python scripts/ro/plot_aro_family.py
```

## Halo 轨道脚本

### generate_halo_orbit.py

使用 Richardson 三阶近似作为初始猜测，再通过微分修正生成精确的 Halo 周期轨道。

```bash
python scripts/halo/generate_halo_orbit.py
```

**参考文献**：Richardson, D. L. (1980). *Analytic construction of periodic orbits about the collinear points.* Celestial Mechanics.

### generate_halo_family.py

从 Richardson 三阶近似种子轨道出发，使用伪弧长延拓生成 Halo 轨道族。

```bash
python scripts/halo/generate_halo_family.py
```

**关键参数**：
- `DeltaS=0.0045`（正向步长）
- `|DeltaS|=0.009`（负向步长）

### plot_halo_orbit.py

可视化单个 Halo 轨道数据（2D/3D 视图及周期-稳定性参数图）。

```bash
python scripts/halo/plot_halo_orbit.py
```

### plot_halo_family.py

可视化 Halo 轨道族。

```bash
python scripts/halo/plot_halo_family.py <path/to/family.json>
python scripts/halo/plot_halo_family.py --latest
python scripts/halo/plot_halo_family.py --latest --no-show
```

**参数**：
- 位置参数：JSON 文件路径
- `--latest`：自动查找最新的 `halo_*_family_*.json`
- `--no-show`：保存 PNG 而不打开窗口

## 转移设计脚本

### grid_search.py

网格搜索 DRO 到 RO 的可行转移轨迹：

```bash
python scripts/transfer/grid_search.py
```

**搜索变量**：
- `alpha`：切向速度比（0.5 ~ 2.5）
- 出发点位置沿 DRO 轨道分布

**算法**：
1. 遍历网格点
2. 计算出发点状态（v_radial·radial + alpha·v_tangential·tangential）
3. 前向积分轨迹（DOP853, rtol=1e-12, atol=1e-12）
4. 检查是否接近目标 RO
5. 记录可行转移

### optimize.py

优化阶段 - 使用 SQP 求解 NLP 问题：

```bash
python scripts/transfer/optimize.py
```

**决策变量**：$y = \{\alpha, T, t_{ins}\}$
**目标函数**：$J(y) = \Delta v_1 + \Delta v_2$

### plot_search_results.py

可视化转移搜索结果：

```bash
python scripts/transfer/plot_search_results.py <results.json>
```

**参数**：
- 位置参数：网格搜索结果 JSON 文件路径
- `--time-dv`：绘制转移时间 vs delta-v 散点图
- `--orbit`：绘制 3D 转移轨道图
- `--idx <int|best|random|all|best:N>`：选择绘制的可行解
- `--seed <int>`：随机种子（配合 `--idx random`）
- `--max-points <int>`：最大绘制轨道数（配合 `--idx all`）
- `--save <path>`：保存图片而非显示

### plot_optimize_result.py

可视化 NLP 优化结果：

```bash
python scripts/transfer/plot_optimize_result.py
python scripts/transfer/plot_optimize_result.py --orbit
python scripts/transfer/plot_optimize_result.py --orbit --idx best
```

**参数**：
- `--file`：优化结果 JSON 路径（默认自动选择最新）
- `--orbit`：绘制 3D 转移轨道示意图
- `--idx <int|best|best:N|random|all>`：选择结果索引
- `--save <path>`：保存图片

### grid_search_dro_geo.py

网格搜索 DRO 到 GEO 的可行转移轨迹：

```bash
python scripts/transfer/grid_search_dro_geo.py
```

与 `grid_search.py` 类似，但目标为 GEO 球面而非 RO 轨道。使用 `GeoTransferSearch` 检测 GEO 球面穿越。

### optimize_dro_geo.py

优化 DRO→GEO 转移轨道：

```bash
python scripts/transfer/optimize_dro_geo.py
```

### plot_search_results_geo.py

可视化 DRO→GEO 搜索结果：

```bash
python scripts/transfer/plot_search_results_geo.py
python scripts/transfer/plot_search_results_geo.py --orbit
python scripts/transfer/plot_search_results_geo.py --interactive
```

**参数**：与 `plot_search_results.py` 类似，额外支持 `--interactive` 交互式浏览模式。

## 星历修正脚本

### correct_dro_to_ephemeris.py

使用多重打靶法将 CR3BP DRO 修正为星历模型下的轨道：

```bash
python scripts/ephemeris/correct_dro_to_ephemeris.py
```

需要 SPICE 内核文件（`de440.bsp`, `naif0012.tls`）。

### homotopy_dro_to_ephemeris.py

使用同伦 λ-延拓方法将 CR3BP DRO 修正为星历模型下的轨道：

```bash
python scripts/ephemeris/homotopy_dro_to_ephemeris.py
```

### compare_ephemeris_methods.py

对比多重打靶法和同伦法的修正效果：

```bash
python scripts/ephemeris/compare_ephemeris_methods.py
```

### plot_ephemeris_correction.py

可视化星历修正前后对比（会合坐标系 + J2000 惯性系）：

```bash
python scripts/ephemeris/plot_ephemeris_correction.py
```

## 通用工具脚本

### plot_single_orbit.py

加载并绘制单个 `Orbit` 对象的 2D 和 3D 视图。

```bash
python scripts/plot_single_orbit.py
```

在脚本顶部配置 `orbit_filename` 和 `output_dir`。

### plot_interactive_orbit_inspector.py

交互式轨道逐条检查工具，用于调试和质量检查。

```bash
python scripts/plot_interactive_orbit_inspector.py
```

**交互操作**：
- `Enter`：绘制下一条轨道
- `q`：退出
- `s`：跳过 N 条轨道
- `j`：跳转到指定索引

### utils/params.py

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

### utils/common.py

共享常数（MU, DU, TU, VU, T_MOON）和文件辅助函数：
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
- `compute_departure_velocity()`：切向速度缩放（径向/切向分解）
- `check_collision()`：碰撞检测
