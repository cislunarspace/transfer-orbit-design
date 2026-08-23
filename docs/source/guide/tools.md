# 工具参考

v4.0.0 界面接通的计算工具只有**轨道族生成**（orbit_family_generation）。
参数面板由工具的 JSON Schema 自动生成：字段范围、默认值与说明来自 e2m2e 的
Pydantic 模型；按 `orbit_type` 裁剪，只显示当前族适用的字段；Optional 字段
以勾选控制传不传值（勾选即传、不勾视为未设置）。

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

14 个工具的 schema 已全部导出（`frontend/src/toolSchemas/`）。7 个计算
工具（轨道族生成、轨道设计、轨道保持、轨道预报、转移设计、轨道稳定性、
时空坐标转换）的界面已全部接通；catalog 管理操作（delete / export /
promote / tag / sweep）尚未提供界面入口，需要时经
[e2m2e CLI](https://cislunarspace.github.io/e2m2e/) 使用。
