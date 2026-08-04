# ADR 0006：e2m2e GUI 前端定位

**状态**：已接受
**日期**：2026-08-04
**关联**：`docs/architecture/architecture.md`

## 背景

transfer-orbit-design（tod）最初是独立的轨道设计工具集，包含自己的生成脚本、转移搜索脚本、可视化脚本和 GUI。随着 e2m2e 的成熟，tod 的所有计算能力已被 e2m2e 覆盖。tod 的脚本层变成了 e2m2e 的薄封装 + argparse CLI + SCRIPT_ENTRY 元数据。

当前状态：tod 的 `generates/`、`transfers/`、`plot/` 目录中有 40+ 脚本，每个脚本内部 `import e2m2e` 调用算法。GUI 通过 QProcess 子进程运行这些脚本。e2m2e 兼容层（`e2m2e_compat.py`）维持旧 import 路径可用。

## 决策

tod 重新定位为 **e2m2e 的 GUI 前端**，职责仅限于：

1. 调用 e2m2e 能力（通过算法层 API 直调）
2. 管理计算产物（Project + Artifact 模型）
3. 可视化呈现（内嵌 matplotlib 画布）

删除 tod 中所有"搬运 e2m2e 能力"的脚本层（`generates/`、`transfers/`、`commons/e2m2e_compat.py`）。tod 不再有自己的 CLI 或命令行脚本——命令行用户直接使用 e2m2e 的 CLI。

## 理由

1. **消除双层封装**：当前 tod 脚本 = argparse + import e2m2e + 调用。这是纯粹的间接层，没有附加价值。
2. **单一事实来源**：算法逻辑只在 e2m2e 中维护，不在 tod 中复制。
3. **ADR 0014 结果**：e2m2e ADR 0014 已明确"transfer-orbit-design 保留独立仓库只留 GUI"。
4. **SCRIPT_ENTRY 废弃**：GUI 参数面板改为从 e2m2e Pydantic 模型自动生成，不再需要 CliParam 声明。

## 结果

- 删除 `tod/generates/`、`tod/transfers/`（含全部子目录）
- 删除 `tod/scripting/`（SCRIPT_ENTRY 机制）
- 删除 `tod/commons/e2m2e_compat.py`
- 核心代码迁入 `src/`（src layout）：`src/model/`、`src/engine/`、`src/view/`、`src/app/`、`src/commons/`
- `tod/plot/` 提升为顶层 `plot/`（独立绘图脚本，高级用户可直接使用）
- GUI 改为直接调用 e2m2e 算法层 API
