# 轨道保持

地月空间的任务轨道——DRO、halo、NRHO、Lissajous——在真实星历模型里都不是严格周期
轨道。月球轨道偏心率、太阳引力、太阳光压等摄动会让实际轨迹缓慢偏离标称轨道。**轨道
保持**（station-keeping）就是定期做小机动，把轨迹拉回标称轨道附近。

这篇文档给出各类轨道在真实星历里的稳定性与保持代价，帮助设置合理的保持参数。数据
来自全星历模型 Monte-Carlo 仿真文献，不是 CR3BP 理论值。

## 各类轨道的稳定性差异

| 轨道 | 稳定性 | 不机动可保持 | 年均保持 Δv |
|------|--------|-------------|------------|
| DRO（大幅） | 稳定（stability index ≈ 1） | 数月至数年有界 | 0.8–1.0 m/s |
| DRO（小幅） | 稳定 | 数月有界 | 1.5–2.0 m/s |
| 9:2 NRHO | 弱稳定 | 数周有界 | 0.5–2.0 m/s |
| halo（L1/L2） | 不稳定 | 数天即需机动 | 5–7 m/s |
| Lissajous | 不稳定 | 数天即需机动 | 5–10 m/s |

核心区别：**DRO 稳定，halo/Lissajous 不稳定**。DRO 的保持是为了抵消长期小漂移；halo/
Lissajous 的保持是为了压制沿不稳定流形的指数发散，代价高一个量级。

## DRO：长期稳定，且大幅更稳

DRO（Distant Retrograde Orbit）在 CR3BP 里 stability index 接近 1，是临界稳定——既不
指数发散也不快速收敛。这个性质在真实星历里近似保留：DRO 变成准周期的有界运动，会振荡、
漂移，但不会逃逸。

**大幅 DRO 比小幅 DRO 更稳定**，这与直觉相反。文献数据（Zhang & Wang 2022，全星历 +
SRP + 月球非球形，2 年 Monte-Carlo）：

| DRO 距月尺寸 | 周期 | 年均保持 Δv |
|---|---|---|
| ~34000 km | 5.5 天 | 1.96 m/s |
| ~51000 km | 9.1 天 | 1.15 m/s |
| ~72000 km（2:1） | 13.7 天 | **0.82 m/s** |

> "The DROs with large amplitudes have the lowest station-keeping cost."
> —— Zhang & Wang 2022

所以选 DRO 做长期任务时，不必为了"怕不稳"而选紧凑轨道。~50000–70000 km 的中等 DRO
兼顾可视性、稳定性与低保持代价。

## 位置保持做什么

保持机动做两件事：

1. **抵消摄动漂移**。模型里没完全建模的摄动（或建模了但标称轨道是近似的）会让实际轨
   迹缓慢偏离标称轨道。保持机动把这些偏差拉回来。
2. **纠正导航与执行误差**。轨道确定有不确定度，机动执行有偏差，这些误差累积也需要修
   正。

对 DRO，保持是"锦上添花"——不做也能维持很久，做了能更贴标称轨道。对 halo/Lissajous，
保持是"刚需"——不做几天到两周就沿不稳定流形发散到不可用。

## 机动频率与速度增量

对 DRO，保持频率可以很低。文献基准（Zhang & Wang 2022，2:1 DRO ~72000 km）：

| 机动间隔 | 年均 Δv | 平均位置偏差 | 最大偏差 |
|---|---|---|---|
| 2 天 | 0.82 m/s | 1.5 km | 4 km |
| 15 天 | 0.16 m/s | 13 km | 45 km |
| 30 天 | 0.27 m/s | 16 km | 60 km |
| 60 天 | **0.05 m/s** | 39 km | 114 km |

60 天不机动也只漂几十公里——这就是 DRO "长期稳定"的含义。每周一次机动对 DRO 来说偏
过度；几周到两个月一次就够了。

作为对比，halo 轨道（L2，ARTEMIS 实测）年均 5–7 m/s、每周约一次，超过 10–14 天不机动
就可能发散。9:2 NRHO 介于两者之间，年均 0.5–2 m/s、1–2 周一次。

## CR3BP 与真实星历的差异

软件先用 CR3BP（圆型限制性三体问题）算标称轨道，再转换到真实星历模型。

CR3BP 假设地球月球做匀速圆运动、忽略太阳引力等摄动，存在 Jacobi 常数。真实星历里这些
都不成立：

- 月球轨道偏心率约 0.055，地月距每天变；
- 太阳引力破坏 Jacobi 常数，轨道不再严格周期；
- DRO 变成准周期有界运动，halo/Lissajous 的不稳定流形结构仍在。

所以标称轨道在 CR3BP 里算出后，必须在星历模型里重新修正（多重打靶），才能作为保持的
基准。这正是"轨道设计"工具做的：CR3BP 初猜 → 星历修正 → 标称星历。

## 当前软件的能力与限制

**轨道保持工具**（`control_orbit`）以一条标称星历为输入，在考虑导航误差、机动执行误
差、光压不确定度等的情况下做 Monte-Carlo 仿真，输出受控星历与机动 Δv 统计。它评估的
是"给定保持策略，实际飞行的轨道会怎样"。

当前版本的限制：

- **大幅 DRO 的星历传播存在问题**（e2m2e issue #324）。`design_orbit` 对大幅 DRO
  （距月几万公里）算出的星历在 1 个月内会漂到 20 万 km——这违背 DRO 的物理稳定性，
  是星历传播的 bug，不是 DRO 的性质。修复前，验证保持流程建议用紧凑 DRO（振幅约
  10000 km），或缩短传播时长。
- **Lissajous 的初猜在星历下发散**（e2m2e issue #323）。一阶线性初猜不足以在非线性
  CR3BP 里保持有界，需要高阶构造。修复前 Lissajous 的保持结果不可用。

这两项修复后，本表的数据才能在软件里复现。

## 参考文献

- Zhang & Wang 2022. *Performance analysis of impulsive station-keeping strategies for
  cis-lunar orbits with the ephemeris*. —— 全星历 DRO/NRHO/halo 保持策略对比，本文
  Δv 与漂移数据的主要来源。
- Minghu 等 2014. *Transfer to long term distant retrograde orbits around the moon*.
  —— 大幅 DRO 在太阳摄动下 300–700 天有界。
- Folta 等 2014. *Earth–moon libration point orbit stationkeeping: theory, modeling,
  and operations*. —— ARTEMIS 平动点轨道保持的工程实践（halo/NRHO 基准）。
- Guzzetti 等 2016. *Rapid trajectory design in the Earth–moon ephemeris system via an
  interactive catalog of periodic and quasi-periodic orbits*. —— 准周期轨道在星历
  模型里的有界性。
