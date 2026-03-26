# Grid Search 实现计划

**Author**: AI Assistant
**Date**: 2026-03-25
**Status**: Ready to Implement
**Target**: `scripts/transfer/grid_search.py`

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
transfer_search.max_transfer_time = 15.0
transfer_search.intersection_threshold = 0.001
transfer_search.min_distance_threshold = 100.0 / 384405.0  # 默认 100 km（无量纲 DU）；或 `from e2m2e.transfer import DEFAULT_MIN_DISTANCE_THRESHOLD_DU`
transfer_search.collision_earth_radius = 0.0005
transfer_search.collision_moon_radius = 0.0003
transfer_search.integration_dt = 0.01
```

### 2.2 e2m2e 改动

已修改 `/home/desktop/codes/e2m2e/e2m2e/transfer/transfer_search.py`:

1. `DROTransferSearch.__init__` 中直接设置实例属性（默认值）
2. `configure_search()` 方法更新实例属性（向后兼容）
3. `_grid_search()` 等内部方法从 `self` 读取配置

---

## 3. 当前状态

### 3.1 已完成

- ✅ e2m2e `DROTransferSearch` 支持直接属性赋值
- ✅ `grid_search.py` 使用直接属性赋值
- ✅ 配置参数通过实例属性传递

### 3.2 待完成

- [ ] 轨道数据文件格式确认（需要单个 orbit JSON）
- [ ] 完整测试运行

---

## 4. 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `alpha_min` | float | 0.5 | α搜索下限 |
| `alpha_max` | float | 2.5 | α搜索上限 |
| `n_alpha` | int | 101 | α方向网格点数 |
| `n_departure` | int | 200 | 出发点采样数量 |
| `max_transfer_time` | float | 15.0 | 最大转移时间 (TU) |
| `intersection_threshold` | float | 0.001 | 相交判定阈值 |
| `min_distance_threshold` | float | 100 km（≈ `2.6×10⁻⁴` DU） | 候选解最小距离；与 `DEFAULT_MIN_DISTANCE_THRESHOLD_DU` 一致 |
| `collision_earth_radius` | float | 0.0005 | 地球碰撞半径 (DU) |
| `collision_moon_radius` | float | 0.0003 | 月球碰撞半径 (DU) |
| `integration_dt` | float | 0.01 | 积分时间步长 |
