# ADR-0002: DRO 参考初值 GUI v1

> **历史参考**：本篇记录旧 GUI（`tod/gui/`）时代的决策，已被 [ADR-0007](0007-big-bang-gui-replacement.md)（大爆炸替换）与 [ADR-0014](0014-migrate-ui-to-tauri.md)（UI 迁移到 Tauri）取代，仅作历史参考，不再指导现行实现。

## 状态

已接受

## 上下文

项目已经将 CR3BP raw xlsx catalog 纳入仓库，并提供 importer 将 raw workbook 规范化为 normalized catalog。DRO single-orbit Generate 已经有手动初值路径，也已有初步 catalog seed propagation 能力。用户需要在 GUI 的 Generate 脚本中增加 catalog 初值选项：选择 catalog 中的初值，直接按 catalog 中记录的周期外推，生成现有 plot 流程可读取的 Orbit JSON。

约束条件：

- v1 只接入 **DRO single-orbit Generate**，不扩大到其它 CR3BP orbit family，也不改 family generation。
- Catalog 模式使用 catalog state 和 catalog period 直接外推，不做 differential correction，也不重新计算周期。
- GUI 默认行为必须保持现有手动 DRO Generate 体验不变。
- Normalized catalog 是 raw xlsx 的派生产物，可能不存在；GUI/CLI 需要能按需从 tracked raw xlsx 生成。
- GUI 的脚本扫描阶段必须保持轻量，不能在 `SCRIPT_ENTRY` 扫描阶段触发 catalog/importer 等重型加载。

## 决策

采用 DRO Generate 内嵌 catalog seed 模式，而不是新增独立 Generate from Catalog 脚本。GUI 增加可配置的 `Cr3bpCatalogSeedSelector`，v1 只配置 `orbit_type="dro"`。该 selector 负责参考初值模式 UI、按参考记录编号搜索、轻量详情 preview、Jacobi 输入和校验；运行时仍输出 ordinary CLI args，交给既有 run orchestrator，不改变脚本执行模型。

用户界面术语以 `CONTEXT.md` 为准：Reference Catalog 面向用户称为 **参考数据集**，catalog seed 面向用户称为 **参考初值**，Seed ID 面向用户称为 **参考记录编号**；`Seed ID`、`Catalog mode` 等仅作为代码/CLI/ADR 历史术语使用。

### 选择模式

参考初值模式提供两种显式选择方式：

1. **按参考记录编号选择**：用户通过可搜索下拉选择精确 `orbit_id`。
2. **按 Jacobi 常数匹配**：用户输入目标 Jacobi，CLI 在 DRO 参考数据集中选择最近参考初值。

按 Jacobi 常数匹配 v1 不做实时 preview。运行日志和输出 metadata 必须记录目标 Jacobi、matched seed、matched Jacobi 和 Jacobi delta。默认无 hard tolerance；如果用户填写 tolerance，则启用 strict tolerance，超过容差时报错。

### GUI 行为

DRO Generate GUI 新增 Use Reference Initial Condition checkbox，默认关闭。

- checkbox 关闭时，manual `x0/vy0/period` 控件可编辑，参考初值 selector 禁用。
- checkbox 开启时，manual `x0/vy0/period` 控件禁用，参考初值 selector 启用。
- 按参考记录编号选择模式显示可搜索下拉，一次性加载 DRO records，并显示轻量详情 preview：参考记录编号、Jacobi、period、state、source file、source row。
- 按 Jacobi 常数匹配模式只显示输入和可选 tolerance，不做实时最近邻 preview。

参考数据集按需 lazy normalized catalog 加载。normalized catalog 缺失时，首次需要参考数据时从 tracked raw xlsx 懒构建。该加载不得发生在 `SCRIPT_ENTRY` 扫描阶段。

### CLI 互斥和参数

CLI 保留手动模式和参考初值模式，但执行 **manual/reference mutual exclusion**：

- 手动模式使用业务默认或显式 `x0/vy0/period`，走原 fixed-period differential correction。
- 参考初值模式使用参考记录编号或 Jacobi selector，直接 propagation。
- 按参考记录编号选择、按 Jacobi 常数匹配、显式 manual `x0/vy0/period` 三类输入互斥。
- 未显式传入的业务默认值不参与冲突判断；因此 manual 默认值应位于业务层常量或等价解析后逻辑，而不是让 argparse 默认值伪装成用户显式输入。

参考初值 propagation 新增：

- `period multiplier`：默认 `1.0`，必须大于 0。
- `num points`：默认 `1000`，高级参数，范围 `2..100000`。

### 传播和输出

参考初值模式使用 catalog initial state 和 catalog period，固定数值积分契约：

- integrator: `DOP853`
- `rtol=atol=1e-12`
- duration = catalog period × period multiplier
- samples = num points
- no differential correction

输出仍是 plot-compatible Orbit JSON。Orbit body 保存外推 trajectory 和 times。metadata 保存完整 provenance，至少包括：

- selection mode
- reference record id / matched reference record id
- catalog initial state
- catalog period
- source file / source row
- requested Jacobi、matched Jacobi、Jacobi delta、tolerance（Jacobi 模式）
- period multiplier
- num points
- integrator / rtol / atol
- raw/normalized catalog provenance

参考初值输出文件名应体现 DRO reference catalog 来源，并对 reference record id 中的文件名不安全字符做 sanitize，避免与手动 `dro_<timestamp>.json` 混淆。

## 后果

### 正面

- DRO 参考初值路径和手动 DRO Generate 路径语义清晰分离。
- GUI 用户可以通过参考记录编号精确选择，也可以通过 Jacobi 常数匹配探索。
- 输出 JSON 保持 plot 兼容，同时 metadata 足够复现实验和排查 catalog 来源。
- 通用 `Cr3bpCatalogSeedSelector` 未来可扩展到其它 CR3BP orbit type，但 v1 不承担其它轨道族语义。

### 负面

- 需要在现有 CLI 参数处理中区分业务默认值和用户显式 manual 输入。
- GUI 参数面板需要接入一个专用 selector，而不是只靠现有普通 CLI 参数控件。
- Seed ID 下拉一次性加载约一万条 DRO records，v1 接受该复杂度；后续如卡顿再引入分页或虚拟列表。

## 非目标

- v1 不支持其它 CR3BP orbit family。
- v1 不接入 family generation。
- v1 不做完整 catalog table/browser。
- v1 不做 Jacobi 实时 nearest-neighbor preview。
- v1 不暴露 integrator、rtol、atol 参数。