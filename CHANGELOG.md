# 更新日志

## 未发布

### 轨道预报接入（issue #389）

- **工具启用**：「轨道预报」（e2m2e 5.8.2 `orbit_propagation`）进入工具下拉，经 Facade 调用（Config 注入 kernel_dir，同 design_orbit 范式）；duration 沿用 GUI 标准单位年，桥接层换算为秒。
- **初值预填**：选中含 GCRS 星历的工件（design_orbit / control_orbit / 预报产物自身）时，`initial_state` 预填为其末端 [位置; 速度]（km, km/s），历元预填为末端时刻；纯手填也可用。
- **力模型配置**：`force_config` 不做结构化表单——留空走默认三体，可填 JSON，非法 JSON 运行前拦截不发起任务。
- **画布渲染**：输出 GCRS km 惯性星历走既有 `ephemeris_position_km` 槽位；会合系位置由 GCRS km 经 e2m2e `SynodicJ2000System`（Rust 批量转换）转质心归一脉动会合系（有测试锚定月球 → 1−μ），两视图与 GIF 导出照常可用，不引入 spacetime_transform 依赖。`times_et` 按 ADR 0013 决策 5 的"后续"路径从 `times_jd_tdb` 直读换算（SPICE ET ≡ J2000 JD TDB 秒，与 str2et 等价且免去闰秒换算）。
- **产物持久化**：e2m2e 未提供该工具的 catalog 入库，星历落 JSON 到 `output/propagation/`，重启经 discovery 扫描恢复进项目树（文件名茎作 artifact_id）。

### 库浏览器改造（issue #375）

- **升级依赖**：最低版本升为 `e2m2e>=5.8.0`，`uv.lock` 同步。获得轨道库 catalog（上游 #475 / ADR 0031）：多维分类、谱系指针、教学标注、子集导出与产物自动入库。
- **项目树接 catalog**：产物清单与多维过滤（族 / 平动点 / Jacobi 区间 / 振幅区间 / 段存在性组合）来自 Facade `catalog_query`；单条产物经 `catalog_get` 懒加载（CR3BP 段 + 星历段双段，四槽位可视化契约不变）。过滤栏取值域经 e2m2e Pydantic 模型公开接口生成（ADR 0009 范式）。discovery.py 的轨道 / 族 / 星历文件名分类正则删除；transfer 分区过渡期沿用目录扫描。
- **谱系持久化**：轨道保持以库中记录直连输入（`input_record_id`），站保产物自动记录 `source_record_id`，重启后因果链不断；上游被删显示 ⚠ 断链降级标记，产物仍可用。
- **切回 Facade**：`design_orbit` / `control_orbit` 从算法层直调切回 Facade 门面（完成 ADR 0011 缓解措施 3 的既定清理），产物随计算自动入库；persistence.py 的手写落盘（save_artifact / save_control_result / save_family_result）退役，仅保留稳定性分析落盘。
- **教学视图**：记录详情面板显示分类与谱系，tags / note 可查看编辑（`catalog_tag` 落库）；族成员可提升为独立记录（`catalog_promote`）进入下游；过滤子集可打包导出案例包（`catalog_export`，zip 或目录，包可直接作为库打开）。
- **库目录设置**：默认仓库根 `catalog/`（与 output/ 平级），菜单「设置 → 轨道库目录…」可改（QSettings 持久化）。
- **旧产物**：output/ 旧格式不迁移（ADR 0008 修订 2026-08-19），需要时重算。

### e2m2e 5.7.3 适配

- **升级依赖**：最低版本升为 `e2m2e>=5.7.3`，`uv.lock` 同步。获得 NRHO 星历修正默认路径在 GUI 默认量级收敛（上游 #473：NRHO 等时间采样 + `revs_per_group=1` + 删近月点采样钉历元 `t=0`；另放宽 NRHO 相位到 0~1）。
- **恢复 NRHO 完整设计路径**：撤掉桥接层「仅 CR3BP 初猜」止血；NRHO 与 Halo 一样走 `design_orbit`，产物含标称星历，可作轨道保持输入。日志/状态栏/文档与 smoke（默认量级 NRHO）同步。
- **真实路径回归**：`tests/engine/test_facade_bridge_e2m2e_smoke.py` 新增默认量级 NRHO（L2 南、5000 km、约 1 个月）端到端收敛 + 星历对齐断言，纯 5.7.3 wheel 上约 30 s 内通过。

