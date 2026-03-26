# Grid Search 实现计划

**Author**: AI Assistant  
**Date**: 2026-03-25  
**Last updated**: 2026-03-26  
**Status**: **已完成**（脚本与 e2m2e 集成已落地；大规模运行与参数扫描由使用者按需执行）  
**Target**: `scripts/transfer/grid_search.py`、`e2m2e.transfer.DROTransferSearch`

---

## 1. 设计原则

参照 `algorithms/continuation.py` 的风格：

- **不使用独立的配置类**（如 `SearchConfig` dataclass）
- **直接在实例上设置属性**：`transfer_search.alpha_min = 0.5`
- 搜索参数作为 `DROTransferSearch` 实例的属性

---

## 2. 实现方式

### 2.1 搜索参数设置（直接在实例上赋值）

```python
transfer_search = DROTransferSearch(system=system, dynamics=dynamics)

transfer_search.alpha_min = 0.5
transfer_search.alpha_max = 2.5
transfer_search.n_alpha = 101
transfer_search.n_departure = 200
transfer_search.max_transfer_time = 200.0 / TU  # 与 grid_search 中无量纲 TU 一致
transfer_search.intersection_threshold = 0.001
transfer_search.min_distance_threshold = 100.0 / DU
transfer_search.collision_earth_radius = 200 / DU
transfer_search.collision_moon_radius = 100 / DU
transfer_search.integration_dt = 1.0 / (24.0 * TU)
```

具体数值以仓库内 `scripts/transfer/grid_search.py` 为准。

### 2.2 e2m2e 侧

`e2m2e/transfer/transfer_search.py` 中 `DROTransferSearch` 支持：

- 实例属性配置与 `search(n_workers=..., parallel_backend="processes"|"threads")` 并行网格搜索。

---

## 3. 当前状态

### 3.1 已完成

- ✅ e2m2e `DROTransferSearch` 支持直接属性赋值与多进程/多线程并行
- ✅ `grid_search.py` 使用上述 API，写出 `output/transfer/search_results_{nDep}-{nAlpha}-...json`
- ✅ 轨道输入为单个 DRO/RO 的 JSON（与 `load_orbit_from_json` 一致）

### 3.2 后续（不属于本文件范围）

- NLP 优化与性能：见 `plan/feature-orbit-transfer-replication-1.md` 中 Phase 2 与「下一步工作」
- 脚本与实现细节：**`plan/optimize-implementation.md`**（`optimize.py` 配置、并行、packed worker、输出 JSON、后续性能任务清单）

---

## 4. 参数说明（与 `grid_search.py` 对齐）

| 参数 | 说明 |
|------|------|
| `alpha_min` / `alpha_max` | $\alpha$ 搜索范围，默认 0.5～2.5 |
| `n_alpha` | $\alpha$ 方向网格点数 |
| `n_departure` | 出发点沿 DRO 采样数 |
| `max_transfer_time` | 单次前向积分上限（无量纲 TU） |
| `intersection_threshold` | 相交判定（无量纲 DU） |
| `min_distance_threshold` | 可行候选距离阈值（DU，如 100 km / `DU`） |
| `collision_earth_radius` / `collision_moon_radius` | 撞星半径（DU） |
| `integration_dt` | 输出/积分步长相关（见脚本） |
| `N_WORKERS` | `None` 表示使用 CPU 核数；`1` 为串行 |

---

## 5. 与主计划文档的关系

更完整的论文复现范围、REQ 编号与 Phase 3/4 内容见 **`feature-orbit-transfer-replication-1.md`**。
