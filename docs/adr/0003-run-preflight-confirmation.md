# ADR-0003: GUI 运行前确认集中化

## 状态

已接受

## 上下文

`CONTEXT.md` 对 GUI 的当前选择文件批量运行覆盖结果有明确约束：支持文件输入的工具可以使用文件树里的当前选择文件，但运行前必须让用户看见并确认；运行前确认用于避免隐式输入、意外批量运行或覆盖结果；发生覆盖结果前，GUI 应显示将被覆盖的文件。

实现层原有三处分散的事实：

1. `_run_from_tab` 在参数校验后直接 `build_run_specs` + `dispatch`（无确认环节）
2. `file_arg` 在 MainWindow 层静默构造并直接前置到 `extra_args`
3. chip 多选通过 `itertools.product` 展开为多个 RunSpec，但用户点击运行前看不到将创建 N 个任务的确认摘要

修复目标：在 dispatch 前集中展示工具名、当前选择文件、任务数量/分组、覆盖目标；用户取消时 0 个 Job 创建。

## 决策

### 1. 引入 `RunPlan` 数据结构 + `RunConfirmationDialog` 独立类

不在 `_run_from_tab` 内直接弹 `QMessageBox`。`RunOrchestrator.build_run_plan` 在 `build_run_specs` 之上叠加覆盖检测与 chip 分组，返回不可变 `RunPlan`；`RunConfirmationDialog.show_and_confirm(plan, parent) -> bool` 是 UI 入口，与 orchestrator 完全解耦。

`RunPlan` / `OverwriteTarget` / `ChipGroup` 全部 `frozen=True` dataclass。`RunPlan` 包含 `entry: ScriptEntry`，避免 dialog 同时依赖 plan + tab。

### 2. `CliParam.kind` 声明式字段

orchestrator 识别输出文件参数不靠 hardcode `"--output-file"` 字符串。新增 `kind: str = ""` 字段；`"file_output"` 表示该参数的值是输出目标。6 处 `--output-file` 注册点加 `kind="file_output"`。

未来若脚本同时支持 `--log-file`、`--export-image` 等输出 flag，只需在注册点标 `kind="file_output"`，orchestrator 零改动。

### 3. `dispatch` 签名保持不变

`build_run_specs` 与 `dispatch` 保留原签名 + 行为；`build_run_plan` 是高层包装，**不**取代 `build_run_specs`。现有 11 个 `test_run_orchestrator.py` 测试在 PR1 后继续 100% 通过。

覆盖目标路径解析：`(repo_root / p).expanduser().is_file()`，不 `resolve()`，与子进程 cwd 行为一致。`--output-file` 为空字符串/纯空白视为未指定输出文件，触发无输出文件参数提示而非覆盖目标。

## 后果

### 正面

- GUI 运行路径在 dispatch 前有显式确认环节，与 `CONTEXT.md` 领域约束一致
- 覆盖检测、chip 分组逻辑集中在 `RunOrchestrator`，UI 端不持有算法
- `RunPlan` frozen dataclass 让 dialog 单元测试可独立进行（widget tree 文本断言）
- 现有 GUI 测试套件（PR1 后 461+8 + 8 个新测试）零回归

### 负面

- `MainWindow._run_from_tab` 路径多了一处计划构造与确认回调，调用方需使用 build_run_plan 替代 build_run_specs 入口
- `RunConfirmationDialog` 是新组件，未来如果 dialog 还要支持更复杂的 spec 编辑，会变成新的耦合点

### 后续

- `_confirm_run_provider` 注入点已就位，但目前没有调用方注入；保留以便未来按工具类别提供不同确认策略
- 按 Jacobi 常数匹配 + 批量展开场景的摘要可视化（如任务组下挂每个 Jacobi 值的预览）属后续 issue