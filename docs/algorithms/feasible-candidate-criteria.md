# 可行解判定

## 什么是「可行解」

网格搜索返回的每一个结果点，在进入优化阶段之前需要先通过「可行性」检查。

一个点是**可行**的，当且仅当：

1. **无碰撞** — 轨迹未进入地球或月球的碰撞保护区。
2. **满足以下距离条件之一**：
   - 与目标轨道发生相交（`intersection_found`）；
   - 全局最小距离 `min_distance` 小于阈值 \(m_{dt}\)；
   - 检测到局部极小距离事件，且该距离 `local_minimum_distance` 小于阈值 \(m_{dt}\)。

> 直观理解：要么轨迹「碰到了」目标轨道（相交），要么「靠得足够近」（距离小于阈值）——近到可以作为一个好的优化初值。

## 距离阈值

阈值 \(m_{dt}\) 控制「多近才算近」。**默认对应物理距离 100 km**：在 CR3BP 中取 \(m_{dt} = 100 / L\)，其中 \(L\) 为地月平均距离（约 384405 km，即 1 DU），故无量纲值约为 `2.6×10⁻⁴` DU。库中常量名为 `DEFAULT_MIN_DISTANCE_THRESHOLD_DU`（`e2m2e/transfer/transfer_base.py`）。

代码中有两处实现：

| 类 | 文件 | 阈值来源 |
|----|------|---------|
| `BaseTransfer` | `e2m2e/transfer/transfer_base.py` | 默认 `DEFAULT_MIN_DISTANCE_THRESHOLD_DU`（100 km） |
| `TransferSearch` | `e2m2e/transfer/transfer_search.py` | 实例属性 `min_distance_threshold`；若为 `None` 则回退到基类 |

> 需要更严或更松时，为 `min_distance_threshold` 显式赋值（无量纲 DU）。`scripts/transfer/grid_search.py` 中 `MIN_DISTANCE_THRESHOLD = 100.0 / DU` 与库默认一致。

## 判定逻辑

伪代码如下：

```
输入：搜索结果字典 result

1. 若 TransferSearch.min_distance_threshold 为 None
     → 使用基类逻辑，阈值 mdt = DEFAULT_MIN_DISTANCE_THRESHOLD_DU（100 km）

2. 若 collision_found == True
     → 不可行（直接排除）

3. 读取全局最小距离 md 和局部极小距离 lmd

4. 若 intersection_found == True
     → 可行（相交优先）

5. 若 md < mdt
     → 可行

6. 若 local_minimum_found == True 且 lmd < mdt
     → 可行

7. 其余情况 → 不可行
```

简化版：排除碰撞后，可行当且仅当「相交」OR「全局最小距离足够近」OR「存在符合条件的局部极小」。

```
feasible = not collision
            and (intersection_found
                 or md < mdt
                 or (local_minimum_found and lmd < mdt))
```

## 字段说明

| 字段 | 含义 |
|------|------|
| `collision_found` | 轨迹是否与地球/月球碰撞球相交 |
| `intersection_found` | 轨迹与目标轨道是否相交（搜索阶段已判定） |
| `min_distance` | 轨迹到目标轨道所有采样点的最小距离 |
| `local_minimum_found` | 轨迹是否经过一个局部极小距离点 |
| `local_minimum_distance` | 上述局部极小点的距离值 |

> 注意：`intersection_threshold` 作用于搜索阶段，决定 `intersection_found` 的值，不出现在 `_is_feasible` 的判定式中。

## 与脚本的关系

- `grid_search.py`：构造 `TransferSearch` 时通过 `MIN_DISTANCE_THRESHOLD`（脚本内常量）设置搜索类的 `min_distance_threshold`，然后调用 `_is_feasible` 将结果写入 JSON 字段 `is_feasible`。两者应保持一致。
- `plot_search_results.py`：仅读取 JSON 中的 `is_feasible`，不再重复判定逻辑。

## 测试

`e2m2e/tests/transfer/test_dro_ro_search.py` 中有单元测试覆盖以下情形：

- 局部极小距离大于阈值 → 不可行
- 局部极小距离小于阈值 → 可行
- 相交（无碰撞）→ 可行
- 发生碰撞 → 不可行
