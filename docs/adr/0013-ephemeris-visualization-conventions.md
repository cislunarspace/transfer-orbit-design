# ADR 0013：星历模型可视化的坐标与时间约定

**状态**：已接受
**日期**：2026-08-09
**关联**：ADR 0010（内嵌可视化）、ADR 0011（算法层直调）；CONTEXT.md（坐标系 / 图层 / 绘图与可视化）

## 背景

ADR 0010 落地内嵌画布时只围绕 CR3BP 旋转系设计：画布读 `states[:,:3]`，按 μ 画地月与 L1–L5，单位隐含无量纲（DU）。星历模型结果（轨道保持 control_orbit 产出的受控星历、轨道设计 design_orbit 产出的标称星历）虽也送进了画布，但有四个问题：

1. **原点不一致**：算法层输出的 `EphemerisTable.synodic_position` 是地心归一（月球在 +1，源自 design_orbit 与 monte_carlo 的 `synodic[:,0] += μ`），而画布地月标注按质心归一（月球在 1−μ）。两者差 μ·DU ≈ 4690 km，画 NRHO 这类绕月轨道时，月球标记与轨迹肉眼可见地错位。
2. **缺惯性系视图**：GCRS 惯性位置 `position_km` 从未进入画布，用户看不到星历结果的地心视角。
3. **时间轴退化**：control_orbit 产物的 `times` 是 `np.arange(n)` 占位索引，丢了物理时间，无法支撑惯性系月球轨迹或动画。
4. **design_orbit 的标称星历在画布上完全看不到**：CR3BP 周期轨道作为初猜能画，但同一产物里真实星历模型下的标称星历（拟周期、跨整个 duration）一直埋在 Artifact 的 `extra["ephemeris"]`，画布只读顶层 `state_data`（初猜）。本 ADR 初版只覆盖 control_orbit 的受控星历；#359 把范围扩到 design_orbit 的标称星历。

文献调研（三轮并行，覆盖约 2700 篇 cislunar 文献）的结论：

- **脉动-旋转系**（pulsating-rotating frame，瞬时地月距离归一）是 cislunar 可视化绝对主流（约 70%）。Folta 等 2022（NASA GSFC 官方建模约定）有专门分析框论证为何用无量纲旋转系：地月与 L₁ 在该系固定，把随时间演化的轨迹压进一张静态 2D 图。Park 2025 给出最严格的定义与转换链。
- **瞬时平动点在脉动归一系里与 CR3BP 几何完全一致**（5 个固定点），只在惯性系或非脉动系里才沿地月连线摆动（Boudad 2022、Gómez 等 2001）。Boudad 同时警告：瞬时点是零维点集，不是轨迹，不能连成平动点运动。
- **多视图并排**（会合系 + 惯性系）是标准做法（Muralidharan & Howell 2021、Boudad 2022）。
- **原点约定有分歧**但只限一处：质心（Park 2025，理论派）、月心（Baresi 2023，月附近可视化）、地心（Pavlak 2013、Han 2026，工程对接 JPL 星历）。其余（归一基准、月球位置、转换链结构）全一致。
- 惯性系画月球完整真实公转轨迹，文献里几乎没有，旋转系月球本就固定，惯性系 snapshot 通常省略或画参考圆。本决策采 SPICE 真实轨迹作为合理增强。

核查算法层：`SynodicAxes.characteristic_length(et)` 返回瞬时地月距离，旋转矩阵由瞬时月球状态构造，e2m2e 已是脉动-旋转系，无需新建坐标系。

## 决策

1. **坐标系**：会合系统一**质心归一**（Earth@−μ, Moon@1−μ，瞬时距离脉动）。星历产物的会合系位置在送入画布前减 μ；CR3BP 单条轨道数据与现有地月 / 平动点标注不动。
2. **视图**：`CanvasState` 加 `frame` 字段（`synodic` | `inertial`），支持会合系（默认）与地心惯性系 GCRS 切换。月心系暂不做。
3. **平动点**：仅会合系视图画 5 个 CR3BP 平动点（脉动系下即瞬时平动点，自动满足画瞬时平动点的需求）；惯性系视图不画。
4. **惯性系天体**：地球置于原点；月球按 `times_et` 从 SPICE 取 GCRS 真实轨迹画出。
5. **时间**：`Artifact.times` 存 **et 秒**（J2000 起算）；显示与导出转 UTC 或 MJD。来源由 GUI 侧从 `EphemerisTable` 的 UTC 拆分用 `spice.str2et` 重建，**不修改算法层上游**填 `times_jd_tdb`。
6. **动画**：GIF 导出为独立导出动画工具（按 frame + `times_et` 逐帧渲染再合成），主画布不做实时播放。（主画布时刻交互已由 ADR 0014 增补：时间轴 scrubber 选择时刻，不含播放。）

