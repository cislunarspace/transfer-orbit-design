# 更新日志

## 3.0.0 (2026-08-05)

本版本主线是 **GUI 架构重写**：把脚本任务范式整体重写为 Project/Artifact 数据模型架构（`src/` 四层），轨道设计与轨道保持经 QThread 直接调用 e2m2e 算法层，结果以 JSON+NPZ 双文件持久化并支持启动扫描恢复。

### 新增

- **src/ 四层架构 GUI**：`src/model`（Project/Artifact 数据模型）、`src/engine`（FacadeBridge 薄封装 + QThread worker + 结果持久化）、`src/view`（内嵌 matplotlib 画布、项目树、Pydantic 自动参数面板、日志）、`src/app`（三栏主窗口组装）（1400a90）。
- **两个启用工具**：轨道设计（`design_orbit`）与轨道保持（`control_orbit`，蒙特卡洛仿真），经 `TOOL_REGISTRY` 注册；轨道族生成、稳定性分析为灰显占位（8359419、0060c73）。
- **可视化**：内嵌 matplotlib 画布，支持 3D/XY/XZ/YZ 投影切换、地月天体与 L1–L5 平动点图层开关、多轨道叠加渲染（d362edf、34f413d）。
- **Artifact 持久化闭环**：结果以 `dro_<ts>.json`（标量元数据）+ `.npz`（states/times/ephemeris 数组）双文件落盘，启动时扫描 `output/` 重建 Project，NPZ 数组懒加载（9121cd0、ea8e5e0、db05f74）。
- **Pydantic 自动参数面板**：参数面板由工具绑定的 Request 模型动态生成（1e772f7）；e2m2e 异常经 `translate_exception` 翻译为结构化错误（8359419）。
- **项目树右键菜单**：右键删除 Artifact、从树直接触发轨道保持（#340）（0060c73）。

### 变更

- **打包切新 GUI**：PyInstaller spec 入口从 `tod.gui.main` 改为 `src.app.main`，datas 收集 `src/` 取代 `tod/`，hiddenimports 补 `e2m2e.algorithm.station_keeping`。
- **README 重写**：README.md / README.en.md 只描述新 GUI（`uv run python -m src.app.main`），移除旧 GUI 入口与 `gui_defaults.json` 语言切换说明；CLI 脚本工作流保留。
- **CONTEXT.md 恢复并更新**：从 git 历史恢复，更新 GUI 相关术语（工具注册、任务范式、设置/主题、图层/标注）以对齐新 GUI。
- 适配 e2m2e v5.4 迁移（96439fc）；新 GUI 架构设计文档与可运行原型（444f0b0）。

### 修复

- 测试隔离：MainWindow 初始化不再读取真实 `output/` 目录（db05f74）。

### 验证

- 全套测试 `pytest tests/ -m "not spice"` 1290 passed, 5 skipped, 33 deselected；ruff（src/）与 pyright 0 error。

## 2.2.0 (2026-07-29)

本版本主线是**可分发性**：PyInstaller 打包的 Windows 便携包首次真正可用（此前 exe 检测不到任何脚本），并打通了 SPICE 内核免配置分发；同时落地 DRO→GEO 星历修正闭环与配套分析脚本，完成一轮大规模重构与类型修复。

### 新增

- **Windows 便携包（PyInstaller 扁平布局）**：`tod/` 源码、`pyproject.toml`、`data/cr3bp_data` 种子数据与 exe 平级打包，脚本扫描（33 个注册脚本）、子进程执行、multiprocessing spawn 在 frozen 环境全部打通；消除 onefile/onedir 双份产物（去掉 286 MB 冗余）。
- **SPICE 内核免配置**：exe 旁存在 `kernels/` 目录时自动设为 `SPICE_KERNEL_DIR`（显式环境变量优先）；内核与 MICE 工具包经独立 `spice-data-v1` release 分发。
- DRO→GEO 转移星历修正闭环：分段打靶拼接法（8a495bf）；DRO→GEO 小推力转移简单验证（ae279aa）。
- DRO→GEO 期刊仿真分析脚本（仿真 4/5/10）（f3e9d69）。
- i18n：`cli_chip_params` 翻译支持（#284），`cli_params` 与 `group_label` 英文翻译补齐（#283）。
- 参数参考文档（#282）。

### 变更

- PyInstaller spec 移至 `packaging/`；`.vscode/`、`MagicMock/`、`.zcode/`、`.mimocode/` 及 AI 工作文档（AGENTS.md、CONTEXT.md 等）移出 git 跟踪。
- README 多语言化（新增 README.en.md）并补齐脚本清单；安装指引对照 e2m2e v5.3.0 更新，SPICE kernels 改指 GitHub Release 打包下载。
- Sphinx 文档删除 `narrative/context`、`narrative/domain` 两个失效壳页面。
- 大规模重构：脚本注册表统一为 `ScriptEntry` 单一直接产出；`EphemerisConversionAdapter` 类取代闭包工厂；MainWindow mixin 覆盖改为钩子回调；ParamValueStore 拆分三 store；plot config/orchestrator 按关注点拆分；`cli/` → `commons/` 命名重组；删除 CR3BP 8 个 stub 族与两个浅模块；GEO/LEO 返回类型统一为 `Orbit`。
- GUI 亮暗双主题 QSS 重写，统一设计语言。

### 修复

- **frozen exe stdout/stderr 退化为 GBK + 块缓冲**（PyInstaller 嵌入式解释器不响应 `PYTHONUNBUFFERED`/`PYTHONIOENCODING`）：GUI 长任务无流式输出、中文全乱码。改为 frozen 初始化时强制 utf-8 + 行缓冲（6b17ba3）。
- **multiprocessing spawn worker 反序列化失败**：CPython 在 win32 下把 frozen 视为 WINEXE，不向子进程传 `init_main_from_path`；解释器分支显式置回 False（34a0e60）。
- windowed spawn 子进程 `sys.stdout/stderr` 为 None 导致 bootstrap 二次崩溃：补 devnull 兜底。
- pyright 在 CI 严格模式下累计 40+ 处类型错误（50871a4、b7a41d4、f46e9a2、e26f04a）。
- registry fixture 截断 sys.path 导致 e2m2e 不可导入（0681c8a）；33 个 halo ephemeris 集成测试失败（3d457f7）；`gui_defaults` 测试缺键失败（0979c8e）。
- 批量修复 review 问题 #295、#297、#298、#302、#304、#305、#312–#319。

### 验证

- frozen 包内实测：33 个脚本扫描发现、ProcessPoolExecutor spawn、SPICE 星历查询（de430.bsp + naif0011.tls）、stdout utf-8 行缓冲流式输出、显式 `SPICE_KERNEL_DIR` 优先级。
- 全套测试 1098 passed, 5 skipped；pyright 0 errors；CI（ubuntu/windows/macOS × Python 3.13 + docs）全绿。

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
