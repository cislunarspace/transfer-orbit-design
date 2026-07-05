# Decision Map: CONTEXT.md 周期性梳理

本地图跟踪 `CONTEXT.md` 领域语言与当前代码之间 ~70 项差异的解决进度。
每条 ticket 是一个独立决策点；解决的填入 Answer，未决的标明 Type 和依赖。

---

## #1: M1 — 任务状态 "成功" vs "已完成"

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 定义任务状态为"成功"，GUI 和 ADR-0004 显示"已完成"。怎么统一？

### Answer

改 CONTEXT.md 为"已完成"，与 GUI 对齐。内部枚举名 `JobStatus.SUCCESS` 不动——它是代码层实现细节，不归 CONTEXT.md 管。

---

## #2: M2 — 批量聚合状态粒度不足

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 只定义了"部分成功"一个聚合状态。代码有 6 种：运行中 / 全部完成 / 全部失败 / 部分完成 / 部分完成（含已停止）/ 已停止。怎么对齐？

### Answer

"部分成功"改名为"部分完成"，与 GUI 一致。补全 6 种聚合状态作为批量运行总体状态的取值集合：运行中 / 全部完成 / 全部失败 / 部分完成 / 部分完成（含已停止）/ 已停止。"部分完成（含已停止）"作为独立取值，注明它混入了用户主动停止的任务，与纯"部分完成"平级。

---

## #3: M3 — "运行组合" vs "任务计划"

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 定义"运行组合"，GUI 运行前确认对话框显示"任务计划"。怎么统一？

### Answer

两个都保留，分层定义。"运行组合"是参数配置概念（任务创建前的输入配置），保持不变。新增"任务计划"作为运行前确认的 GUI 展示概念——将一个或多个运行组合汇总展示给用户确认的区块名。

---

## #4: M4 — Halo 子类术语 "North/South" vs "Class I/Class II"

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 写 Halo 族为 "North/South"，GUI 显示"北族 (Class I) / 南族 (Class II)"。怎么统一？

### Answer

统一为"北族 / 南族"作为主术语。CONTEXT.md 轨道族表 Halo 行改为"(北族/南族)"，注明 Class I = 北族（z 轴正方向）、Class II = 南族（z 轴负方向）作为同义映射。英文 North/South 降为辅助说明。

---

## #5: M5 — 星历转换方法标签 "两级多重打靶" vs "双重"

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 写"两级多重打靶"，GUI 显示"双重"。怎么统一？

### Answer

两处都要改。

1. **CONTEXT.md 修正定义**：`two_level` 的实质是"先修正位置使位置约束满足，再进行第二阶段修正使位置和速度同时满足约束"。原文"先以粗调子问题快速逼近，再以精调子问题细化收敛"不准确——不是精度层级关系，而是修正对象的阶段递进。

2. **GUI 标签**："双重"改为"两阶段法"，贴合实质。

---

## #6: M6 — patch points 中英文混用

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 用英文"patch points"，GUI 用中文"拼接点数量"。是否统一为一个写法？

### Answer

保持英文 "patch points" 为 CONTEXT.md 主术语不变，在定义中注明 GUI 显示为"拼接点（数量）"作为界面别名。不改 GUI——中文界面上写"拼接点数量"合理，CONTEXT.md 作为领域语言文档保留英文原词。

---

## #7: 延拓子类型 (M7)

Blocked by: #4
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 只定义"延拓"，代码有两种子方法（自然延拓 / 伪弧长延拓）。是否在 CONTEXT.md 补充子类型？

### Answer

在"延拓"条目下补充两种子方法的简要定义：自然延拓 (natural)，沿参数方向逐步小步推进，每步做微分修正；伪弧长延拓 (pseudo_arclength)，以弧长为参数的延拓方法，能穿越转折点。

---

## #8: 共振轨道子类型 (M8, N18)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

RO 族通过 `--ratio` 区分 3:1 和 3:2，是否作为独立术语写入 CONTEXT.md？

### Answer

保持现状。CONTEXT.md 的 RO 表格行已写"通过 `--ratio` 区分 3:1 和 3:2"，不需要提升为独立条目——它们只是参数取值，不是两个不同的用户概念。

---

## #9: 转移设计子概念 (N1–N4, N8–N10)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

转移设计管线有两阶段（网格搜索 → NLP 优化），产出候选解 / 可行解 / 最优解，核心指标是 Δv。这些是否作为领域语言写入 CONTEXT.md？

### Answer

补充四个核心术语：
- **网格搜索**：转移设计第一阶段，枚举出发时刻与方向参数网格，逐点传播并筛选可行解
- **NLP 优化**：转移设计第二阶段，在可行解上做数值优化以最小化 Δv
- **可行解 / 最优解**：搜索产出的候选点 / 优化后收敛的解
- **Δv（速度增量）**：转移机动所需的速度变化量，是衡量转移代价的核心指标

