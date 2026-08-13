# 工具参考

GUI 的工具下拉与 e2m2e facade 工具清单对齐：**轨道设计 / 轨道保持 / 轨道族生成**
已接入（可选），**稳定性分析**走项目树右键入口；e2m2e 已实现但 GUI 尚未接入的
（转移设计 / 轨道预报 / 时空坐标转换）与 e2m2e 占位的（转移搜索 / 小推力设计 /
不变流形分析 / 低能转移 / 相对运动）灰显"即将提供"，悬停显示工具说明。

参数面板由工具绑定的 Pydantic 模型自动生成，字段范围、默认值与说明来自模型
本身。面板按组展示（组标题 + 分隔线），每个可换算数值参数都有单位下拉框——
切换单位只改变显示数值，不改变物理量；数值框清空时显示"可填范围"占位提示，
悬停同样可见。"重置参数"按钮一键恢复默认值。

## 轨道设计（design_orbit）

在 CR3BP 中生成周期轨道并修正到星历模型。可选轨道类型：**DRO / DPO / Halo /
NRHO / Lissajous / Axial / L4 / L5 / L4_SPO / L5_SPO / L4_LPO / L5_LPO /
L4_HORSESHOE / L5_HORSESHOE / ELFO**。选择类型后面板只显示该类型相关的形状参数。

### 形状参数（按类型）

| 轨道类型 | 参数 | 说明 |
|----------|------|------|
| DRO | `amplitude` | 距月振幅（km，默认 60000；可切 km/m/DU） |
| DRO | `phase` | 相位（默认 0.5001；可切 周期份额/度/弧度） |
| DPO | `amplitude` / `phase` | 同 DRO，默认 20000 / 0.5001 |
| Halo | `collinear_point` | 共线平动点（L1/L2/L3 下拉，默认 L2） |
| Halo | `amplitude` | 面外振幅（km，默认 30000） |
| Halo | `phase` | 相位（默认 0） |
| NRHO | `collinear_point` | 共线平动点（默认 L2） |
| NRHO | `north_south` | 北族 / 南族下拉（默认南族） |
| NRHO | `perilune_height` | 近月点高度（km，默认 5000） |
| NRHO | `phase` | 相位（默认 0.5） |
| Lissajous | `collinear_point` | 共线平动点（默认 L2） |
| Lissajous | `amplitude_in` / `amplitude_out` | 面内 / 面外振幅（km，默认 2500 / 7500） |
| Lissajous | `phase_in` / `phase_out` | 两个相位（默认 0.01 / 0.55） |
| Axial | `collinear_point` / `amplitude` / `phase` | 轴向族（默认 L2 / 5000 km / 0） |
| L4 / L5 | `amplitude_in` / `amplitude_out` | 振幅（默认 8000 / 6000） |
| L4 / L5 | `phase_in` / `phase_out` | 相位（默认 0） |
| L4_SPO / L5_SPO | `amplitude` / `phase` | 短周期族（默认 10000 km / 0） |
| L4_LPO / L5_LPO | `amplitude` / `phase` | 长周期族（默认 50000 km / 0） |
| L4_HORSESHOE / L5_HORSESHOE | `amplitude` / `phase` | 马蹄形族（默认 150000 km / 0） |
| ELFO | `semi_major_axis` | 月心半长轴（km，必填，默认 6500） |
| ELFO | `inclination` / `arg_of_pericenter` | 倾角 / 近月点幅角（度，默认 75 / 270；可切 rad） |
| ELFO | `perilune_height` | 近月点高度（km，默认 200） |

### 通用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `epoch` | 2024-01-01 | 起始历元：6 个输入框（年/月/日/时/分/秒）或 ISO 字符串 |
| `duration` | 1 个月 | 传播时长（可切 年/月/日/时/秒/TU。轨道保持以它为输入，建议 ≥ 保持总时长） |
| `output_step` | 3600 s | 星历输出步长（可切 秒/时/日/TU） |
| `correction_method` | two_level | 星历修正方法：`standard` / `two_level` / `homotopy`。Halo/NRHO 由算法自动改走 `segmented`（见 {doc}`../concepts/ephemeris`），无需手选 |
| `correction_revolutions` | 1 | 修正圈数 |
| `correction_velocity_tolerance` | 0.1 | 速度连续性容差 |
| `earth_degree` / `moon_degree` | 10 | 地球 / 月球引力位阶数 |
| `perturbation` / `dyb` | 空 | 可选摄动项（太阳引力等）/ DYB 面质比系数（9 分量，dyb[0] 为等效面质比 m²/kg；空框时显示 JSON 格式示例） |