### e2m2e 5.7.1 适配

- **升级依赖**：最低版本升为 `e2m2e>=5.7.1`，`uv.lock` 同步。获得七族统一轨道族生成（#428）与多项数值内核下沉 Rust。
- **轨道族生成接入七族**：GUI 暴露 Halo / NRHO / Axial / Lissajous / SPO / LPO / Horseshoe 下拉，按族显示对应参数（振幅、近月点、相位、延拓方向等）；`sampling_mode` 各族首版只有唯一规则，不进面板。桥接层改走 `Facade.orbit_family_generation`（响应 `FamilyGenerationResponse` 携带完整轨道成员与状态三元组，软失败保留部分族）；5.7.1 起请求按 `model_fields_set` 拒绝跨族字段，面板收集后只传当前族适用字段，None 一并剔除。周期族成员只携带初态与周期，桥接层按周期重采样到固定点数供画布渲染；Lissajous 拟周期成员自带等长完整轨迹。
- **结果契约泛化**：`FamilyResultData` 增加 `family_type` / `periodicity` / `member_parameters` / `status_message`；`z0s` 仅 Halo 保留。落盘 JSON 同步写入成员参数；完成日志按族报告标志性几何量（z 振幅 / 近月点高度 / 径向振幅等）。
- **轨道设计默认对齐**：Horseshoe 振幅默认 150000 → 100000 km（上游默认与可达包络收口至 110000 km）；范围以 `DesignOrbitRequest.valid_ranges()` 为准，GUI 不另维护一份。
- **异常翻译**：`e2m2e.api.OrbitError`（Facade 接缝）透传错误码与消息。

## 3.2.3 (2026-08-14)

### 修复

- **短弧轨道保持默认值**：GUI 轨道保持面板改用 0.25 天控制间隔与 0.125 天反馈弧，覆盖 120 次控制约 29.6 天；此前沿用上游多年星历的 30 天/28 天默认值，用户设计 Halo 短弧后直接运行必被覆盖校验拦截。上游算法默认值保持不变，较长任务仍可在面板调整。
- **防止默认 Lissajous 轨道发散**：e2m2e 5.6.9 仅对 Halo/NRHO 自动改走 segmented 分段修正，Lissajous 沿用 standard/two_level 时，一圈修正后的自由外推沿不稳定流形发散，标称星历整段越飘越远。GUI 不暴露 segmented 选项，桥接层对 Lissajous 固定注入 segmented，保持整段星历有界；附默认 Lissajous 星历有界回归测试，工具文档同步说明。
- **窗口取消最大化后无法再次全屏**：画布工具栏所有控件单行排列，Qt 把累积最小宽度（2029 px）传播给主窗口，窄屏下布局约束无法满足，窗口有响应但不能恢复最大化。改为多行 QGridLayout 后最小宽度降至 936 px（回归测试锁定 ≤960 px），启动入口改 `showMaximized()` 默认最大化。

### 功能

- **轨道保持识别、停止与图例**：选中 Halo/NRHO 后，特征点模式自动设为 ẋ=0 且 ż=0；运行区新增停止按钮，当前数值调用返回后丢弃已取消结果；画布各视图自动显示轨道、初猜与星历的图例。

### e2m2e 5.6.9 适配

- **升级依赖**：最低版本升为 `e2m2e>=5.6.9`，`uv.lock` 同步。获得 Halo/NRHO 长弧段分段打靶与 Rust 并行修复（#404），以及 FiniteBurn 恒质量 Rust 传播（#420）。
- **轨道设计参数收口**：移除上游已删除的 `correction_velocity_tolerance`；修正方法下拉移除已不存在的 `homotopy`，保留公开契约中的 `standard` / `two_level`，Halo/NRHO 继续自动使用 `segmented`。旧 `UnsupportedCorrectorMethodError` 类型随上游 `ephemeris_correction` 包删除，非法修正方法统一按 `INVALID_PARAMS` 翻译。
- **轨道族接入公开契约**：删本地 `FamilyGenerationRequest`，改用上游模型的平动点与折叠点振幅校验；桥接层委托 `design_halo_family`。GUI 保持 Halo 北族入口，隐藏模型中的族类型字段并在调用时固定注入 `HALO`。
- **轨道保持面板对齐模型**：`control_interval` / `feedback_arc` 改由 `ControlOrbitRequest` 自动生成；新增的控制迭代、测定轨与推力误差、真实力模型字段补齐中文标签，分入控制、仿真与误差、力模型、角动量管理四组。
- **工具状态派生**：`TOOL_REGISTRY` 改从 `tool_inventory()` 读取 facade 工具状态，灰显工具不再维护“已实现/占位”的本地判断。

