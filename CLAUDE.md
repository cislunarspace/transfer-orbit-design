# Transfer Orbit Design

## 项目概述

Transfer Orbit Design 是一个轨道设计工具，提供 CR3BP 轨道生成、转换、绘图和星历转换等功能，带有 PyQt6 GUI 界面。

## 开发环境

- **包管理器**: uv — 所有运行和调试命令必须通过 `uv run` 执行
- **启动 GUI**: `uv run python -m tod.gui.main`
- **运行测试**: `uv run pytest`
- **运行单脚本**: `uv run python <script_path>`
- **Python 版本**: 参见 `pyproject.toml` 中的 `requires-python`

## 架构要点

- 每个可运行脚本底部声明 `SCRIPT_ENTRY = ScriptEntry(...)`，描述该脚本在 GUI 中的元数据。`tod/gui/scripts/_registry.py` 中的扫描器从实现目录（`tod/generates/`、`tod/plot/`、`tod/transfers/`）发现并加载这些注册信息。`_ScanEntry` 是 `ScriptEntry` 的运行时代理；PyQt6 信号类型声明为 `ScriptEntry`，但运行时实际传入 `_ScanEntry`，需注意类型兼容性。

## 交流语言

始终使用中文与用户交流。代码、commit message、PR 描述等技术输出也用中文。

## 写作要求

所有面向人读的文本——注释、CONTEXT.md、ADR、issue 评论、PR 描述、agent brief、triage notes、Sphinx 文档、Agent 回复——遵守以下原则：

- **善于总结材料**：材料弄全弄准，去粗取精、去伪存真、由此及彼、由表及里，反映事物本质；不堆砌细节、不拼凑清单。
- **不用夸大的修饰词**：不写"权威""强大""完整""单一事实来源"之类的修饰，它们减损力量。
- **注意词语的逻辑界限**：相邻概念要划清，不混用、不模糊。
- **废话应当尽量除去**。
- **通俗、亲切，由小讲到大，由近讲到远，引人入胜**：先讲读者已知／当前的事物，再推到陌生／抽象的；忌一上来就宏大叙事或先搬死人、外国人。
- **与读者完全平等**：靠分析说服，不要装腔作势来吓人；老老实实办事。

## 构建

## Agent 技能

### Issue 跟踪

Issue 在 GitHub（`cislunarspace/transfer-orbit-design`）上跟踪，使用 `gh` CLI。详见 `docs/agents/issue-tracker.md`。

### Triage 标签

五个规范 triage 标签（`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`）。详见 `docs/agents/triage-labels.md`。

### 领域文档

单上下文布局：仓库根目录下一个 `CONTEXT.md` 加 `docs/adr/`。详见 `docs/agents/domain.md`。
