# 更新日志

## Unreleased

3.1.2 之后的星历模型可视化改造：星历结果获得会合系（质心归一，自洽）/ 地心惯性系双视图与 GIF 动画导出，修复星历产物与地月标注的原点偏移，并为画布接入真物理时间轴。约定见 ADR 0013。

### 功能

- **星历模型坐标系切换与惯性系视图（#358 P1，93977fa）**：画布新增会合系 / 地心惯性系（GCRS）切换。惯性系视图以地球为原点、月球按 SPICE 真实轨迹移动、轨迹用 GCRS km、不画平动点；会合系维持 CR3BP 旋转系 + 地月 + L1–L5。脉动-旋转系为 cislunar 可视化主流（Folta 2022、Park 2025），瞬时平动点在该系与 CR3BP 几何一致（Boudad 2022）。
- **GIF 动画导出（#358 P2，93977fa）**：新增独立"导出动画"工具，按时间等分采样逐帧渲染、Pillow 合成 GIF（不依赖 ffmpeg）。支持累积 / 滑动窗口、UTC 帧时间戳、坐标系随当前视图。

### 修复

- **control_orbit 星历的原点偏移（#358 P0，d0e1449）**：受控星历的会合系位置是地心归一（月球 +1），画布标注按质心归一（月球 1−μ），相差 μ·DU ≈ 4690 km。提取时减 source_mu 对齐；同源 GCRS 位置 km 与由 UTC 重建的 ET 秒一并透传到画布接口，为惯性系视图与动画铺路。

## 3.1.2 (2026-08-08)

3.1.1 之后的 CI 修复补丁：修复 release 流程中 headless 环境的 GUI 测试崩溃。

### 修复

- **修复 release CI 的 headless 测试配置（88ae7f9）**：`release.yml` 的 test job 在 ubuntu-latest 跑 GUI 测试时，`tests/app/test_context_menu.py` 等处的 `qapp` fixture 直接 `QApplication([])`，无显示服务器即 SIGABRT（exit 134，第一个 GUI 测试就崩）。给 Run tests 步骤加 `env: QT_QPA_PLATFORM: offscreen`。本仓 `ci.yml` 只有 lint、无 test job，此缺陷一直未暴露，直到 v3.1.1 release 才触发。

## 3.1.1 (2026-08-08)

3.1.0 之后的小幅修订：GUI 默认 DRO 振幅调到典型中等量级，新增轨道保持专题文档，并修正随 e2m2e 改 PyPI 安装而过时的说明。

### 修复

- **GUI 默认 DRO 振幅 10000→60000 km（02e5bca）**：默认 10000 km 产出贴月的近月紧凑 DRO，在地月尺度画布上只是一个点；改到 60000 km（距月 5.4–6.6 万 km，ARTEMIS/Gateway 量级），打开即见典型中等 DRO。e2m2e 兜底仍为 10000（DFH 黄金样本）。文献里大幅 DRO 比小幅更稳（Zhang & Wang 2022：72000 km 年均保持 0.82 m/s vs 34000 km 1.96 m/s），选 60000 不牺牲稳定性。注：e2m2e 对大幅 DRO 的星历传播有 bug（cislunarspace/e2m2e#324），修复前该默认的星历会漂移；画布画 CR3BP 周期轨道，形状观察不受影响。

### 文档

- **新增轨道保持专题（fb85d1a）**：`docs/source/narrative/station-keeping.md` 给出 DRO/NRHO/halo/Lissajous 在真实星历里的稳定性差异与保持代价基准（Zhang & Wang 2022 全星历 2 年 Monte-Carlo）。如实标注当前软件限制（e2m2e#323 Lissajous 发散、#324 大幅 DRO 星历传播 bug），修复前哪些流程不可用。
- **修正 e2m2e 改 PyPI 安装后的过时描述（ad8edf4）**：README/README.en/architecture.md 删除「手动克隆 ../e2m2e + editable 安装 + 改 tool.uv.sources 路径」步骤，改为 PyPI 依赖（e2m2e>=5.6.0）由 `uv sync` 一并安装，补充 SPICE 内核自动探测说明。ADR 0012 增补「后续更新」：冻窗已随 5.6.0/5.6.1 根治，QMovie 缓解作废。

### 工程

- **修复 release CI 的 headless 测试配置**：`release.yml` 的 test job 在 ubuntu-latest 跑 GUI 测试时，`tests/app/test_context_menu.py` 等处的 `qapp` fixture 直接 `QApplication([])`，无显示服务器即 SIGABRT（exit 134，第一个 GUI 测试就崩）。给 Run tests 步骤加 `env: QT_QPA_PLATFORM: offscreen`。本仓 `ci.yml` 只有 lint、无 test job，此缺陷一直未暴露，直到本版本 release 才触发。

