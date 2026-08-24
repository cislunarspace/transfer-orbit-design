# 旧 PyQt 版 GUI 功能盘点（迁移前最后状态：commit fa2d0e3 = 64c943b^）

来源说明：以下所有条目均出自 `git show 64c943b^:<path>`（即迁移删除前的最后版本，fa2d0e3）。旧 GUI 代码分布：`src/app/`（入口/主窗口/内核引导/i18n）与 `src/view/`（12 个视图组件），另有 `src/engine/workers.py`（QThread 工作线程，随迁移删除）。参数约束的运行时来源是 e2m2e Pydantic 模型（本机 e2m2e 5.8.5 导出；64c943b^ 的 pyproject 钉 `e2m2e>=5.8.2`），GUI 在构建控件时动态读取 `ge/gt/le/lt/multiple_of` 等元数据。

---

## A. PyQt 版功能全清单

### A1. 应用入口与全局（src/app/main.py、kernel_setup.py、i18n/）

| 功能 | 描述 | 来源 |
|---|---|---|
| 启动流程 | CJK 字体回退 → QApplication → 应用界面设置（字号/主题）→ SPICE 内核探测/引导 → 主窗口 showMaximized | main.py:12-44 |
| SPICE 内核首次引导 | 内核缺失时弹三按钮对话框：下载内核（后台线程 + 模态进度条 + 可取消 + 幂等续传）/ 指定已有目录（校验 .bsp+.tls 后写配置）/ 暂时跳过 | kernel_setup.py:127-156 |
| 内核下载进度 | QProgressDialog 逐文件显示"正在下载 {name}（{done}/{total}）"，取消后已下载文件保留 | kernel_setup.py:77-108 |
| i18n 翻译加载 | QTranslator 加载 gui.en.qm + scripts.en.json 脚本翻译表，中文为回退语言；qt_format 支持 %1 占位符 | i18n/__init__.py:29-74 |
| 脚本条目翻译 | translate_script_entry 对 ScriptEntry 的 description/CLI 参数/chip 参数/环境变量应用翻译表 | i18n/__init__.py:77-146 |

### A2. 主窗口布局与全局交互（src/app/main_window.py，2370 行）

| 功能 | 描述 | 来源 |
|---|---|---|
| 三栏 Splitter 布局 | 左（项目树，默认 240px）/ 中（画布+日志，778px）/ 右（参数面板，370px）；左右栏固定宽不可收起，中间弹性 | main_window.py:103-109, 453-473 |
| 分栏位置持久化 | closeEvent 保存两个 splitter 的 saveState 到 QSettings（ui/splitter/main、ui/splitter/center），启动 restoreState | main_window.py:468-471, 547-551 |
| 分栏默认值版本迁移 | _SPLITTER_DEFAULTS_VERSION=3，升版后首次启动丢弃旧存档改用新默认 | main_window.py:111-113, 445-451 |
| 中栏纵向分栏 | 画布（默认 560）/日志（默认 160）垂直 splitter，同屏显示可拖动 | main_window.py:620-631 |
| 菜单栏"设置" | 图表设置… / 界面设置… / 轨道库目录… / 重置布局 四项 | main_window.py:504-523 |
| 重置布局 | 清除持久化分隔条位置并恢复默认分栏 | main_window.py:539-545 |
| 状态栏 | QStatusBar，所有操作反馈 5 秒自动消失（_STATUS_MSG_TIMEOUT_MS=5000），启动显示"就绪" | main_window.py:100-101, 396-398 |
| 工具选择器 | QComboBox 列出 TOOL_REGISTRY 全部工具（enabled 在前），禁用项灰显且 tooltip 显示原因；control_orbit 不进下拉（入口在选中产物后） | main_window.py:641-658；facade_bridge_old.py:340-437 |
| 工具说明区 | 切换工具时显示 spec.description（多行自动换行） | main_window.py:661-665 |
| 运行/停止/重置按钮 | 运行中按钮文本变"运行中…"，停止变"停止中…"；运行时禁用工具切换与重置；全局绿色运行/红色停止样式 | main_window.py:353-358, 723-731；ui_settings.py:110-115 |
| 任务互斥 | 主窗口 worker 与轨道保持弹窗任一在运行时拒绝新任务，状态栏提示"已有任务运行…" | main_window.py:827-843 |
| 协作式停止 | 停止请求 → worker.requestInterruption() → 当前数值调用返回后丢弃结果（"运行已停止，结果未保存"） | main_window.py:801-825 |
| 计算完成后自动选中新记录 | 重查轨道库清单后按 record_id 选中并渲染；不满足当前过滤条件时日志说明 | main_window.py:1585-1594 |
| 项目树多选 | Ctrl+多选触发批量渲染（懒加载 + 缺 mu/星历警告逐条打日志） | main_window.py:1327-1341 |
| 删除产物（含确认框） | 右键删除：库记录弹 QMessageBox 确认"永久删除 N 条（含数据文件，不可撤销）"，走 catalog_delete；遗留分区仅移出内存 | main_window.py:1644-1686 |
| 稳定性分析（右键） | 右键 orbit → 查看稳定性：后台 StabilityWorker 计算，结果格式化为只读文本对话框（分类/指数/分岔/Floquet 乘子/6×6 单值矩阵），同时落盘 JSON | main_window.py:1796-1926 |
| 轨道预报初值预填 | 选中含 GCRS 星历的产物时切到轨道预报工具，initial_state 预填末端 [位置;速度]、epoch 预填末端时刻（SPICE et2utc） | main_window.py:733-799 |
| LGA 转移目标注入 | transfer_design 选 LGA 时以项目树选中轨道工件末态为目标，未选中时状态栏拦截提示 | main_window.py:1429-1445 |

