# 通用星历轨道可视化脚本

## 目标
在 `scripts/ephemeris/` 下创建 `plot_ephemeris_orbit.py`，从 JSON 文件加载星历修正结果，传播各段轨道并生成多维度可视化图表，支持任意轨道类型（DRO、Halo、RO 等）。

## 任务列表
- [x] 1. 搭建脚本骨架：参数解析（JSON 文件路径、展示模式）、数据加载
- [x] 2. 轨道传播模块：从 corrected_states + corrected_times_et 传播各段轨道拼接完整轨迹
- [x] 3. J2000 km 坐标系可视化：3D 轨道图 + 2D 投影图（含天体真实位置）
- [x] 4. Synodic 无量纲坐标转换：通过 SynodicJ2000Transformation 转换后复用 OrbitVisualizer
- [x] 5. 距离时间曲线：到地球/月球距离随时间变化
- [x] 6. 位置连续性验证图：各 patch point 间的位置误差
- [x] 7. 残差收敛图：迭代过程的残差变化

## 备注
- e2m2e 的 OrbitVisualizer 仅支持 CR3BP（synodic 无量纲），J2000 km 模式需自行用 matplotlib 实现
- SPICEManager.get_body_position() 获取天体在特定 ET 时刻的 J2000 位置
- EphemerisDynamics.propagate() 返回 states 形状为 (6, n)，注意转置
- JSON 中 corrected_states 单位为 km/km/s，corrected_times_et 单位为秒（ET）