## 3.1.0 (2026-08-08)

本版本收尾 3.0.0 GUI 架构重写：修复默认轨道设计的界面冻窗、参数面板补单位切换与 duration 默认下调、e2m2e 改 pip 安装并自动探测 SPICE 内核，并退役旧架构 `tod/` 完成 `src/` 单轨迁移。

### 修复

- **GUI 轨道设计冻窗（#357）**：默认参数设计 DRO 时界面卡死数十秒、无法完成计算与可视化。根因是 e2m2e 5.5.0 两处死持 GIL——CR3BP 族延拓走 scipy `solve_ivp`（设计阶段，约 70s，与 duration 无关）和长期预报 `propagate_compiled`（随 duration 增长）。升级 e2m2e 5.5.0→5.6.1（约束 `>=5.6.0`），两层分别由 5.6.0（`dee042d`，切 Rust `propagate_cr3bp_stm_py`）与 5.6.1（补 `allow_threads`）修复；默认 DRO + 1 月路径由约 88s 冻死降至约 23s、零冻窗。

### 体验

- **参数面板按字段切换显示单位（#351）**：振幅 km↔DU、时间年↔TU、秒↔TU，切换显示单位保持物理量不变。
- **duration 默认下调至 1 个月并新增月/日显示单位（#355、#356）**：短弧设计更顺手，同时压低长期预报时长以减轻冻窗（配合 #357 根治）。

### 分发

- **e2m2e 改 pip 安装并自动探测 SPICE 内核目录（#353，ADR 0012）**：e2m2e 由 editable 指向本地改为 pip 正式安装；启动时探测内核目录并设 `SPICE_KERNEL_DIR`，避免闰秒内核 `SPICE(NOLEAPSECONDS)`。

### 退役

- **删除 `tod/`（136 .py）与 `tests/tod/`（81 文件）**：旧 GUI（mixin 架构）、`generates/transfers/scripting` 脚本层、`commons/e2m2e_compat` 旧路径兼容 shim 全部移除。脚本工作流的算法逻辑本就属于 e2m2e，CLI 用户改经 e2m2e CLI 使用（ADR 0006）。
- **`tod/commons/` 迁入 `src/commons/`**：`constants.py`（CR3BP 惰性常量 MU/DU/TU/VU）、`orbits.py`（GEO/LEO 圆轨道几何）、`input_contract.py`（输入文件选择契约）、`paths.py`（OUTPUT_DIR + find_project_root + safe_resolve_within + ensure_output_dir 合并）。
- **`tod/plot/` 提升为顶层 `plot/`**：内部 import 改 `src.commons.*`，剥离 `tod.scripting`（SCRIPT_ENTRY 机制废弃），`load_search_results` 与 `find_latest_single_dro` 提取为 `plot/_io_utils.py`、`plot/_artifact_helpers.py`。绘图脚本作为独立命令行工具保留，供高级用户使用。
- **`tod/gui/i18n` 迁入 `src/app/i18n`**：`.qm`/`.json` 资源随 package-data 路径同步更新。

### 变更

- **入口扶正**：`transfer-orbit-design` 命令从 `tod.gui.main:main` 改为 `src.app.main:main`，移除 `-v2` 别名。
- **PyInstaller spec**：datas 收 `src/` + `plot/` 取代 `tod/`；注释更新为新 GUI QThread 直调模型（不再依赖磁盘脚本扫描）。
- **README**：移除 `-v2` 命令与 `tod/` 引用，CLI 脚本工作流指向 e2m2e CLI。
- **CI/lint**：ruff `exclude` 移除 `"tod/"`（全仓纳入扫描）；`docs.yml` 触发路径移除 `tod/**`、增加 `plot/**`。
- **Sphinx 文档**：删除 `docs/source/tod/`（101 RST，含 `automodule:: tod.*`）与对应 locale `.po`（137 文件），`index.rst` 移除 `tod/index` toctree。
- **扫描结论**：`tod/transfers`、`tod/generates` 经核查均为 e2m2e algorithm 层的薄封装 + argparse CLI，无非薄封装的编排逻辑需迁移；等价覆盖由 e2m2e 自身测试承担。

### 验证

- 测试基线随 `tod/` 移除从 ~1290 降至 232；本版本含后续补丁，发布前 `uv run pytest` 243 passed、`uv run ruff check .` 0 error。

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