### A3. 左栏：过滤栏 / 项目树 / 详情面板

| 功能 | 描述 | 来源 |
|---|---|---|
| 轨道库多维过滤栏 | 族下拉（解析 CatalogQueryRequest.orbit_family description 生成取值域）/ 平动点下拉（解析"1–5"） / Jacobi 区间（勾选启用 1.0–5.0，默认 3.0–3.2）/ 振幅 km 区间（0–1e6，默认 0–50000）/ CR3BP 段与星历段三态下拉（不限/含/不含）/ 重置 / 导出案例包按钮；任一变化即时重查 | catalog_filter_bar.py:49-182 |
| 导出教学案例包 | QFileDialog 选 zip 或目录，当前过滤子集经 catalog_export 打包，状态栏显示条数 | main_window.py:1724-1742 |
| 项目树四分组 | 🪐轨道 / 🌀轨道族 / 🚀转移 / 📡星历 四类分组（分组节点不可选），断链记录加"⚠断链"后缀 | project_tree.py:12-17, 71-92 |
| 右键上下文菜单 | orbit：轨道保持/生成轨道族(灰显,带 tooltip)/查看稳定性；ephemeris：轨道保持（链式站保）；family：展开成员(灰显)；transfer：优化(灰显)；所有类型追加"删除"；右键未选中项先单选它 | project_tree.py:23-36, 116-168 |
| 记录详情面板 | 显示族/平动点/Jacobi 区间/主振幅区间/段(CR3BP+星历)/成员数/来源工具/创建时间/谱系指针（上游已删显示"⚠ 上游记录已删除，本记录仍可使用"） | record_detail_panel.py:86-145 |
| 教学标注编辑 | tags（逗号分隔）+ note（多行），保存按钮 → catalog_tag 落库后保持选中 | record_detail_panel.py:48-56, 159-163；main_window.py:1698-1708 |
| 族成员提升 | family 记录显示成员序号 QSpinBox（0..member_count-1），"提升成员为记录"→ catalog_promote 生成独立记录并选中 | record_detail_panel.py:57-67, 165-167；main_window.py:1710-1722 |
| 轨道保持入口按钮 | 详情面板"轨道保持…"按钮，无星历段的产物（如提升的族成员）置灰并 tooltip 说明原因 | record_detail_panel.py:100-110 |
| 轨道库目录切换 | 菜单"轨道库目录…"：QFileDialog 选目录，QSettings 持久化（catalog/dir），清单从新库重读、新计算写入新库 | main_window.py:553-566 |
| 记录懒加载 | 选中/多选时经 catalog_get 按需加载完整数组，失败记日志"记录数据加载失败…" | main_window.py:1282-1289 |

### A4. 中栏：画布 + 工具栏 + 时间轴 + 日志

