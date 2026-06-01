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

- `tod/gui/scripts/_registry.py` 中 `_ScanEntry` 是 `ScriptEntry` 的运行时代理，避免在扫描阶段触发重型依赖（e2m2e）。PyQt6 信号类型声明为 `ScriptEntry`，但运行时实际传入 `_ScanEntry`，需注意类型兼容性。

## 交流语言

与用户使用**中文**交流。

## Agent skills

### Issue tracker

Issues are tracked on GitHub (`cislunarspace/transfer-orbit-design`), using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
