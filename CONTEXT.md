# Transfer Orbit Design

本上下文描述 CR3BP 轨道转换到星历模型时使用的领域语言，确保单条轨道与轨道族批处理的语义一致。

## Language

**单条轨道**:
一个 CR3BP 周期轨道对象，通常由顶层 `states`、`times` 和 `period` 描述；也可由用户通过索引从 **轨道族** 中明确选取。
_Avoid_: 单个 JSON、种子轨道（除非确实用于延拓）

**轨道族**:
按延拓顺序排列的一组 CR3BP 周期轨道，通常由顶层 `orbits` 列表描述。
_Avoid_: 采样轨道、代表性轨道集

**CR3BP 周期轨道族类型**:

| 族名 | 英文名 | 相关平动点 | 物理特征 |
|------|--------|------------|----------|
| Lyapunov | Lyapunov Family | L1–L5 | 平面周期轨道，沿共线平动点主轴振荡 |
| Halo | Halo Family (North/South/Near-Rectilinear) | L1, L2, L3 | 三维周期轨道，含近直线晕轨道 (NRHO) |
| Vertical | Vertical Family | L1–L5 | 垂直方向振荡的周期轨道 |
| Axial | Axial Family | L1–L5 | 沿平动点轴向的周期轨道 |
| Butterfly | Butterfly Family | L1–L2 | 连接两个共线平动点的对称轨道 |
| DRO | Distant Retrograde Orbit | secondary | 围绕次天体的远程逆行轨道 |
| DPO | Direct Prograde Orbit | secondary | 围绕次天体的顺行轨道 |
| SPO | Short Period Orbit | L4, L5 | 三角平动点附近的短周期轨道（Lyapunov 族的特殊分支） |
| LPO | Long Period Orbit | L4, L5 | 三角平动点附近的长周期轨道（Lyapunov 族的特殊分支） |
| Tadpole | Tadpole Orbits | L4, L5 | 围绕单个三角平动点的蝌蚪形轨道 |
| Horseshoe | Horseshoe Orbits | L4–L5 | 跨越两个三角平动点的马蹄形轨道 |
| Resonant | Resonant Orbits (3:n) | 全系统 | 满足 m:n 共振比例的周期轨道；3:1 / 3:2 / ARO / RRO 均属此类 |

**轨道族转换**:
将轨道族内每条轨道逐条独立转换到星历模型；单条转换失败时默认记录该项并继续处理其余轨道，可由用户选择快速失败。
_Avoid_: 沿族递推、只转换里程碑轨道

**星历转换输入文件**:
用户显式提供给转换脚本的 CR3BP 轨道 JSON 文件；脚本不应隐式选择最新文件。
_Avoid_: 最新输出文件、默认输入文件

**轨道族转换结果**:
一次 **轨道族转换** 产生的单个汇总 JSON，包含每条轨道的转换状态、诊断信息和成功时的星历轨迹。
_Avoid_: 每轨道分散输出、只保存成功项

**星历转换方法**:
转换脚本用于修正星历模型 patch points 的算法选择；所有脚本都允许用户选择，默认使用 `two_level`。
_Avoid_: 固定方法、按文件硬编码方法

**参考历元**:
用户为星历转换显式提供的 UTC 历元，用于将 CR3BP 轨道映射到 J2000 星历时间。
_Avoid_: 隐式默认历元、脚本内固定历元

## Relationships

- 一个 **轨道族** 包含一条或多条 **单条轨道**。
- **轨道族转换** 对每条 **单条轨道** 执行独立的星历模型转换。
- 每次转换从一个 **星历转换输入文件** 加载 **单条轨道** 或 **轨道族**。
- 每次转换使用一个 **星历转换方法** 修正 patch points。
- 每次转换必须由用户提供一个 **参考历元**。
- 一次 **轨道族转换** 产生一个 **轨道族转换结果**。
- 共振比参数 `--ratio` 决定 **Resonant** 轨道族的具体共振形式（如 3:1、3:2）。

## Example dialogue

> **Dev:** “DRO 轨道族转换时，第二条轨道要复用第一条已收敛的星历解吗？”
> **Domain expert:** “不需要；族内每条轨道逐条独立转换，失败项记录后继续下一条。”

## Flagged ambiguities

- “一个轨道族转换”曾可能表示沿族递推或只转换代表性轨道；已解析为逐条独立转换完整族。
- DRO（表内原始含义 Direct Prograde & Retrograde Orbits）与项目中已有的 Distant Retrograde Orbit 重名；已拆分为 DRO（Distant Retrograde Orbit）和 DPO（Direct Prograde Orbit）两个独立族。
- RO（Retrograde Orbits）原含 3:1 / 3:2 / ARO / RRO 四套脚本；已统一为 **Resonant** 族，通过 `--ratio` 参数区分具体共振比。
- SPO（Short Period Orbit）和 LPO（Long Period Orbit）原合并为 Short & Long Period Orbits；已拆分为两个独立族。
