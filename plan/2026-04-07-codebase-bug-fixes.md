# 代码仓库错误检查与修复

## 目标
系统检查并修复代码仓库中的 bug、逻辑错误和不一致问题。

## 背景
全面代码审查发现多个问题，包括物理计算错误（GEO 球心错误、单位转换错误）、运行时崩溃（缺少 import）、可视化错误（标签错误、周期值错误）等。

## 约束与风险
- 修改常量相关代码需确保不破坏已有输出数据的兼容性
- Halo 轨道相关脚本因 e2m2e API 不确定，修复需谨慎

## 任务列表

- [x] 1. **修复 GEO 球心错误** `scripts/transfer/plot_search_results_geo.py`
  - `_geo_sphere_points` 和 `_plot_single_transfer_orbit` 中 `earth_x` 从 `1.0 - MU` 改为 `-MU`
  - 函数注释中的 `(1-μ, 0)` 改为 `(-μ, 0)`

- [x] 2. **修复速度单位转换错误** `scripts/transfer/plot_search_results_geo.py`
  - 所有 `V_CIRCULAR_GEO * 1000` 改为 `VU * 1000`
  - 添加 `VU` 到 import 列表

- [x] 3. **修复 `_compute_departure_velocity` 丢弃径向速度** `scripts/transfer/plot_optimize_result.py`
  - 重写为径向/切向分解式，与 `geo.py` 和 `plot_search_results.py` 一致

- [x] 4. **修复 `generate_halo_family.py` 多个 bug** `scripts/halo/generate_halo_family.py`
  - 添加 `import sys` 和 `import numpy as np`
  - `seed_halo.states[0, 0]` → `np.asarray(seed_halo.states)[0, 0]`
  - `o.parameters.get()` → `getattr(o, "parameters", {}).get()`

- [x] 5. **修复 `plot_ephemeris_correction.py` IndexError** `scripts/ephemeris/plot_ephemeris_correction.py`
  - glob + `[-1]` 改为直接路径 + `is_file()` 检查

- [x] 6. **修复标签/注释错误**
  - `scripts/plot_single_orbit.py`：所有 "3:1 DRO" → "3:1 RO"
  - `scripts/transfer/plot_search_results.py`："TOOD" → "TODO"
  - `scripts/plot_interactive_orbit_inspector.py`：注释 "3:2 RO" → "3:1 RO"

- [x] 7. **修复 RRO/ARO 绘图 target_period 错误** `scripts/ro/plot_rro_family.py`, `scripts/ro/plot_aro_family.py`
  - `2 * np.pi` → `4 * np.pi`

- [x] 8. **修复硬编码常数** `scripts/dro/generate_31_dro_orbit.py`
  - 添加 `TU` 到 import，`4.348` → `TU`

## 备注
- Issue 27（common.py/params.py 双重定义常数）暂不处理，当前值一致，属于重构范畴
- Issue 11（optimize_dro_geo.py 缓存机制脆弱性）暂不处理，当前流程下不会触发
- Issue 25（PlotConfig 整数字体大小）确认是 e2m2e API 设计，非 bug
- 测试结果：69 passed, 2 skipped，全部通过
