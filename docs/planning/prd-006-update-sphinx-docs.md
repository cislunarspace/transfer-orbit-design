# PRD: 更新 Sphinx 文档以反映当前代码库状态

## 问题描述

README.md 的同步更新（PRD #128）已完成，但 Sphinx 文档（`docs/source/`）仍存在以下缺口：

1. **PRD toctree 缺失 PRD-005**：`docs/source/index.rst` 的 PRD 章节未引用 `narrative/prd-005-fix-ci-and-release`，导致该 PRD 无法从文档导航访问。
2. **Plot API 文档缺口**：轨道族绘图 API 文档仅覆盖 DRO、Halo、RO 三类，新增的 DPO、Lyapunov、Vertical、Axial、Butterfly、SPO、LPO、Tadpole、Horseshoe、Resonant 等 10 个轨道族的绘图脚本文档完全缺失。
3. **星历绘图文档部分缺失**：`plot/ephemeris/` 下已有 `plot_ephemeris_correction.rst` 和 `plot_halo_ephemeris_correction.rst`，但未创建 `plot_dro_ephemeris_correction.rst`（DRO 星历修正绘图）。

## 解决方案

对 Sphinx 文档进行结构性更新，填补 Plot API 和星历绘图文档缺口，并修复 toctree 引用：

1. 在 `docs/source/index.rst` 添加 `narrative/prd-005-fix-ci-and-release` 到 PRD toctree
2. 为 10 个新增轨道族创建 Plot API 文档（遵循现有 `dro/index.rst` + `plot_dro_family.rst` 模式）
3. 创建 DRO 星历绘图文档 `plot_dro_ephemeris_correction.rst`
4. 验证 Sphinx 构建无错误

## 用户故事

1. 作为文档读者，我希望通过 Sphinx 导航访问 PRD-005，以便完整了解 CI/Release 工作流的修复背景。
2. 作为新用户，我希望通过 Sphinx API 文档了解所有 13 类 CR3BP 轨道族的绘图脚本，以便学习如何使用绘图功能。
3. 作为开发者，我希望 Plot API 文档覆盖所有轨道族绘图脚本，以便为新绘图功能编写文档时参考现有模式。
4. 作为星历转换用户，我希望 DRO 星历修正结果的可视化脚本有独立文档，以便理解绘图输出的含义。
5. 作为贡献者，我希望 Sphinx 构建无错误或警告，以便文档更新不影响 CI 状态。

## 实现决策

### 1. 更新 index.rst 的 PRD toctree

在 `docs/source/index.rst` 的 PRD 章节添加 `narrative/prd-005-fix-ci-and-release` 条目。

### 2. 创建 Plot API 文档

为以下 10 个轨道族创建绘图 API 文档（每个族一个目录）：

| 轨道族 | 需创建的文档 |
|--------|-------------|
| DPO | `plot/dpo/index.rst`, `plot/dpo/plot_dpo_family.rst` |
| Lyapunov | `plot/lyapunov/index.rst`, `plot/lyapunov/plot_lyapunov_family.rst` |
| Vertical | `plot/vertical/index.rst`, `plot/vertical/plot_vertical_family.rst` |
| Axial | `plot/axial/index.rst`, `plot/axial/plot_axial_family.rst` |
| Butterfly | `plot/butterfly/index.rst`, `plot/butterfly/plot_butterfly_family.rst` |
| SPO | `plot/spo/index.rst`, `plot/spo/plot_spo_family.rst` |
| LPO | `plot/lpo/index.rst`, `plot/lpo/plot_lpo_family.rst` |
| Tadpole | `plot/tadpole/index.rst`, `plot/tadpole/plot_tadpole_family.rst` |
| Horseshoe | `plot/horseshoe/index.rst`, `plot/horseshoe/plot_horseshoe_family.rst` |
| Resonant | `plot/resonant/index.rst`, `plot/resonant/plot_resonant_family.rst` |

### 3. 创建 DRO 星历绘图文档

在 `docs/source/tod/plot/ephemeris/` 下新增 `plot_dro_ephemeris_correction.rst`。

### 4. 更新 plot/index.rst

在 `tod/plot/index.rst` 的 toctree 中添加新创建的轨道族绘图目录。

### 5. 术语规范

- **轨道族术语**：使用 `CONTEXT.md` 中定义的 13 族标准名称（DRO、DPO、Halo、Lyapunov、Vertical、Axial、Butterfly、SPO、LPO、Tadpole、Horseshoe、Resonant）。
- **RST 文件模式**：参考 `docs/source/tod/plot/dro/` 的现有结构。
- **不修改业务代码**：本次仅更新 RST 文档文件。

## 测试决策

- **构建验证**：运行 `sphinx-build -b html docs/source docs/build/html`，确认无致命错误（ERROR 不可接受，WARNING 可接受）。
- **链接检查**：Sphinx 自动检查内部链接完整性。
- **格式一致性**：所有新增 RST 文件遵循现有格式（toctree、autodoc 指令）。
- **不新增自动化测试**：纯文档变更。

## 不在范围内

- 不修改任何 `.py` 脚本逻辑或 docstring
- 不创建 `gui/scripts/` 下的绘图脚本文档（GUI 层文档结构待后续评估）
- 不更新 `narrative/readme.md`（已由 PRD-128 覆盖）
- 不构建或部署文档站点（仅本地验证构建）
- 不修改 `conf.py` 配置
- 不添加截图或图片资源

## 补充说明

- Plot API 文档的结构与 `docs/source/tod/generates/cr3bp/` 类似，可参考 `dpo/index.rst` 和 `dpo/generate_dpo_family.rst` 作为新增轨道族绘图文档的模板。
- `FamilyPlotOrchestrator` 是各轨道族绘图脚本的统一入口点，RST 文档应反映此架构模式。
- 新增的 10 个轨道族绘图文档可以批量创建，遵循统一模式以保持可维护性。
- GitHub Issue: #130