| 功能 | 描述 | 来源 |
|---|---|---|
| matplotlib 嵌入画布 | FigureCanvasQTAgg + NavigationToolbar2QT（平移/缩放/旋转/保存，图标 16px） | canvas.py:103-132, 1254-1256 |
| 投影切换 | 3D / XY / XZ / YZ / 四视图（quad，2×2 网格同时显示 3D+三投影）；QButtonGroup 互斥 + checked 高亮 | canvas_toolbar.py:40-44；canvas.py:329-337 |
| 坐标系切换 | 会合系（CR3BP 旋转系，无量纲）/ 惯性系（GCRS/J2000 km，地球原点 + SPICE 月球真实轨迹）；惯性系下无 position_km 的纯 CR3BP 产物降级为旋转近似视图并状态栏提示 | main_window.py:2115-2132；canvas.py:890-988 |
| 绘制中心切换 | 质心 / 月球 / L1 / L2（渲染整体平移使中心为原点，坐标范围对称化居中）；惯性系下 L1/L2 灰显并回退质心 | main_window.py:2110-2139；canvas.py:441-447, 609-626 |
| 绘制内容切换 | 叠加（初猜实线+星历虚线，相邻色）/ 初猜（仅 CR3BP）/ 星历；惯性系下"初猜"灰显自动切"星历"；control_orbit 产物会合系下"初猜"也灰显 | main_window.py:2142-2168 |
| 地月/L 点标注开关 | 两个 QCheckBox 默认勾选；地月标注经 viz_adapter（大小/字号走 ChartSettings）；惯性系画地球原点 marker + 月球轨迹（月心视图画地球相对轨迹深蓝虚线） | canvas_toolbar.py:54-55；canvas.py:778-817, 990-1127 |
| 等比例开关 | 默认开：3D box_aspect + 2D aspect=equal，Z 区间至少取 XY 较小范围的 z_ratio 倍防压扁；关闭后各轴独立填满 | canvas.py:62-69, 462-490 |
| 视图适配按钮 | 按带 _ORBIT_GID 标记的轨道线范围重设窗口（每轴 5% 余量），标注/时间轴 marker 不参与 | canvas.py:492-530 |
| 视图保持 | 布局（投影×坐标系×中心）不变的重绘捕获/恢复相机角(elev/azim/roll)与轴范围，增添/移除轨道不重置视角 | canvas.py:10-11, 291-387 |
| 时间轴 | 画布下方滑块（0..1000 线性映射 ET 区间），UTC 标签；100ms 周期节流（拖动中约 10Hz 重绘，松手补发终值）；飞行器与月球"此刻"marker（线性插值）；无星历产物灰显"时间轴（无星历数据）" | timeline_bar.py 全文；main_window.py:2070-2091；canvas.py:562-601 |
| 轨道族渐变渲染 | 族 (m,n,6) 逐成员 viridis 渐变色，起点小点标记族起始端；2D/3D/惯性近似视图一致 | canvas.py:680-729, 932-963 |
| 自动图例 | 带标签轨迹与天体自动 legend（>4 项两列） | canvas.py:532-543 |
| 空态标题 | 未选记录/无惯性系数据/月球位置不可用（SPICE 失败）三种提示标题 | canvas.py:427-439 |
| 日志面板 | 只读 QPlainTextEdit 等宽字体，每行 [HH:MM:SS] 时间戳；worker 进度/参数/结果统一走此处 | log_panel.py 全文 |
| GIF 动画导出 | 工具栏"导出动画"：参数对话框（坐标系按数据可用性、帧数 2–200 默认 20、窗口模式 cumulative/sliding、滑动窗宽度 1–1e9 秒默认 3 天）→ 选路径 → Pillow 逐帧合成 GIF（每帧 200ms 循环播放，右下角 UTC 时间戳）；初猜模式/无星历时间数据时明确拒绝并提示 | main_window.py:2223-2365；gif_exporter.py 全文 |

### A5. 右栏：参数面板（详见 B 节）

| 功能 | 描述 | 来源 |
|---|---|---|
| Pydantic→Qt 自动表单 | float→QDoubleSpinBox、int→QSpinBox、str+Literal→QComboBox、str→QLineEdit、Optional→勾选框+控件、list[float]→竖排 N 个 spinbox、epoch→QDateTimeEdit、Any→JSON 文本框 | params_panel.py:1-15, 903-976 |
| 参数分组 | 每工具声明组（形状参数/传播参数/修正参数/族参数/转移参数/目标参数/初值/预报参数/控制参数/仿真与误差），未分组字段自动归"其他"；组标题加粗+分隔线，整组隐藏时表头同步隐藏 | main_window.py:186-281, 845-854 |
| 轨道类型分支 | design_orbit 15 种轨道类型下拉（ORBIT_TYPE_DEFAULTS keys），切换即填该分支默认值并只显示分支字段 | params_panel.py:54-124；main_window.py:1042-1056 |
| 族类型分支 | 七族下拉 + 平动点下拉按族重建（共线 L1/L2、Lissajous 加 L3、三角 L4/L5、DRO 隐藏）+ 族默认值直接从 FamilyGenerationRequest 构造读取（不在 GUI 维护第二份表） | params_panel.py:132-180, 1106-1129；main_window.py:1160-1170 |
| 平动点联动裁剪 | 切平动点后刷新该点 valid_ranges 到控件范围/提示，超范围的当前值替换为该点默认值；范围内的用户输入保留 | params_panel.py:1177-1219；main_window.py:1147-1158 |
| 单位切换 | 17 个字段带单位下拉（见 B 节表），切单位换算显示值+范围+步长+小数位+label 后缀；换算缓存避免多次切换的舍入累积 | params_panel.py:247-385, 513-600 |
| 范围占位提示 | 数值框 placeholder + tooltip 显示"可填范围: ≥/≤/~/ min max 单位"，严格边界显示 >/<，无约束显示"无范围约束"，GUI 临时范围加注；tooltip = 字段 description + 范围提示 | params_panel.py:608-664 |
| Optional 勾选语义 | 未勾选收集为 None；duration/libration_point/max_amplitude_km 三个常用 Optional 不包勾选框直接展示默认值 | params_panel.py:387-401, 785-806, 957-974 |
| duration GUI 覆盖 | design_orbit 默认单位切"月"值 1（=1/12 年）；orbit_propagation 默认 30 天 | main_window.py:983-987, 1256-1278 |
| 重置参数按钮 | 重建当前工具面板恢复模型默认+分支默认 | main_window.py:718-721 |

