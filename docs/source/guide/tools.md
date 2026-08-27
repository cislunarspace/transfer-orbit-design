# 工具参考

中栏工具面板接通八个工具。参数面板由工具的 JSON Schema 自动生成：字段范围、
默认值与说明来自 e2m2e 的 Pydantic 模型；按 `orbit_type` 裁剪，只显示当前族
适用的字段；Optional 字段以勾选控制传不传值（勾选即传、不勾视为未设置）。
本页展开说明轨道族生成，其余工具的参数见各 schema 与 {doc}`../dev/architecture`。

## 轨道族生成（orbit_family_generation）

在 CR3BP 中生成轨道族：周期族（Halo / NRHO / Axial / SPO / LPO / Horseshoe）
为延拓，Lissajous 为拟周期轨迹的参数采样，DRO 为月心族（不绑定平动点）。
范围与默认值由 e2m2e `FamilyGenerationRequest` 的 `valid_ranges` 决定，GUI
不另维护一份。纯 CR3BP 计算，不需要 SPICE 内核。

| 参数 | 适用族 | 说明 |
|------|--------|------|
| `orbit_type` | 全部 | 族类型：HALO / NRHO / AXIAL / LISSAJOUS / SPO / LPO / HORSESHOE / DRO |
| `libration_point` | 除 DRO | 平动点（共线族 L1/L2，Lissajous 加 L3，三角族 L4/L5）；缺省按族取默认 |
| `n_orbits` | 全部 | 族成员数上限（实际以延拓/采样结果为准） |
| `max_amplitude_km` | 全部 | 振幅上限（km）：Halo/Axial 带符号区分北/南（上/下）族；SPO/LPO/Horseshoe 为距 L4/L5 径向距离；DRO 为距月心距离 |
| `min_amplitude_km` | SPO / LPO / Horseshoe / DRO | 振幅下限（km） |
| `north_south` | NRHO | 北族 / 南族 |
| `perilune_height_max_km` | NRHO | 近月点高度上限（km） |
| `amplitude_in_km` / `amplitude_out_km` | Lissajous | 面内 / 面外振幅上限（km） |
| `phase_in` / `phase_out` | Lissajous | 面内 / 面外初始相位（0~1） |
| `continuation_direction` | SPO / LPO / Horseshoe / NRHO | 延拓方向（`decrease-x0` / `increase-x0`） |
| `match_tolerance_km` | SPO / LPO / Horseshoe | 振幅匹配容差（km） |

结果入轨道库（record id 显示在面板下方），族成员轨迹逐条渲染到画布。

## 其余工具

14 个工具的 schema 已全部导出（`frontend/src/toolSchemas/`）。其余六个计算
工具（轨道设计、轨道保持、轨道预报、转移设计、轨道稳定性、时空坐标转换）
与参数空间扫描（catalog_sweep）都在工具面板直接可用。catalog 管理操作的
界面分布：查询/取用由目录浏览与画布叠加承担，删除在项目树右键菜单，标注
与族成员提升在记录详情面板，教学案例包导出在过滤栏。需要脚本化工作流时
经 [e2m2e CLI](https://cislunarspace.github.io/e2m2e/) 使用。