碰撞检测、相交阈值、最小距离阈值等参数级细节归入 #18 讨论。

---

## #10: 转移管线方向 (M10, N11–N15)

Blocked by: #9
Type: Grilling
Status: ✅ 已解决

### Question

代码有 4 条子管线（DRO→GEO / DRO→RO / GEO→DRO / LEO→DRO），各有独立 GUI 分组。是否在 CONTEXT.md 补充？

### Answer

补充。在"转移设计"下列出 4 条管线方向，作为转移设计工具的子类别。同时补充"搜索结果 / 优化结果"作为转移设计的输出文件子类型。

---

## #11: 端点轨道 GEO / LEO (N16–N17)

Blocked by: #10
Type: Grilling
Status: ✅ 已解决

### Question

GEO 和 LEO 在转移设计中作为端点轨道，但不在 CR3BP 轨道族表内。是否写入 CONTEXT.md？以什么形式？

### Answer

补充。GEO（地球静止轨道）和 LEO（低地球轨道）作为转移设计的端点轨道写入 CONTEXT.md，放在转移设计相关概念下，不放入 CR3BP 轨道族表——它们不是 CR3BP 周期轨道族。

---

## #12: Jacobi 常数作为独立术语 (N20–N21)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

Jacobi 常数在代码中频繁出现（匹配、绘图、筛选），CONTEXT.md 只在"按 Jacobi 常数匹配"中间接提及。是否提升为独立术语？

### Answer

提升为独立术语。新增"Jacobi 常数"条目，说明是 CR3BP 中的守恒量，用于轨道筛选、参考初值匹配和稳定性分析。

---

## #13: 参考数据集 raw → normalized 两阶段 (M11, N22–N24)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

代码区分 raw XLSX 和 normalized 参考数据集，有自动构建管线。CONTEXT.md 只定义"参考数据集"，是否补充两阶段？

### Answer

补充。在"参考数据集"条目下说明两阶段：原始 XLSX 数据（raw）经预处理生成 normalized 参考数据集，工具默认使用 normalized。

---

## #14: 绘图显示设置粒度 (M9)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CONTEXT.md 只写"绘图字号"，代码有 7 种字号 + 天体图标缩放 + LP 标注字号。是否逐一列举还是保持概括？

### Answer

保持概括。CONTEXT.md 的"绘图显示设置"维持当前写法，不逐一列举各种字号和缩放。参数级细节归工具说明和设置界面。

---

## #15: 单位 VU / T_MOON (M19–M20, N46–N47)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

VU（速度单位）和 T_MOON 在代码中到处使用，CONTEXT.md 只有 DU/MU/TU。是否补充？

### Answer

补充两者。VU 是 CR3BP 无量纲化中的速度单位，与 DU/MU/TU 平级。T_MOON 是月球轨道周期，无量纲值为 2π。

---

## #16: 过时术语清理 (M12–M16)

Blocked by: —
Type: Research
Status: ✅ 已解决

### Question

失败项（M12）：per-orbit 失败项已无 GUI 呈现；NRHO（M13）：无 GUI 入口；PENDING（M14）：无代码路径发出；绘图与可视化（M15）：GUI 标签只写"绘图"；检查与分析（M16）：GUI 只有"交互检查"和"验证"。这些术语是删除、保留还是降级？

### Answer

全部保留。

- **失败项**：它是轨道族转换结果 JSON 里的结构，即使 GUI 没有专门展示也仍然存在。
- **NRHO**：在 Halo 族定义中作为物理特征描述提及，是领域知识。
- **PENDING/等待中**：ADR-0004 明确说已就位，待后续接入队列调度。
- **绘图与可视化 / 检查与分析**：CONTEXT.md 定义的是概括性用户目标类别，GUI 分组标签是当前实现的具体表面形式。CONTEXT.md 的上层概念比当前 GUI 标签更稳定，不改。

---

## #17: CLI flag 遗留 (M17–M18)

Blocked by: —
Type: Grilling
Status: ✅ 已解决

### Question

CLI 仍用 `--seed-id`，ADR-0002 说应面向用户称"参考记录编号"。是改 CLI flag 还是在 CONTEXT.md 注明映射？

### Answer

不改 CLI flag（改动面大、涉及向后兼容）。CONTEXT.md 在"按参考记录编号选择"条目中注明 CLI 参数为 `--seed-id`。

---

## #18: 参数级细节是否纳入 (Tier 3)

Blocked by: #9, #10, #14
Type: Grilling
Status: ✅ 已解决

### Question

DPI、仰角/方位角、投影平面、子采样种子、路径模式、并发上限等参数级概念。是否纳入 CONTEXT.md，还是归工具说明 / 帮助文档？

### Answer

不纳入 CONTEXT.md。这些是工具参数级细节，归工具说明和帮助文档。CONTEXT.md 只收结构性领域概念。