### A6. 设置与持久化（chart_settings.py、ui_settings.py、main_window.py）

| 设置项 | 默认值 / 范围 | 持久化键 | 来源 |
|---|---|---|---|
| 轨道线宽 | 0.8（对话框 0.2–3.0 步 0.1） | QSettings(chart) orbit_linewidth | chart_settings.py:24, 90-95 |
| 颜色方案 | tab10（下拉：tab10/tab20/Set1/Set2/Dark2/Paired） | colormap | chart_settings.py:12, 26 |
| 地球标记大小 | 160（20–500） | earth_size | chart_settings.py:28, 102-109 |
| 月球标记大小 | 90（20–500） | moon_size | chart_settings.py:30 |
| L 点颜色 | #d62728（QColorDialog 取色器） | lp_color | chart_settings.py:32, 113-124 |
| L 点大小 | 80（20–300） | lp_size | chart_settings.py:34, 126-129 |
| 标注字号 | 10（6–24） | label_fontsize | chart_settings.py:36, 131-134 |
| Z 轴区间比例 | 0.5（0.1–1.0 步 0.05） | z_ratio | chart_settings.py:38, 136-141 |
| 基准字号 | 10pt（8–16），全部控件字号派生 | ui/font_size | ui_settings.py:21-22, 51-52 |
| 主题 | light（浅色/深色，QSS 全局样式表 + matplotlib rcParams 同步；重启生效） | ui/theme | ui_settings.py:16-18, 25-44, 119-131 |
| 分栏位置 | 见 A2 | ui/splitter/main、ui/splitter/center | main_window.py:468-471 |
| 轨道库目录 | 仓库根 catalog/ | catalog/dir | main_window.py:403-408 |

### A7. 后台工作线程（src/engine/workers.py，随迁移删除）

OrbitDesignWorker / ControlOrbitWorker / PropagationWorker / FamilyOrbitWorker / StabilityWorker / TransferDesignWorker：全部 QThread，log/finished/error/cancelled 四信号，开场打"开始…+参数"日志，族完成日志附各族标志性几何量范围（如 Halo z 振幅、NRHO 近月点高度），错误统一 "[错误码] 消息" 前缀。

---

## B. 参数表单细节清单（重点）

### B0. 控件生成规则（params_panel.py:672-976）

- float：范围取 ge/gt/le/lt（gt/lt 内缩 1e-8），默认 4 位小数步长 1.0；无上界时 max 扩到 1e12 容纳默认值；默认值填入或 0.0。
- int：同上；无约束 int 字段查 _INT_RANGE_OVERRIDES 兜底：num_controls(1,10000)、num_monte_carlo(1,1000)、n_orbits(1,100)，提示加注"部分边界模型未声明，GUI 临时"。
- 整数枚举下拉 _INT_COMBO_OPTIONS：collinear_point=1/2/3(L1/L2/L3)、libration_point=1/2、north_south=1北族/2南族、control_mode 6 项、is_nrho 0否/1是、special_mode 1 Lissajous(ẋ=0)/2 Halo/NRHO(ẋ=0 且 ż=0)。
- str 枚举下拉 _STR_ENUM_FIELDS：correction_method 仅暴露 two_level（segmented 由 e2m2e 自动分派不暴露）；continuation_direction=decrease-x0/increase-x0。
- epoch：QDateTimeEdit 日历弹出，格式 yyyy-MM-dd HH:mm:ss 整秒精度，范围 1900-01-01 至 2100-12-31，默认 2024-01-01 00:00:00；收集为 [年,月,日,时,分,秒]。
- JSON 文本占位提示 _FIELD_PLACEHOLDERS：perturbation '{"sun_body": 1, "planets": 1}（留空=默认全开）'；dyb '9 分量面质比系数，dyb[0] 等效面质比 m²/kg'；engine_layout 六喷管 positions/directions 布局示例（模式 4-6 必填）。

### B1. 可切换单位字段全表（params_panel.py:264-385，首个=标准单位，收集时换算回标准单位）