### 功能（右边栏更新）

- **参数分组与工具说明**：参数面板按组展示（轨道设计：形状/传播/修正参数；轨道保持：控制/仿真与误差/角动量管理；族生成：族参数），组表头 + 分隔线，轨道类型切换时整组隐藏；工具选择器下方新增工具说明（`ToolSpec.description`）；运行按钮旁新增"重置参数"按钮（重建面板恢复默认值）。
- **整数枚举改下拉**：`collinear_point`（L1/L2/L3）、`north_south`（北族/南族）、`control_mode`（1-6 带角动量管理语义）、`is_nrho`、`special_mode`、`libration_point` 由裸 spinbox 改为带中文标签的 QComboBox（值存 itemData，收集按数据取值）。
- **范围占位提示**：数值控件框内文本清空时显示约束范围（placeholder），tooltip 附描述+范围；切单位后提示同步刷新。全约束显示 min~max，单侧 `gt/lt` 显示 >/<，无约束字段如实显示"无范围约束"（不拿 Qt 兜底值冒充）。JSON 文本框（perturbation/dyb/engine_layout）为空时给格式示例提示。模型缺上界的 int 字段（num_controls/num_monte_carlo）用 GUI 临时上界兜底并注明。
- **单位换算全覆盖**：所有可换算参数都提供国际单位与归一化单位切换——距离 km/m/DU（amplitude/amplitude_in/amplitude_out/perilune_height/semi_major_axis/max_amplitude_km）、相位 周期份额/度/弧度、角度 度/rad、时间 duration 年/月/日/时/秒/TU、output_step 秒/时/日/TU、control_interval/feedback_arc/momentum_interval 天/秒/TU、srp_offset_m 列表容器 m/DU；5.6.9 起 control_interval/feedback_arc 由模型自动生成并按显示单位换算。多次切单位精确往返（换算缓存，30 天→TU→秒→天无舍入漂移）。
- **facade 工具清单对齐**：`TOOL_REGISTRY` 从 `e2m2e.api.Facade.mcp_tools()` 自动派生全量清单——已接入的轨道设计/轨道保持/轨道族生成 enabled，e2m2e 已实现但 GUI 未接入的（转移设计/轨道预报/时空坐标转换）与 e2m2e 占位的（转移搜索/小推力设计/不变流形分析/低能转移/相对运动）灰显并附工具说明；e2m2e 新增工具时清单零改动跟随。稳定性分析保持右键入口（下拉灰显）。
- **新增轨道类型**：轨道设计支持 e2m2e 5.6.8 全部周期轨道类型——新增 DPO、Axial、L4_SPO、L5_SPO、L4_LPO、L5_LPO、L4_HORSESHOE、L5_HORSESHOE（默认值对齐 `DesignOrbitRequest` model_validator）。
- **补全字段标签与 JSON 接口**：perturbation/dyb/earth_degree/moon_degree/correction_revolutions 与轨道保持字段全部换中文标签（此前裸显字段名）。`engine_layout` 的有效 JSON 文本现会解析为 `EngineLayout`，角动量管理模式 4–6 可实际使用；非法 JSON 与非布局 JSON 均给出 `INVALID_PARAMS` 明确错误。

### 工程

- **CI/release 一致性与效率**：PR CI 补全 headless GUI 测试，不再等到发布 tag 才首次执行；静态检查、测试、文档和 Windows 打包均改用 `uv.lock` 的冻结安装，避免 `pip` 和临时 PyInstaller 版本漂移；静态检查跳过本项目安装，docs/release 取消无用的 e2m2e 源码 clone。runner 固定为 Ubuntu 24.04 / Windows 2025，uv 缓存按 `uv.lock` 失效，checkout 不保留凭据；发布 token 收敛到创建 GitHub Release 的 job，Windows 产物缺失会立即失败。PyInstaller 构建组纳入锁文件，并移除 e2m2e 5.6.8 已删除的 `tools.viz` hidden import。

