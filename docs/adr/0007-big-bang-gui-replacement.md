# ADR 0007：大爆炸替换旧 GUI

**状态**：已接受
**日期**：2026-08-04
**关联**：ADR 0006（e2m2e GUI 前端定位）

## 背景

现有 GUI（`tod/gui/`）基于 mixin 架构：`MainWindow` 继承 `FileTreeMixin` + `JobPanelMixin` + `QMainWindow`。通过 QProcess 子进程运行脚本，文件浏览器手动刷新，参数面板从 SCRIPT_ENTRY 自动生成。

新 GUI 需要根本不同的架构：Project 数据模型、内嵌可视化、Facade 直调。两种架构差异太大，增量改造不可行。

## 决策

**大爆炸替换**：用新的四层架构（model/engine/view/app）完全替代旧的 `tod/gui/`。不做并行双模式，不做原地重构。

## 理由

1. **架构差异不可调和**：旧 GUI 的核心假设是脚本对应进程，新架构是 API 对应线程。这两个假设不兼容。
2. **mixin 限制**：`MainWindow` 的 mixin 链（FileTreeMixin → JobPanelMixin → QMainWindow）使得替换任一组件都需要重构整条继承链。
3. **SCRIPT_ENTRY 废弃**：旧 GUI 的参数面板生成依赖 SCRIPT_ENTRY 扫描，新 GUI 从 Pydantic 模型生成。机制完全不同。
4. **e2m2e_compat 不再需要**：新架构直接调用 e2m2e 的新 API 路径，不需要旧路径兼容层。

## 后果

### 正面

- 无技术债务继承
- 新架构干净，无 mixin 复杂度
- 代码量大幅减少（删除 40+ 脚本 + scripting 框架 + compat 层）

### 负面

- 过渡期旧功能不可用（直到新 GUI 覆盖对应能力）
- 一次性工作量大
- 需要重新实现文件发现、设置持久化等基础设施

## 过渡策略

1. 原型阶段：在 `tod/gui/prototype/` 下验证新架构（已完成）
2. 实现阶段：在 `src/model/`、`src/engine/`、`src/view/`、`src/app/` 下实现最终代码（src layout）
3. 切换：删除 `tod/gui/`，更新 `pyproject.toml` 入口指向 `src.app.main`
4. 清理：删除 `tod/generates/`、`tod/transfers/`、`tod/scripting/`、`tod/commons/e2m2e_compat.py`
5. 收尾：`tod/commons/` 迁入 `src/commons/`，`tod/plot/` 提升为顶层 `plot/`