| 字段 | 单位选项（label: to_standard, decimals, step） |
|---|---|
| amplitude / perilune_height / amplitude_in / amplitude_out / semi_major_axis / max_amplitude_km / min_amplitude_km / perilune_height_max_km / amplitude_in_km / amplitude_out_km / match_tolerance_km | km(1.0) / m(1e-3, 0 位, 步 1000) / DU(=384400 km, 10 位, 步 0.001) |
| phase / phase_in / phase_out | 周期份额(1.0, 4 位, 步 0.05) / 度(1/360, 1 位, 步 5) / 弧度(1/2π, 3 位, 步 0.05) |
| inclination / arg_of_pericenter | 度(1.0, 2 位, 步 1) / rad(180/π, 4 位, 步 0.01) |
| duration | 年(1.0) / 月(1/12) / 日(1/365.25) / 时 / 秒(0 位, 步 86400) / TU(≈375676.97s) |
| output_step | 秒(1.0) / 时(3600) / 日(86400) / TU |
| control_interval / feedback_arc / momentum_interval | 天(1.0, 3 位, 步 1) / 秒 / TU |
| srp_offset_m（list 3 元） | m(1.0) / DU |

duration 的 GUI 标准单位是"年"，facade_bridge 构造请求时 ×SECONDS_PER_YEAR 换算为 e2m2e 的秒（facade_bridge_old.py:586-612, 787-803）。

### B2. 轨道设计 design_orbit（DesignOrbitRequest；GUI 分组：形状参数/传播参数/修正参数）

| 参数 | 控件 | 范围（模型约束） | GUI 默认（按 orbit_type 分支） | 提示/单位 |
|---|---|---|---|---|
| orbit_type | 下拉 | DRO/DPO/NRHO/Halo/Lissajous/Axial/L4/L5/L4_SPO/L5_SPO/L4_LPO/L5_LPO/L4_HORSESHOE/L5_HORSESHOE/ELFO | Halo（首项） | tooltip=模型 description |
| amplitude | spin+单位 | -110000 ≤ x ≤ 200000 km | DRO 60000 / DPO 20000 / Halo 30000 / Axial 5000 / L*_SPO 10000 / L*_LPO 50000 / L*_HORSESHOE 100000 | km/m/DU；DRO 默认注释：60000 是 GUI 认知默认（上游兜底 10000 是 DFH 标定值） |
| phase | spin+单位 | 0 ≤ x ≤ 1（周期份额） | DRO/DPO 0.5001 / NRHO 0.5 / Halo/Axial 0.0 / SPO/LPO/HORSESHOE 0.0 | 周期份额/度/弧度 |
| collinear_point | 下拉 | 1–3（L1/L2/L3） | NRHO/Halo/Lissajous/Axial=2（L2） | — |
| north_south | 下拉 | 1 北族 / 2 南族 | NRHO=2（南族） | — |
| perilune_height | spin+单位 | >0 且 ≤10000 km | NRHO 5000 / ELFO 200 | km/m/DU |
| amplitude_in / amplitude_out | spin+单位 | >0 且 ≤100000 km | Lissajous 2500/7500；L4/L5 8000/6000 | km/m/DU |
| phase_in / phase_out | spin+单位 | 0–1 | Lissajous 0.01/0.55；L4/L5 0/0 | 周期份额/度/弧度 |
| semi_major_axis | spin+单位 | >0 km | ELFO 6500（必填） | km/m/DU |
| inclination | spin+单位 | 0–180 度 | ELFO 75 | 度/rad |
| arg_of_pericenter | spin+单位 | ≥0 且 <360 度 | ELFO 270 | 度/rad；tooltip"近月点幅角（度），ELFO 用，默认 270" |
| epoch | QDateTimeEdit | 1900–2100 | 2024-01-01 00:00:00 | — |
| duration | spin+单位 | >0 | 模型 None（按类型兜底）；GUI 展示 1 月 | 年/月/日/时/秒/TU |
| output_step | spin+单位 | >0 秒 | 3600 | 秒/时/日/TU |
| perturbation | JSON 文本 | dict | 留空=默认全开 | 占位提示见 B0 |
| dyb | JSON 文本 | 9 元 list | 留空=默认 | 占位提示见 B0 |
| earth_degree / moon_degree | int spin | 2–120 | 10 / 10 | — |
| correction_method | 下拉 | two_level（唯一暴露项） | two_level | tooltip 含三方法分派说明 |
| correction_revolutions | int spin | ≥1 | 1 | — |

### B3. 轨道族生成 orbit_family_generation（FamilyGenerationRequest；分组：族参数）

公共字段始终显示：orbit_type（七族下拉）、n_orbits（int 1–100 默认 50，GUI 兜底范围）、libration_point（按族重建：共线族 L1/L2，Lissajous L1/L2/L3，三角族 L4/L5，DRO 隐藏）。sampling_mode 不暴露（各族唯一规则，模型自动填）。分支字段与默认值（apply_family_type_defaults 从 FamilyGenerationRequest(orbit_type=…) 实例直接读取，GUI 不维护第二份）：