### 上游问题跟踪

- 向 e2m2e 提交 5 条 issue（右边栏无法在本仓解决的问题）：#408（ControlOrbitRequest 是算法层签名子集且缺约束/单位说明）、#409（DesignOrbitRequest 分支范围不可机器读取）、#410（correction_velocity_tolerance 死参数）、#411（orbit_family_generation 无 Request 模型）、#412（facade 工具清单状态不可机器读取）。

## 3.2.2 (2026-08-13)

适配 e2m2e 5.6.8：上游修复 segmented 逐段积分的位置-时间错位（#398）——`ForceModel._prepare_t_eval` 会在 `t_eval` 末尾自动追加段终点，逐段积分把每段多出的端点状态拼进星历，位置数组比时间网格多出段数个点，`batch_j2000_to_synodic` 按索引配对，错位逐段累积，会合系曲线一圈一圈偏离 Halo 轨道（GUI 观感"慢慢发散"）。同版为 GUI 补上 SPICE 内核引导（首次启动探测不到内核自动弹窗，可一键下载或指定已有目录），并修复轨道保持三处可用性问题（mu 透传崩溃、engine_layout 字符串崩溃、仿真时长超出星历覆盖致全样本失败）。

### 功能

- **启动时内核缺失引导（#366）**：`main()` 启动时探测可用内核目录（`$SPICE_KERNEL_DIR` → 配置记录 → 仓库 `kernels/` → 用户数据目录 → 同级 e2m2e 源码仓库），缺失则弹窗三选一：
  - **下载内核**：后台线程从 e2m2e `kernels-v1` release 下载到用户数据目录（`~/.local/share/transfer-orbit-design/kernels`，Windows 为 `%LOCALAPPDATA%`，跨版本共享），模态进度条显示逐文件进度，可取消（已下载文件保留，重试幂等续传）；
  - **指定已有目录**：文件选择对话框选目录，校验含行星历 `.bsp` 与闰秒 `.tls` 后写入配置文件（`~/.config/transfer-orbit-design/kernels_dir.txt`），下次启动自动探测；
  - **暂时跳过**：本次不准备，功能用时再报错。
- **下载逻辑抽为 `src/commons/kernels.py`**：`download_kernels`（幂等 + 进度回调）、`kernel_dir_usable`（行星历 `.bsp` + 闰秒 `.tls` 完整性判断）、`user_kernel_dir`；`scripts/download_kernels.py` 改为其 CLI 包装（命令行行为不变）。

### 修复

- **轨道保持 mu 透传崩溃**：参数面板按 `ControlOrbitRequest` 字段收集 `mu`（e2m2e 的响应透传字段，画地月标注用，算法函数签名无此参数），facade 以 `**params` 展开调用 `control_orbit()` 直接 `TypeError`（GUI 报 UNKNOWN_ERROR，轨道保持完全不可用）。修复：面板隐藏 mu（与 `input_ephemeris` 同构，由源 Artifact 注入 `source_mu`），facade 接缝处 `pop("mu")` 防回归。新增 3 项测试（面板不含 mu、params 不含 mu、算法层收不到 mu）。
- **轨道保持 engine_layout 字符串崩溃**：面板把 `engine_layout` 建成 JSON 文本框（Any 字段），用户随手填 "4"，e2m2e 对非 None 布局无条件 `validate`（访问 `.E_r`），字符串直接 `AttributeError`（GUI 报 UNKNOWN_ERROR）。修复：facade 规范化——`control_mode < 4`（无角动量管理）时忽略置 None；`>= 4` 时 dict 构造 `EngineLayout` 实例、空串归一 None（走 e2m2e 清晰报错）、其余值报 INVALID_PARAMS 明确提示输入格式。新增 3 项测试（低模式忽略、dict 构造实例、无效值清晰报错）。
- **轨道保持全样本失败（仿真时长超出星历覆盖）**：`ControlOrbitRequest` 模型未暴露 `control_interval`/`feedback_arc`，面板没有这两个字段，e2m2e 默认 30 天/次 × 119 次 + 28 天反馈弧 ≈ 3598 天，而 GUI 设计默认星历仅 30 天——控制律目标点全部超出标称星历覆盖，5 个蒙特卡洛样本必然全部失败（Δv=0、无机动，GUI 无任何提示）。修复：面板补充 `control_interval`/`feedback_arc` 字段（默认对齐 e2m2e 签名，`collect_params` 支持模型外补充字段）；`_run_control` 运行前校验仿真时长 ≤ 星历覆盖，超出则拦截并提示调整参数或延长标称轨道。实测 30 天 Halo 用 0.25 天/次 + 0.125 天反馈弧 → 4/5 样本成功。新增 3 项测试（面板含补充字段、超出拦截、覆盖内放行）。
- **matplotlib 3.11 兼容（画布轨道族渲染）**：`matplotlib.cm.get_cmap` 自 3.7 弃用、3.11 移除，画布按图表设置取色（`_orbit_color`）与轨道族 3D/2D 渲染在 matplotlib>=3.11 下直接 `AttributeError`（CI 全新安装即触发，本地旧版只告警不报错）。改用 `matplotlib.colormaps[...]`（3.5+ 可用，与 `src/commons/viz` 的 `PlotConfig.get_cmap` 一致）。

