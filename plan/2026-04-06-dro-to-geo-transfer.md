# DRO → GEO 双脉冲转移轨道设计

## 目标
设计从 DRO（远距离逆行轨道）到 GEO（地球同步轨道）的双脉冲转移轨道，复用现有 grid_search → NLP optimize → plot 的两阶段流程。

## 背景与关键差异
- **现有流程**：3:1 DRO → 3:1 RO（两个 CR3BP 周期轨道）
- **新流程**：DRO → GEO（周期轨道 → 固定半径球面）
- **GEO 建模**：固定半径圆（r = 42164 km from Earth center），非 CR3BP 周期轨道
- **到达条件变更**：从"轨迹接近 RO 状态点"变为"轨迹穿越 GEO 球面"
- **速度匹配变更**：从"与 RO 轨道速度平行"变为"与 GEO 圆速度匹配"

## GEO 参数（CR3BP 归一化单位）
- r_GEO = 42164 / 384405 ≈ 0.10968 DU
- Earth 位置：(-μ, 0, 0) ≈ (-0.01215, 0, 0)
- v_circular = sqrt((1-μ)/r_GEO) ≈ 3.001 VU ≈ 3071 m/s
- GEO 惯性周期 ≈ 0.2296 TU ≈ 1 天

## 任务列表

- [x] 1. **创建 GEO 工具模块** `scripts/utils/geo.py` ✓
  - GEO 常量: R_GEO=0.10969 DU, V_CIRCULAR_GEO=3.001 VU, T_GEO=0.2296 TU
  - `geo_circular_velocity_rotating()`: 旋转系圆速度计算
  - `detect_geo_sphere_crossing()`: GEO 球面穿越检测
  - `find_closest_approach_to_geo()`: 最接近 GEO 点
  - `compute_geo_dv2()`: GEO 插入 delta-v
  - `compute_departure_velocity()`: 切向速度缩放
  - `check_collision()`: 碰撞检测

- [x] 2. **实现 DRO→GEO 网格搜索** `scripts/transfer/grid_search_dro_geo.py` ✓
  - 参考 `grid_search.py` 结构
  - GEO 球面穿越条件替代 RO 距离检测
  - 碰撞检测、dv 估算、可行解筛选
  - tqdm 进度条
  - 冒烟测试: 20 dep × 20 α → 47 可行解，最优 total dv ≈ 1.28 VU (1307 m/s)

- [x] 3. **实现 DRO→GEO NLP 优化** `scripts/transfer/optimize_dro_geo.py` ✓
  - 参考 `optimize.py` 结构
  - 优化变量: [α, T]（2变量，比 DRO→RO 的 3 变量更简洁）
  - 约束: |r_final - r_earth|² = r_GEO²（GEO 球面约束）
  - 目标: min(dv1 + dv2)
  - 支持并行（ProcessPoolExecutor / ThreadPoolExecutor）

- [ ] 4. **创建可视化脚本**
  - `scripts/transfer/plot_search_results_dro_geo.py`：搜索结果散点图 + 轨道图
  - `scripts/transfer/plot_optimize_result_dro_geo.py`：优化结果 dv 柱状图 + 轨道图

- [x] 5. **端到端冒烟测试** ✓
  - 网格搜索冒烟测试通过
  - DRO 文件已存在: `output/dro/dro_31_3857864736.json`
  - 待运行: 完整 200×100 搜索 + NLP 优化

## 备注
- **风险**：GEO 距离地球很近（0.11 DU），远小于 DRO 半径（~1 DU），转移轨迹可能多次穿越 GEO 球面，需要正确处理
- **约束**：复用 e2m2e 的 CR3BP_System、CR3BP_Dynamics、Orbit 等基础类
- **注意**：GEO 圆速度在旋转系中需要扣除坐标系旋转效应（v_rot = v_inertial - ω × r）
- **参数调优**：alpha 范围和转移时间上界可能需要根据 DRO→GEO 的物理特性调整