| 族 | 显示字段（范围来自模型 valid_ranges，切平动点联动刷新） | GUI 预填 |
|---|---|---|
| Halo | max_amplitude_km（带符号区分北/南族；L2 默认 30000，切 L1 超范围自动换 L1 默认 25000） | libration_point=2, max=30000 |
| NRHO | north_south（1/2）、perilune_height_max_km | 按模型 |
| Axial | max_amplitude_km（带符号上/下族） | 按模型 |
| Lissajous | amplitude_in_km(>0)、amplitude_out_km(>0)、phase_in(0–1)、phase_out(0–1) | 按模型 |
| SPO / LPO / Horseshoe | min_amplitude_km、max_amplitude_km、continuation_direction（decrease-x0/increase-x0）、match_tolerance_km(>0) | 按模型 |
| DRO | min_amplitude_km、max_amplitude_km（月心族，无平动点字段） | 按模型 |

收集时 _family_request_params 按族过滤：隐藏分支残留值与未勾选 Optional 的 None 都不进请求（e2m2e 5.7.1 起 model_fields_set 拒绝跨族字段）；DRO 的空字符串平动点也过滤（main_window.py:291-304）。

### B4. 转移设计 transfer_design（TransferDesignRequest；分组：转移参数/目标参数）

| 参数 | 控件 | 范围 | 默认 | 说明 |
|---|---|---|---|---|
| transfer_type | 下拉 | 仅 HMN/LGA（WSB/low_thrust 被上游阻塞未暴露） | HMN | tooltip："HMN 直接霍曼转移；LGA 月球引力辅助（目标取选中轨道工件）" |
| tli_epoch | QDateTimeEdit | 1900–2100 | 2025-01-01 00:00:00 | 模型 Any 无默认，GUI 换日期编辑 |
| parking_alt_km | spin | >0 km | 200 | 停泊轨道高度 |
| incl_deg | spin | 0–180 度 | 28.5 | 轨道倾角 |
| target_orbit_radius_km | spin | >0 km | 无（HMN 必填） | 仅 HMN 显示（LGA 隐藏行） |
| tof_range | — | [min,max] 天 | 无 | 仅 HMN 显示；label"飞行时间范围 (天)" |
| flight_path_deg / target_ephemeris / lga_search_params / wsb_search_params | — | — | — | 隐藏（模型仅支持 0 / 由选中工件注入 / 算法层默认） |

切 transfer_type 时 HMN 专属两字段（含组表头）整体显示/隐藏；收集后非 HMN 剔除两字段（main_window.py:1100-1126, 1422-1427）。

### B5. 轨道预报 orbit_propagation（PropagationRequest；分组：初值/预报参数）

| 参数 | 控件 | 范围 | 默认 | 说明 |
|---|---|---|---|---|
| initial_state | 6 个竖排 spin（±1e12，"无范围约束"） | 长度 6 | 选中星历工件末端状态预填 | label"初值 (GCRS km, km/s)" |
| epoch | QDateTimeEdit | 1900–2100 | 2024-01-01（无选中时） | 选中时预填末端时刻；SPICE 不可用时日志提示手填 |
| duration | spin+单位 | >0 | GUI 默认 30 日 | 年/月/日/时/秒/TU（标准单位年，facade 换秒） |
| output_step | spin+单位 | >0 秒 | 3600 | 秒/时/日/TU |
| force_config | 文本框（解包 Optional） | JSON dict | 留空 | 占位"JSON 力模型配置（留空 = 默认三体：地球点质量 + 月球/太阳第三体）"；非法 JSON 运行前拦截并报"力模型配置 JSON 无效: …" |

### B6. 轨道保持 control_orbit（ControlOrbitRequest；ControlOrbitDialog 模态弹窗，分组：控制参数/仿真与误差/其他）

隐藏字段：input_ephemeris、input_record_id（由源工件注入：库记录含星历段走 record_id 谱系直连，否则内存星历）、mu（源注入）。GUI 覆盖默认：control_interval=0.25 天、feedback_arc=0.125 天（短弧适配，上游默认 30/28 天面向多年星历）。special_mode 按源轨道类型锁定：HALO/NRHO→2（ẋ=0 且 ż=0），其余→1，控件禁用。