### 工程

- **pin e2m2e>=5.6.8**：含 segmented 星历对齐修复的最低版本（上游 #398，5.6.8 同时收尾圈终点覆盖与 ELFO 截断对齐），uv.lock 同步（5.6.7 → 5.6.8）。
- **新增测试**：下载幂等/进度/资产过滤、可用性判断、用户目录探测、配置读写、弹窗三分支（可用直返/下载/指定/跳过）共 34 项。

## 3.2.1 (2026-08-12)

适配 e2m2e 5.6.7：上游删除 `tools/viz` 模块（各自实现绘图）并统一结果契约（#351，`success`/`converged` 方言废除，改 `status`/`cause`/`message`），本项目收编绘图代码、迁移收敛判定，并把新增的类型化异常接入错误翻译层。5.6.6 发布物漏打包 `constants.toml`（安装后 import 即 `FileNotFoundError`），由上游 5.6.7 修复（文件收进 `e2m2e/data/constants/` 包内），故下限直接钉 5.6.7。

### 修复

- **收编 e2m2e `tools/viz` 为 `src/commons/viz`**：e2m2e 5.6.6 删除整个 `tools/viz` 模块（上游 #391），GUI 画布的地月标注/平动点绘制（viz_adapter）与 plot/ 脚本的 FamilyPlotter/PlotConfig 全部 `ModuleNotFoundError`（34 项测试挂）。将 5.6.5 的 base/config/family/icons 四件套收编进 `src/commons/viz`（Apache-2.0，内部相对导入改绝对导入，剔除未用的 TransferPlotter），由本项目自维护。
- **收敛判定迁移统一结果契约**：e2m2e 5.6.6 起 `EphemerisCorrectionResult.converged` 废除（上游 #351），facade 的 `result.correction.converged` 会 AttributeError。改为 `status is ConvergenceState.CONVERGED`；顺带修了 ELFO 场景 `correction=None` 时的既有 AttributeError 隐患（现视为未收敛）。
- **plot/ 脚本导入修正**：`from e2m2e.transfer import ...`（5.6.5 下即不存在的顶层模块，既存错误）改为 `e2m2e.algorithm.transfer`；`Orbit`/`OrbitFamily` 不再由 `e2m2e.algorithm.dynamics` 转发、`CR3BP_System`/`SynodicJ2000System` 不再由 `e2m2e.data.types.orbit` 转发，统一改从定义处导入（`e2m2e.data.types.orbit` / `e2m2e.algorithm.dynamics` / `e2m2e.algorithm.coordinate.synodic_j2000`）。

### 功能

- **异常翻译接入 5.6.6 新类型化异常**：`PropagationFailure`（传播失败，上游 #349，取代错误消息前缀匹配）映射为新错误码 `PROPAGATION_FAILED`；`RustExtensionUnavailableError`（Rust 内核缺失不再静默回退 Python，上游 #378）映射为 `BACKEND_UNAVAILABLE`；`DesignNotConvergedError` 消息附带上游 `FailureCause`，失败原因可定位。

### 工程

