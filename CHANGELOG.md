# 更新日志

## 未发布

### 变更

- README 安装章节对照 e2m2e v5.3.0 更新：补充 PyPI 可选安装方式（`uv add e2m2e`，默认仍为本地 editable 联调）；SPICE kernels 改指 GitHub Release `kernels-v1` 打包下载，内核清单更新为 9 个；补充 e2m2e 在线文档链接。
- Sphinx 文档删除 `narrative/context`、`narrative/domain` 两个壳页面（被 include 的 CONTEXT.md、docs/domain.md 已移出 git 跟踪）。
- AI 工作文档移出 git 跟踪、本地保留：`AGENTS.md`、`CLAUDE.md`、`CONTEXT.md`、`docs/agents/`、`docs/domain.md`、`docs/issue-tracker.md`、`docs/triage-labels.md`、`docs/adr/decision-map-context-revision.md`、`.reasonix/`，并加入 `.gitignore`。

## 2.1.0 (2026-07-10)

随 e2m2e v5.3.0 上游变更同步适配，并在项目内重建 GEO/LEO 圆轨道几何能力。

### 新增

- `tod/commons/orbits.py`：GEO/LEO 圆轨道几何工具模块。因 e2m2e 误删 `e2m2e.orbits` 包（tod 13 个文件依赖它），在 tod 内重建——移植原 geo/leo 的纯几何函数，复用 `tod.commons.constants` 的归一化常量。同时整合去重了项目内 4 处 `compute_departure_velocity` 重复副本，全仓现仅 1 个定义。

### 变更

- 适配 e2m2e v5.3.0 破坏性变更：
  - `SynodicJ2000Transformation` → `SynodicJ2000System`（6 文件改名，API 兼容）。
  - `EphemerisDynamics` 不再从 `e2m2e.core` 公开导出，改从 `e2m2e.core.ephemeris_dynamics` 导入。
  - 13 个文件的 `from e2m2e.orbits.geo/leo import` → `from tod.commons.orbits import`。

### 修复

- `tests/tod/gui/test_script_registry.py` 漏 `import pytest`（`pytest.skip` 报 `NameError`）。
- `tests/tod/gui/conftest.py` 的 `qapp` fixture 创建 `QApplication` 前未设 `AA_ShareOpenGLContexts`，导致 `test_doc_window_import_order` 全套跑时 `import QtWebEngineWidgets` 报 `ImportError`。与 `tod.gui.main` 对齐，在模块顶部设此属性。

### 验证

- 全套测试 1156 passed, 0 failed（适配前因 e2m2e.orbits 断裂导致 23 failed + 3 collection error）。

## 2.0.0 (2026-06-19)

这个版本把脚本注册方式从集中式改为由实现脚本自声明、扫描器自动发现，同时补全了地月转移的星历转换链路，因此升级为主版本。

### 新增

- DRO→GEO 转移轨迹的星历转换脚本，以及一个通用星历转换 CLI，用于把 CR3BP 设计结果接入 N 体星历动力学。
- DRO→GEO 搜索与绘图脚本支持论文版配图，并可通过 `--caption` 添加图注。
- PyQt6 GUI 的脚本扫描器，自动从 `tod/generates/`、`tod/plot/`、`tod/transfers/` 加载脚本底部的 `SCRIPT_ENTRY`。

### 变更

- 项目描述更新为“地月空间转移轨道设计与分析脚本工具集，提供 CR3BP 轨道生成、转移设计、绘图和星历转换能力”。
- `SCRIPT_ENTRY` 注册机制重构：原来由单一文件集中维护注册信息，现在由各实现脚本底部声明，扫描器按路径哈希生成唯一模块名加载，避免同名脚本冲突。
- 随 e2m2e 上游重构同步更新依赖路径与导入方式。

### 修复

- QtWebEngine OpenGL 上下文初始化失败。
- 星历转换脚本中坐标、时间与状态索引的处理错误。
- 测试断言使用 `assertRaises` 掩盖真实异常类型的问题。
- 扫描器将“模块加载失败”与“模块未声明 SCRIPT_ENTRY”混为一谈的问题，并为加载失败补充日志。

### 文档

- 新增 ADR-0005，说明 `SCRIPT_ENTRY` 注册机制的设计决策。
- 更新 `CONTEXT.md`，补充星历转换领域术语与 Phase 3 上下文。
- 将 `CLAUDE.md` 与 `docs` 中的英文内容翻译为中文。
- 更新 README 星历转换章节。