| 参数 | 控件 | 范围 | 模型默认 | label |
|---|---|---|---|---|
| control_mode | 下拉 | 1–6 | 1 | 1 目标点（宽松）/2 目标点（严格）/3 特征点/4-6 同名+角动量管理 |
| is_nrho | 下拉 | 0/1 | 0 | 目标为 NRHO：否/是 |
| special_mode | 下拉（锁定） | 1/2 | 1 | 特征点模式 |
| control_interval | spin+单位 | >0 天 | 30.0（GUI 0.25） | 控制间隔（天/秒/TU） |
| feedback_arc | spin+单位 | >0 天 | 28.0（GUI 0.125） | 反馈弧段 |
| special_crossings | int spin | ≥1 | 3 | 特征点穿越次数 |
| num_controls | int spin | 1–10000 | 120 | 控制次数 |
| tight_tolerance_km | spin | >0 km | 0.1 | 严格控制位置容差 |
| tight_max_iter | int | ≥1 | 6 | 严格控制迭代上限 |
| special_damping_factor | spin | >0 且 ≤1 | 1.0 | 特征点迭代阻尼因子 |
| num_monte_carlo | int | 1–1000 | 5（tooltip 注明惯例 100） | 蒙特卡洛样本数 |
| output_step | spin+单位 | >0 秒 | 86400 | 输出步长（秒/时/日/TU） |
| position_accuracy | spin | >0 m | 1500 | 测定轨位置误差 |
| velocity_accuracy | spin | >0 m/s | 0.002 | 测定轨速度误差 |
| thrust_angle_err | spin | ≥0 度 | 0.333 | 推力方向角误差 |
| thrust_mean / thrust_min / thrust_max / thrust_total | spin | >0（min ≥0 无强制） m/s | 10 / 0.1 / 100 / 1000 | 推力中点值/最小开机/最大开机/累计上限 |
| thrust_rel_err | spin | ≥0 | 0.003 | 推力相对误差 |
| thrust_abs_err | spin | ≥0 m/s | 0.033 | 推力绝对误差 |
| srp_error_level | spin | ≥0 | 0.1 | 光压弧段随机误差 |
| perturbation / dyb / earth_degree / moon_degree | JSON/int | 阶数 2–120 | 2/2 | 控制力模型（dyb 9 元） |
| real_perturbation / real_dyb / real_earth_degree / real_moon_degree | JSON/int | 阶数 2–120 | 10/10 | 真实力模型 |
| engine_layout | JSON 文本 | — | 无 | 占位含六喷管示例（模式 4-6 必填） |
| momentum_interval | spin+单位 | >0 天 | 5.0 | 角动量卸载间隔 |
| srp_offset_m | 3 竖排 spin+单位 | list 3 | 无 | SRP 压心偏移（m/DU） |
| spacecraft_mass | spin | >0 kg | 1000 | 航天器质量 |
| srp_torque | 3 竖排 spin | list 3 | 无 | SRP 力矩 N·m |
| 弹窗专属校验 | — | 仿真时长 =(N-2)×间隔+反馈弧 > 源星历覆盖天数时拦截，日志给出完整算式与两条出路 | — | control_orbit_dialog.py:359-376 |
| 弹窗专属交互 | 运行中关闭弹窗视为取消：先请求停止，取消信号到达后再关 | — | — | control_orbit_dialog.py:452-461 |

### B7. 稳定性分析（右键触发，无表单）

输入取选中 orbit 的 state_data/times/mu（mu 缺失由 FacadeBridge 用默认地月系统兜底）；输出对话框只读文本：稳定性分类（类型/稳定/不稳定/稳定裕度/Floquet 模最大最小/最大 Lyapunov 指数）、稳定性指数（ν1/ν2/ν3/Broucke）、分岔类型与检测标志、Floquet 乘子逐个（实虚部+模）、6×6 单值矩阵（main_window.py:1851-1926）。

---

## C. 迁移后可能丢失/难以迁移的功能点

对照对象：本分支 HEAD（755b567）的 Tauri 前端（frontend/src/App.tsx 325 行、OrbitCanvas.tsx 149 行、ParamsPanel.tsx 130 行等）。64c943b 提交信息自述新 UI 覆盖"参数面板/项目树/画布/库过滤/i18n/设置持久化/动画导出"，以下为逐项核对后在新前端源码中找不到对应实现的点（均以代码为据，非猜测）：