- **pin e2m2e>=5.6.7**：结果契约迁移后的最低可用版本（5.6.6 发布物漏打包 `constants.toml`，安装后 import 即 `FileNotFoundError`，上游 5.6.7 已修复），uv.lock 同步。
- **常数注释同步上游单一来源化（#377）**：`CR3BP_System` 默认尺度变化（DU 384405.0→384400.0 km、TU 4.33030→4.34248 天、VU 1027.30→1024.55 m/s），与 `data.templates` 特征尺度对齐，units.py 中两者不一致的历史警告移除；同时纠正 constants.py 行内注释的单位误标（TU 属性返回天、VU 返回 m/s，非 s/km/s——消费方用法本就与天/m/s 一致，仅注释错）。
- **已知上游问题（5.6.7 已修复，本条留档）**：e2m2e 5.6.6 发布物（sdist/wheel）漏打包 `constants.toml`，安装后 import 即 `FileNotFoundError`（loader 按 site-packages 根寻址）；5.6.7 将文件收进 `e2m2e/data/constants/` 包内并改包内寻址，问题消除，本地不再需要桥接。
- **清理 release lint job 的 e2m2e clone（dcc6602）**：08c6bb1 已把 test/build job 改用 PyPI e2m2e，lint job 里遗留的 `git clone ../e2m2e` 纯属闲置（lint 只跑 ruff），删除。
- **重新生成 uv.lock（7531c03）**：v3.2.0 发布途中 rebase 冲突残留了 `<<<<<<<` 标记，`uv lock` 重新生成以清掉，当前文件已无冲突标记。

## 3.2.0 (2026-08-10)

3.1.3 之后适配 e2m2e 5.6.5：恢复 Halo/NRHO 设计端到端可用（e2m2e 自动走 segmented 星历修正，修多圈发散），并修复 e2m2e 5.6.4 起 `design_orbit` 入口的签名与参数模型 breaking——后者自 5.6.4 起让 GUI 任何轨道设计都 TypeError，因测试全 mock 未暴露。

### 功能

- **Halo/NRHO 设计端到端可用（e2m2e 5.6.5，docs 73d1ff6）**：two_level 的「修正 1 圈 + 自由外推」对不稳定轨道（STM ~1e7/圈）必发散；e2m2e 5.6.5 对 Halo/NRHO 自动重定向 segmented（全程分段打靶，不依赖外推）。GUI 设计 Halo（amp=30000、L2、30 天）~9 s 收敛，三圈会合系 x∈[1.085, 1.187] 紧邻 L2。圈间漂移是固有准周期特征，由 station_keeping 处理，设计阶段不压。

### 修复

- **适配 design_orbit 入口签名 + duration 单位（27eda00）**：e2m2e 5.6.4 起 `design_orbit` 首参从散字段改为 `DesignOrbitRequest`（`extra="forbid"`），facade 的 `**kwargs` 转发会 TypeError、GUI 设计全挂；`duration` 单位从年改秒，facade 加 `* SECONDS_PER_YEAR` 换算（不修则 1 年当 1 秒、et_grid 只剩 1 点）。改为构造 request 调用。此前测试全 mock（伪造 kwargs 签名）掩盖了断裂，本次把 mock 改回真签名 + 加 `@pytest.mark.spice` 真 smoke 守住接缝。
- **params_panel 适配新参数模型（27eda00）**：`DesignOrbitRequest` 从 14 字段扩到 23（ELFO 根数 inclination 与摄动/修正字段 dyb 等新增），duration 改 Optional。`ORBIT_TYPE_DEFAULTS` 补 ELFO 分支与新 Optional 默认值；orbit_type 下拉原从 description split（5.6.4 改全大写 + 含 "..." 占位符，得 "HALO" 与 key "Halo" 不匹配），改从 `ORBIT_TYPE_DEFAULTS` key 取。

### 工程

- **pin e2m2e>=5.6.5（e00b64f）**：含 Halo segmented 修复的最低版本，uv.lock 同步。

## 3.1.3 (2026-08-09)

3.1.2 之后的星历模型可视化改造：星历结果获得会合系（质心归一，自洽）/ 地心惯性系双视图与 GIF 动画导出，轨道设计标称星历进画布，修复星历产物与地月标注的原点偏移，并为画布接入真物理时间轴。约定见 ADR 0013。