### 结果

输出 JSON + NPZ 双文件到 `output/<type>/`（见 {doc}`output`），画布叠加显示
CR3BP 初猜（实线）与标称星历（虚线）。参数校验失败（如 ELFO 缺半长轴）会
阻止运行并给出明确原因。

## 轨道保持（control_orbit）

以选中轨道工件的星历为输入，做带导航误差、机动执行误差与光压不确定度的
蒙特卡洛仿真，输出受控星历与机动 Δv 统计。**必须从项目树右键轨道发起**
（选中工件作为标称星历输入）。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `control_mode` | 1 | 控制模式下拉：1=目标点（宽松）、2=目标点（严格）、3=特征点；4/5/6 为对应模式 + 角动量管理 |
| `is_nrho` | 0 | 目标轨道是否 NRHO（是/否下拉） |
| `special_mode` | 1 | 特征点模式下拉：1=Lissajous（ẋ=0）、2=Halo/NRHO（ẋ=0 且 ż=0） |
| `control_interval` | 30 天 | 控制时间间隔（可切 天/秒/TU） |
| `feedback_arc` | 28 天 | 目标点模式反馈弧段（可切 天/秒/TU） |
| `num_controls` | 120 | 控制次数（总时长 = (次数-1) × 间隔） |
| `num_monte_carlo` | 5 | 蒙特卡洛样本数 |
| `output_step` | 86400 s | 受控星历输出间隔（可切 秒/时/日/TU） |
| `engine_layout` | 空 | 发动机布局 JSON（`positions_m` / `directions`），角动量管理（模式 4–6）必填；空框时显示格式示例 |
| `momentum_interval` | 5 天 | 角动量卸载间隔，0 = 与轨道控制同步（可切 天/秒/TU） |
| `spacecraft_mass` | 1000 kg | 航天器质量 |
| `srp_offset_m` | 空 | SRP 压心相对质心偏移 [x,y,z]（m，可切 DU） |
| `srp_torque` | 空 | 常值 SRP 力矩 [τx,τy,τz]（N·m） |

运行前校验：**仿真总时长（= 控制次数 × 间隔 + 反馈弧）不得超过标称星历
覆盖时长**，超出会拦截并提示调整参数或延长标称轨道。例如 30 天标称星历，
用 0.25 天/次 × 119 次 + 0.125 天反馈弧可覆盖。

结果写入 `output/ephemeris/`（JSON + NPZ）。全样本失败时只写 JSON 元数据
（`num_failed` 等于样本数），画布无受控星历可显示。

## 轨道族生成（orbit_family_generation）

从 Halo 小振幅种子出发，固定面外振幅逐步延拓，生成一族轨道。第一版仅支持
**Halo 北族**（其余轨道类型在 e2m2e 只有单条设计函数，无族延拓接口）。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `libration_point` | 2 | 共线平动点（L1/L2 下拉） |
| `max_amplitude_km` | 30000 | 最大面外振幅（km，范围 1000–57000；可切 km/m/DU）；延拓到该振幅或折叠点自动停止 |
| `n_orbits` | 20 | 族成员数（含种子，实际以延拓结果为准） |

纯 CR3BP 计算，不需要 SPICE 内核。结果写入 `output/family/`，画布按成员
逐条叠加渲染。

## 稳定性分析（orbit_stability）

对选中轨道的 CR3BP 周期解做 Floquet 稳定性分析。**无参数面板**，右键轨道
工件触发，结果在对话框展示并落盘 `output/stability/` 独立 JSON（不进项目树、
不上画布）：

- 单值矩阵与特征值（Floquet 乘子）；
- 稳定性指数 ν₁ / ν₂ / ν₃ / Broucke；
- 稳定性分类与分岔检测（含数值误差诊断）。

纯 CR3BP 计算，不需要 SPICE 内核。