1. **坐标系切换（会合系/惯性系）整条链路**——旧 GUI 惯性系画 GCRS km + SPICE 月球真实轨迹 + 旋转近似降级（main_window.py:2115-2132、canvas.py:819-1127）；新 OrbitCanvas.tsx 无 inertial/synodic 任何代码（App.tsx grep 无命中）。画布目前只有会合系无量纲轨迹。
2. **投影切换（XY/XZ/YZ/四视图）与 2D 视图**——旧 canvas_toolbar.py 四投影按钮 + canvas.py 2D 渲染分支；新前端只有 Three.js 3D 视图（OrbitCanvas.tsx 149 行内无 projection 概念）。
3. **绘制中心切换（质心/月球/L1/L2）与对称居中**——canvas.py:609-626、441-447；新前端无 center 概念。
4. **时间轴（ET 滑块 + 飞行器/月球此刻 marker + UTC 标签 + 10Hz 节流）**——timeline_bar.py 全文、canvas.py:562-601；新前端无 timeline。这是 64c943b 前最后一个 commit（fa2d0e3，#395/#396）刚做完的功能，迁移提交信息未提及其在新 UI 的对应物。
5. **GIF 参数化导出（帧数/累计/滑动窗/UTC 时间戳/Pillow 逐帧）→ 换成固定 8 秒自转 webm 录屏**——gif_exporter.py vs canvasRecorder.ts（App.tsx:40-58：录制 8 秒 autoRotate，无帧数/窗口/时间轴语义；时间轴本身已不存在，无法做逐帧时间推进动画）。
6. **单位切换体系（17 个字段 km/m/DU、周期份额/度/弧度、年/月/日/时/秒/TU 等）与换算精度缓存**——params_panel.py:264-600；新 ParamsPanel.tsx 的 number input 只有 min/max，无单位下拉与换算。
7. **范围占位提示与 tooltip（"可填范围: ≥ min ~ ≤ max 单位"、严格边界 >/<、"无范围约束"、GUI 临时范围加注、description 拼接）**——params_panel.py:608-664；新前端 Field 组件仅显示 description 首行（ParamsPanel.tsx:72-76），min/max 只落在 input 属性上不可见。
8. **轨道类型分支默认值表（15 类型 GUI 认知默认，如 DRO 60000 km）与切类型填默认**——params_panel.py:54-124；新前端切 orbit_type 只裁剪字段并保留旧值，不填分支默认（ParamsPanel.tsx:100-110），且 ORBIT_TYPES/裁剪规则来自 schema.ts 静态导出而非 e2m2e valid_ranges。
9. **族平动点联动（按族重建平动点下拉 + 切点刷新 valid_ranges + 超范围值自动换该点默认）**——params_panel.py:164-180, 1177-1219；新前端无此联动。
10. **轨道保持弹窗整套（30+ 参数、控制模式下拉、special_mode 按源锁定、短弧默认覆盖、时长覆盖校验、链式站保、弹窗内日志）**——control_orbit_dialog.py 全文；新前端工具下拉含 control_orbit schema 但 App.tsx 无选中产物注入 input_record_id/星历的接线，也无时长校验。
11. **稳定性分析（右键 → 后台计算 → 结果对话框 + 落盘）**——main_window.py:1796-1926；新前端无 stability 入口（grep 无命中）。
12. **转移设计（HMN/LGA、目标注入、类型联动显隐）**——main_window.py:1403-1465；新前端 transfer_design schema 存在但无目标工件注入/联动逻辑。
13. **轨道预报初值预填（选中星历末端状态 + SPICE 历元换算）**——main_window.py:733-799；新前端无预填。
14. **记录详情面板（谱系/断链标记、Jacobi/振幅区间展示、tags/note 教学标注、族成员提升）**——record_detail_panel.py 全文；新前端无详情面板。
15. **项目树右键菜单与多选渲染**——project_tree.py:116-168；新 ProjectTree.tsx 只有单选 + 删除按钮（App.tsx:189-213）。
16. **教学案例包导出（catalog_export zip/目录）**——main_window.py:1724-1742；新前端无导出（catalog_export.json schema 存在但未接线）。
17. **轨道库目录切换**——main_window.py:553-566；新前端无。
18. **SPICE 内核首次启动引导（下载进度/指定目录/跳过三选）**——kernel_setup.py；新前端无对应向导。
19. **日志面板（时间戳、worker 进度流、错误码前缀）与 5 秒状态栏消息**——log_panel.py、main_window.py；新前端只有一行 progressMessage（App.tsx:34, 262-265）。
20. **界面设置（全局字号 8–16、浅/深主题 QSS+matplotlib 同步）**——ui_settings.py；新前端 chartSettings.ts 无字号/主题项（仅有轨道线宽/颜色循环/天体与平动点标注/z 比例，localStorage）。
21. **分栏布局持久化与重置**——main_window.py:445-471, 539-545；新前端为固定 230px/300px 两栏（App.tsx:165, 215），无拖拽与持久化。
22. **停止/任务互斥语义**——旧 GUI 停止按钮 + 弹窗互斥（main_window.py:723-843）；新前端仅 busy 禁用执行按钮，无取消。
23. **过滤栏三态段过滤与 Jacobi/振幅数值区间**——catalog_filter_bar.py:73-81；新 CatalogFilterBar.tsx 依据 commit 信息含族/平动点/Jacobi/振幅区间/标签，但三态段（含/不含）过滤是否齐备需在界面核实（此条按代码 grep 程度列为"待核实"）。
24. **新增而无对应旧功能**（反向差异，供参考）：中英文界面切换 i18n（frontend/src/i18n.ts，PyQt 版仅中→英翻译文件机制且 main.py 未接线语言切换）。

补充事实：迁移提交 64c943b 自述"已知遗留"两项上游问题（#525/#526，后在 e2m2e 5.8.5 解决），并声明图表设置对齐 PyQt 版"可调参数面"（线宽/颜色循环/天体与平动点标注/z 轴比例）、动画导出"替代 PyQt 版 gif_exporter"；但上表 1–22 项在该提交信息与新前端代码中均无对应声明或实现。