### 功能

- **轨道设计标称星历进入画布（#359）**：轨道设计产物此前在画布上只能看到 CR3BP 周期初猜，真实星历模型下的标称星历（拟周期、跨整个 duration）一直埋在 Artifact 的 `extra["ephemeris"]`。画布新增"绘制内容"维度（初猜 / 星历 / 叠加，默认叠加）——与会合系/惯性系正交。叠加视图初猜用实线、星历用虚线，TAB10 相邻色区分。两份轨迹从 `_artifact_for_id` 显式平级进画布（`initial_guess_states` / `ephemeris_synodic` / `ephemeris_position_km` / `ephemeris_times_et` 四槽），不嵌套、不靠隐式 fallback。惯性系下"初猜"灰显（CR3BP 无量纲无惯性系表示）；control_orbit 产物无初猜，"初猜"恒灰显。导出动画跟随绘制内容：初猜模式无物理时间轴，明确拒绝导出。从磁盘恢复的历史 design_orbit Artifact 也支持（NPZ 已存全字段）。ADR 0013 范围从 control_orbit 受控星历扩到 design_orbit 标称星历 + control_orbit 受控星历。
- **星历模型坐标系切换与惯性系视图（#358 P1，93977fa）**：画布新增会合系 / 地心惯性系（GCRS）切换。惯性系视图以地球为原点、月球按 SPICE 真实轨迹移动、轨迹用 GCRS km、不画平动点；会合系维持 CR3BP 旋转系 + 地月 + L1–L5。脉动-旋转系为 cislunar 可视化主流（Folta 2022、Park 2025），瞬时平动点在该系与 CR3BP 几何一致（Boudad 2022）。
- **GIF 动画导出（#358 P2，93977fa）**：新增独立"导出动画"工具，按时间等分采样逐帧渲染、Pillow 合成 GIF（不依赖 ffmpeg）。支持累积 / 滑动窗口、UTC 帧时间戳、坐标系随当前视图。

### 修复

- **control_orbit 星历的原点偏移（#358 P0，d0e1449）**：受控星历的会合系位置是地心归一（月球 +1），画布标注按质心归一（月球 1−μ），相差 μ·DU ≈ 4690 km。提取时减 source_mu 对齐；同源 GCRS 位置 km 与由 UTC 重建的 ET 秒一并透传到画布接口，为惯性系视图与动画铺路。
- **design_orbit 产物按轨道类型分目录落盘（8a2925e）**：`save_artifact` 曾无条件写 `output/dro/dro_<ts>`，Halo/NRHO/Lissajous 等非 DRO 轨道被存成 DRO 文件；discovery 按目录+前缀分类，读取时误当作 DRO，画布四槽数据契约因此失效。改为按 `orbit_type` 归一化派生目录名与文件名前缀，DRO 保持既有布局向后兼容；discovery 改为「目录名 → 轨道类型」映射 + 文件名前缀校验分类，兼容 `halo_north_L1.json` 等旧手工命名。新增回归测试覆盖保存、roundtrip 分类与多类型混存。
- **锁定 e2m2e==5.6.3（778f66d）**：5.6.1 的 two_level 修正把位置(km)与速度(km/s)混在同一残差向量取范数，速度项被量级淹没，求解器停在「位置连续、速度跳变数十 m/s」的局部极小，L1 Halo 长期预报发散。5.6.3 含上游 Rust 打靶速度加权修复；pyproject 从 `>=5.6.0` 收紧为 `==5.6.3` 精确锁定。
- **无标称星历时明确提示（cdaeae1）**：design_orbit 产物无标称星历时，此前会合系下画布静默只画初猜、无任何提示。新增 `_warn_missing_ephemeris`，与 `_warn_missing_mu` 并列在选中 Artifact 时提示（设计正常总有星历，仅防御异常/旧产物）。
- **discovery 合并嵌套 if 过 ruff（786f4c1）**：8a2925e 引入的 `parent == "dro"` 嵌套 if 触发 ruff SIM102（CI `ruff check .` 会红）。合并为单 if，纯风格、语义等价。

### 工程

- **从 git 移除论文版 PNG（f1b6cc1）**：删除 `figures/结果` 下的论文版 PNG，改由 `plot/` 脚本现算现出，避免大二进制文件进版本库。

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
