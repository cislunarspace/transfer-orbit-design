# Transfer Orbit Design

本上下文描述 CR3BP 轨道转换到星历模型时使用的领域语言，确保单条轨道与轨道族批处理的语义一致。

此外，自 ADR-0001 起，本文档同时定义软件界面国际化相关的领域语言。

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
| Halo | Halo Family (North/South/Near-Rectilinear) | L1, L2 | 三维周期轨道，含近直线晕轨道 (NRHO)。L3 处无经典 Halo 轨道族。 |
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

## UI Language（界面语言）

> 自 ADR-0001 起，软件支持中英文界面切换。以下术语定义国际化方案中的核心概念。

**界面语言 (UI Language)**:
软件 GUI 中所有用户可见文本的显示语言。当前支持 `zh`（中文，默认）和 `en`（英文），通过 `gui_defaults.json` 中的 `”language”` 配置项持久化。切换后需重启生效。
_Avoid_: locale（包含区域格式，本项目仅区分语言）、实时热切换

**源语言 (Source Language)**:
翻译系统中的原始文本语言。本项目源语言为**中文**，代码中所有需翻译的字符串均以中文编写（通过 `self.tr(“...”)` 包裹），英文版通过翻译文件映射获得。
_Avoid_: 英文作为源语言（与常见惯例相反，但符合本项目历史）

**翻译回退 (Translation Fallback)**:
当目标语言的翻译条目缺失时，显示源语言（中文）文本的行为。适用于 `.qm` 翻译文件和 JSON 翻译表两者。
_Avoid_: 显示占位符、显示空白、抛出错误

**GUI 翻译文件 (GUI Translation File)**:
PyQt6 `QTranslator` 使用的二进制翻译文件，由 `.ts` XML 源文件经 `lrelease6` 编译为 `.qm`。路径为 `tod/gui/i18n/gui.<lang>.qm`。启动时由 `MainWindow` 按当前界面语言加载。
_Avoid_: 运行时手动替换每个控件的文本

**脚本翻译表 (Script Translation Table)**:
存储脚本描述、long_description、cli_params help 文本翻译的 JSON 文件。路径为 `tod/gui/i18n/scripts.<lang>.json`，按脚本名结构化：`{“script_name”: {“description”: “...”, “long_description”: “...”, “cli_params”: {“param_name”: “...”}}}`。
_Avoid_: 以原始中文为 key 的扁平字典（易因原文修改而失效）

**占位符文本 (Placeholder Text)**:
动态文本中用于运行时填充的标记，Qt 格式为 `%1`、`%2` 等。替代 `f-string` 和 `.format()`，以确保 `pylupdate6` 能正确提取整句模板。
_Avoid_: f-string 拼接翻译片段、运行时字符串拼接后传入 `tr()`