## 理由

- 质心归一与 CR3BP 教科书及现有 viz_adapter 一致，改动最小（仅星历侧减 μ）。
- 算法层已是脉动系（SynodicAxes 用瞬时地月距离），无需新建坐标系。
- 瞬时平动点在脉动系下退化为 5 个固定点，免去逐历元算法，会合系视图直接复用现有 L1–L5 标注即满足需求。
- et 秒是 SPICE 原生，惯性系查月球与 GIF 帧采样直接复用。
- GIF 走独立导出，规避主画布逐帧性能问题（matplotlib 3D + SPICE 查询）。

## 后果

### 正面

- 修掉 control_orbit 星历的 ~μ 偏移，轨迹与地月标注严格对齐。
- 星历结果获得会合系（自洽）与地心惯性系两种视图，可同轨对比。
- 真物理时间贯通数据契约，为动画与未来时间相关分析（色标、时刻标注、滑窗）铺路。

### 负面

- Artifact 契约变厚（多带 `position_km`、`times_et`、`frame`）。
- 惯性系视图与 GIF 依赖 SPICE 星历内核（`.bsp`），离线环境需降级提示。
- GIF 导出是新增子系统，有维护成本：当前同步渲染阻塞 UI，大画布高帧数下数秒；未来可移 QThread（与 OrbitDesignWorker 同模式）。

## 后续

- 月心系视图（文献低频）若有明确需求再开。
- GIF 帧采样策略在参数对话框暴露，默认 cumulative、滑窗 3 天（地月 DRO ~14 天周期的合理量级）。
- 若算法层将来填 `times_jd_tdb`，GUI 侧的 `str2et` 重建可替换为直读，去掉一处重复。

## 更新（#359，2026-08-09）：范围扩到 design_orbit 的标称星历

初版只覆盖 control_orbit 的受控星历。#359 把范围扩到 design_orbit 产出的标称星历，同一份产物里 CR3BP 初猜（无量纲周期轨道）与真实星历模型下的标称星历（拟周期、跨整个 duration）首次并列进入画布。

具体落地：

- **数据契约**：`_artifact_for_id` 显式暴露四个并列槽位：`initial_guess_states`（CR3BP 周期轨道，无量纲会合系）、`ephemeris_synodic`（星历会合系位置，已减 μ）、`ephemeris_position_km`（GCRS km）、`ephemeris_times_et`（ET 秒）。不嵌套在 `extra["ephemeris"]` 里让人猜、不靠顶层找不到翻 dict 的隐式 fallback。control_orbit 的受控星历沿 `ephemeris_synodic` 槽（state_data 已在 facade_bridge 减过 μ）。
- **质心归一对齐沿用决策 1**：design_orbit 标称星历的会合系位置在 `_artifact_for_id` 里减 μ 后再送画布，与 control_orbit 的处理一致。
- **绘制内容**：`CanvasState` 加 `plot_content` 字段（初猜 / 星历 / 叠加，默认叠加），与 `frame` 正交。叠加视图初猜用实线、星历用虚线，TAB10 相邻色区分。惯性系下初猜灰显（CR3BP 无量纲无惯性系表示）；control_orbit 产物无初猜，初猜恒灰显。
- **导出动画跟随绘制内容**：仅星历可按物理时间轴动画化；初猜模式明确拒绝导出（CR3BP 单周期无物理时间轴）。
- **持久化**：design_orbit NPZ 已存全字段（`eph_` 前缀），`load_artifact_arrays` 还原进 `extra["ephemeris"]`，从磁盘恢复的历史 Artifact 同样支持绘制内容切换。NPZ schema 不变。
