---
sidebar_position: 4
---

# 脚本参数速查

共 36 个脚本，按 GUI 标签页分组。

## DRO

### 生成

**generate_31_dro_orbit** — 单个 3:1 DRO
```bash
uv run python -m tod.pipelines.dro.generate.generate_31_dro_orbit --x0 1.1202 --vy0 -0.4618 --period 2.095
```

**generate_dro_family** — DRO 轨道族（微分修正 + 自然延拓）
```bash
uv run python -m tod.pipelines.dro.generate.generate_dro_family --x0 0.7919 --vy0 0.5368 --period 3.4725 --param-min 0.6 --param-max 0.8 --step-size 0.005
```

### 绘图

**plot_dro_family** — 绘制 DRO 轨道族
```bash
uv run python -m tod.pipelines.dro.plot.plot_dro_family --json-file <path>
```

## RO

### 生成

**generate_31_ro_orbit** — 单个 3:1 RO
```bash
uv run python -m tod.pipelines.ro.generate.generate_31_ro_orbit --x0 -0.8805 --vy0 0.3921 --period 6.2832
```

**generate_31_ro_family** — 3:1 RO 族
```bash
uv run python -m tod.pipelines.ro.generate.generate_31_ro_family --x0 -0.8805 --vy0 0.3921 --period 6.2832 --param-min -0.8905 --param-max -0.8305 --step-size 0.001
```

**generate_32_ro_family** — 3:2 RO 族
```bash
uv run python -m tod.pipelines.ro.generate.generate_32_ro_family --x0 -1.1453 --vy0 0.4633 --period 12.566 --param-min -1.2 --param-max -0.8 --step-size 0.005
```

**generate_rro_family** — RRO 反射共振轨道族（从 3:2 RO 分岔）
```bash
uv run python -m tod.pipelines.ro.generate.generate_rro_family --ro-file <path> --target-x0 -1.1318 --z-max 0.5 --step-size 0.01
```

**generate_aro_family** — ARO 轴向共振轨道族（从 3:2 RO 分岔）
```bash
uv run python -m tod.pipelines.ro.generate.generate_aro_family --ro-file <path> --target-x0 -1.0878 --z0 0.1999 --vy0 0.4 --period 60.0 --x-min -1.2 --x-max -0.9 --step-size 0.005
```

### 绘图

**plot_31_ro_family** — 绘制 3:1 RO 族
```bash
uv run python -m tod.pipelines.ro.plot.plot_31_ro_family --json-file <path> --start -1 --end -1
```

**plot_32_ro_family** — 绘制 3:2 RO 族
```bash
uv run python -m tod.pipelines.ro.plot.plot_32_ro_family --json-file <path> --start -1 --end 42
```

**plot_rro_family** — 绘制 RRO 族
```bash
uv run python -m tod.pipelines.ro.plot.plot_rro_family --json-file <path> --start -1 --end -1
```

**plot_aro_family** — 绘制 ARO 族
```bash
uv run python -m tod.pipelines.ro.plot.plot_aro_family --json-file <path> --start -1 --end -1
```

## Halo

### 生成

**generate_halo_orbit** — 单个 Halo 轨道
```bash
uv run python -m tod.pipelines.halo.generate.generate_halo_orbit --libration-point L1 --amplitude-z 0.23 --halo-class 北族
```

**generate_halo_family** — Halo 轨道族（伪弧长延拓）
```bash
uv run python -m tod.pipelines.halo.generate.generate_halo_family --libration-point L1 --halo-class 北族 --amplitude-z 0.23 --n-orbits 20
```

### 绘图

**plot_halo_family** — 绘制 Halo 轨道族
```bash
uv run python -m tod.pipelines.halo.plot.plot_halo_family --latest
```

**plot_halo_orbit** — 绘制 Halo 轨道（含 Jacobi/稳定性分析）
```bash
uv run python -m tod.pipelines.halo.plot.plot_halo_orbit --json-file <path> --start -1 --end -1
```

## Transfer

### DRO → RO

**grid_search_dro_to_ro** — 网格搜索
```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.grid_search_dro_to_ro --dro-file <path> --ro-file <path>
```

**optimize_dro_to_ro** — NLP 优化
```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.optimize_dro_to_ro --search-file <path> --dro-file <path> --ro-file <path>
```

