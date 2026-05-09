---
sidebar_position: 5
---

# 转移设计与优化

轨道生成后，使用"搜索-优化"两步法设计两脉冲转移。

## 统一两步法

所有转移类型（DRO↔RO、DRO↔GEO、GEO↔DRO、LEO↔DRO）使用相同的两步框架：

### 第一步：网格搜索

对搜索变量在设定范围内网格化，前向积分筛选可行转移。

### 第二步：NLP 优化

以网格搜索结果为初始猜测，使用 SQP 算法最小化 $\Delta v_1 + \Delta v_2$。

---

## DRO → RO

从远距离逆行轨道到共振轨道的两脉冲转移。

### 搜索变量

| 变量 | 描述 | 范围 |
|------|------|------|
| 出发点 | DRO 上的位置 | 沿轨道分布 |
| α | 切向速度比 | 0.5 ~ 2.5 |
| θs0 | 太阳初始相位（BR4BP） | 0 ~ 2π |

### 脚本

```bash
# 网格搜索
uv run python -m tod.pipelines.transfer.dro_to_ro.grid_search_dro_to_ro

# NLP 优化
uv run python -m tod.pipelines.transfer.dro_to_ro.optimize_dro_to_ro

# 可视化
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_search_results_dro_to_ro
uv run python -m tod.pipelines.transfer.dro_to_ro.plot_optimize_result_dro_to_ro
```

---

## DRO → GEO

从远距离逆行轨道到地球同步轨道的转移。

### 搜索变量

| 变量 | 描述 | 范围 |
|------|------|------|
| 出发点 | DRO 上的位置 | 沿轨道分布 |
| α | 切向速度比 | 0.5 ~ 2.5 |

### 脚本

```bash
# 网格搜索
uv run python -m tod.pipelines.transfer.dro_to_geo.grid_search_dro_to_geo

# NLP 优化
uv run python -m tod.pipelines.transfer.dro_to_geo.optimize_dro_to_geo

# 可视化
uv run python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo
```

---

## GEO → DRO

从地球同步轨道返回远距离逆行轨道的转移（逆向）。

### 搜索变量

| 变量 | 描述 | 范围 |
|------|------|------|
| 出发点 | GEO 上的位置 | 沿轨道分布 |
| α | 切向速度比 | 0.5 ~ 2.5 |

### 脚本

```bash
# 网格搜索
uv run python -m tod.pipelines.transfer.geo_to_dro.grid_search_geo_to_dro

# NLP 优化
uv run python -m tod.pipelines.transfer.geo_to_dro.optimize_geo_to_dro

# 验证（碰撞检测）
uv run python -m tod.pipelines.transfer.geo_to_dro.validate_geo_to_dro

# 可视化
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_search_results_geo_to_dro
uv run python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro
```

---

## LEO → DRO

从低轨道到远距离逆行轨道的转移。

### 搜索变量

| 变量 | 描述 | 范围 |
|------|------|------|
| 出发点 | LEO 上的位置 | 沿轨道分布 |
| α | 切向速度比 | 0.5 ~ 2.5 |

### 脚本

```bash
# 网格搜索
uv run python -m tod.pipelines.transfer.leo_to_dro.grid_search_leo_to_dro

# NLP 优化
uv run python -m tod.pipelines.transfer.leo_to_dro.optimize_leo_to_dro
```

---

## 转移类型分类

| 类型 | 持续时间 | Δv | 特征 |
|------|----------|-----|------|
| 直接转移 | < 20 天 | 高 | 短椭圆，不到一圈地球 |
| 月球借力转移（LGA） | 60-80 天 | 最低 | 月球引力辅助，多圈调相 |
| 外部转移 | 60-100 天 | 中等 | 远地点 > 3 倍地月距离 |

## 可视化参数

所有 plot 脚本支持：

| 参数 | 描述 |
|------|------|
| `--orbit` | 绘制 3D 转移轨道图 |
| `--time-dv` | 绘制转移时间 vs Δv 散点图 |
| `--idx <N\|best\|all>` | 选择绘制的可行解 |
| `--save <path>` | 保存图片而非显示 |
