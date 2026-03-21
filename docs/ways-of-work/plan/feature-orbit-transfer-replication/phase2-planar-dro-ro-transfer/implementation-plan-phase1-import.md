# Phase 1 数据导入优化 - 实施计划

## 1. 概述

**问题**: 当前 `phase1_grid_search.py` 导入的是 `OrbitFamily` 对象，需要额外通过索引提取单条轨道。

**目标**: 改为直接导入单条 `Orbit` 对象，简化数据流。

### 当前数据流
```
DRO family JSON → OrbitFamily.load_from_file() → dro_data.orbits[index] → Orbit
RO family JSON → OrbitFamily.load_from_file() → ro_data.orbits[index] → Orbit
```

### 优化后数据流
```
单条DRO JSON → Orbit.load() → Orbit (直接)
单条RO JSON → Orbit.load() → Orbit (直接)
```

## 2. 技术分析

### 2.1 Orbit vs OrbitFamily

| 类 | 用途 | 关键方法 |
|----|------|----------|
| `Orbit` | 单条轨道 | `load()` |
| `OrbitFamily` | 轨道族 | `load_from_file()` |

### 2.2 e2m2e 轨道加载接口

需要确认 `Orbit.load()` 是否支持从 JSON 文件加载单条轨道。查看 `e2m2e/core/orbit.py` 中的 `Orbit` 类加载方法。

## 3. 实施步骤

### 3.1 调研阶段

| 步骤 | 描述 | 验证方法 |
|------|------|----------|
| STEP-1 | 确认 `Orbit.load()` 方法签名 | 读取 e2m2e/core/orbit.py |
| STEP-2 | 检查 JSON 格式是否支持单条轨道 | 查看 output JSON 结构 |
| STEP-3 | 确认 family JSON 也可用 `Orbit.load()` | 测试兼容性 |

### 3.2 代码修改

#### 修改 `phase1_grid_search.py`

```python
# 修改前
dro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(dro_files[0])
ro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_files[0])
dro_orbit = dro_data.orbits[args.dro_index]
ro_orbit = ro_data.orbits[args.ro_index]

# 修改后
dro_orbit = e2m2e.core.orbit.Orbit.load(dro_files[0])
ro_orbit = e2m2e.core.orbit.Orbit.load(ro_files[0])
```

#### 同步修改 `phase2_optimize.py` 和 `plot_transfer.py`

## 4. 文件清单

| 文件 | 修改类型 | 变更内容 |
|------|----------|----------|
| `scripts/transfer/phase1_grid_search.py` | 修改 | 改用 `Orbit.load()` |
| `scripts/transfer/phase2_optimize.py` | 修改 | 改用 `Orbit.load()` |
| `scripts/transfer/plot_transfer.py` | 修改 | 改用 `Orbit.load()` |

## 5. 验证计划

1. 运行 `phase1_grid_search.py` 确认功能正常
2. 运行 `phase2_optimize.py` 确认功能正常  
3. 运行 `plot_transfer.py` 确认绘图正常