**plot_search_results_dro_to_ro** — 可视化搜索结果
```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_search_results_dro_to_ro --file <path> --time-dv --orbit
```

**plot_optimize_result_dro_to_ro** — 可视化优化结果
```bash
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_optimize_result_dro_to_ro --file <path> --orbit --idx best
```

### DRO → GEO

**grid_search_dro_to_geo** — 网格搜索
```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.grid_search_dro_to_geo --dro-file <path>
```

**optimize_dro_to_geo** — NLP 优化
```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.optimize_dro_to_geo --search-file <path> --dro-file <path>
```

**plot_search_results_dro_to_geo** — 可视化搜索结果
```bash
uv run python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --file <path> --time-dv --orbit
```

### GEO → DRO

**grid_search_geo_to_dro** — 网格搜索
```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.grid_search_geo_to_dro --dro-file <path>
```

**optimize_geo_to_dro** — NLP 优化
```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.optimize_geo_to_dro --search-file <path> --dro-file <path>
```

**plot_search_results_geo_to_dro** — 可视化搜索结果
```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_search_results_geo_to_dro --file <path> --time-dv --orbit
```

**plot_optimize_result_geo_to_dro** — 可视化优化结果
```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --file <path> --orbit --idx best:5
```

**validate_geo_to_dro** — 验证搜索可行性
```bash
uv run python -m tod.pipelines.transfer.geo_to_dro.validate_geo_to_dro
```

### LEO → DRO

**grid_search_leo_to_dro** — 网格搜索
```bash
uv run python -m tod.pipelines.transfer.leo_to_dro.grid_search_leo_to_dro --dro-file <path>
```

**optimize_leo_to_dro** — NLP 优化
```bash
uv run python -m tod.pipelines.transfer.leo_to_dro.optimize_leo_to_dro --search-file <path> --dro-file <path>
```

## Ephemeris

星历修正脚本需要 SPICE 内核（`de440.bsp`、`naif0012.tls`），设置 `SPICE_KERNEL_DIR` 或放在 `e2m2e/kernels/`。

**correct_dro_to_ephemeris** — 多重打靶法（环境变量：`DRO_FILE`）
```bash
uv run python -m tod.pipelines.ephemeris.correct.correct_dro_to_ephemeris
```

**homotopy_dro_to_ephemeris** — 同伦 λ 延拓法（环境变量：`DRO_FILE`）
```bash
uv run python -m tod.pipelines.ephemeris.correct.homotopy_dro_to_ephemeris
```

**compare_ephemeris_methods** — 方法对比
```bash
uv run python -m tod.pipelines.ephemeris.compare.compare_ephemeris_methods
```

**plot_ephemeris_correction** — 绘制修正前后对比
```bash
uv run python -m tod.pipelines.ephemeris.plot.plot_ephemeris_correction --dro-file <path> --ephemeris-file <path>
```

## Inspection

**plot_interactive_orbit_inspector** — 交互式轨道检查器
```bash
uv run python -m tod.pipelines.inspection.plot_interactive_orbit_inspector --json-file <path> --plane xy --show-3d
```

**plot_single_orbit** — 单轨道绘图
```bash
uv run python -m tod.pipelines.inspection.plot_single_orbit --json-file <path>
```

## 共用参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `--json-file` | str | 轨道 JSON 文件路径（GUI 下拉自动发现） |
| `--file` | str | 搜索/优化结果 JSON 文件路径 |
| `--dro-file` / `--ro-file` | str | 基线轨道 JSON 文件路径 |
| `--idx` | str | `best` / `best:N` / `all` / `random` / 整数索引 |
| `--orbit` | bool | 是否绘制 3D 转移轨道图 |
| `--time-dv` | bool | 是否绘制转移时间 vs Δv 散点图 |
| `--save` | str | 图片保存路径（不填则弹窗显示） |
| `--start` / `--end` | int | 轨道索引范围，-1 表示从头/到尾 |
| `--n-workers` | int | 并行 worker 数（影响运行速度） |
| `--nlp-ftol` | float | NLP 收敛容差（默认 1e-8） |
| `--nlp-maxiter` | int | NLP 最大迭代次数（默认 100） |
