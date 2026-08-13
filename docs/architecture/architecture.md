# transfer-orbit-design 架构设计

> 本文描述 transfer-orbit-design（以下简称 tod）的**最终形态**架构。逐项架构决策见 `docs/adr/`。

## 总体定位

tod 是 **e2m2e 的 GUI 前端**。它不实现任何轨道力学算法，只做三件事：

1. **调用**——通过 e2m2e Facade API 发起计算任务（轨道设计、轨道族生成、轨道保持、稳定性分析）。
2. **管理**——追踪用户工作会话中的全部计算产物（轨道、轨道族、转移结果），提供结构化的数据导航和管线串联。
3. **呈现**——将计算结果以内嵌可视化的方式展示在主窗口中，支持 3D/2D 轨道图、多轨道叠加、地月系统标注。

用户不需要知道 e2m2e 的内部结构，也不需要手动管理文件路径。tod 把 e2m2e 的能力封装为"选工件 → 选操作 → 看结果"的三步交互。

## 总体分层

按依赖方向由内向外，四层。**内层不感知外层**。

| 层级 | 名称 | 职责 |
|:---|:---|:---|
| 第1层 | 数据层 `src/model/` | Project、Artifact、output/ 扫描、元数据 |
| 第2层 | 执行层 `src/engine/` | Facade/算法层调用（QThread 工作线程）、结果落盘 |
| 第3层 | 表现层 `src/view/` | Qt 控件：项目树、可视化画布、参数面板、日志 |
| 第4层 | 入口 `src/app/` | 主窗口组装、设置、国际化、主题 |

**分层哲学**：

- **数据层不知道 GUI 的存在**。Project/Artifact 是纯 Python 数据类，可在测试中独立使用。
- **执行层不知道 Qt 的存在**。它只负责"接收参数 → 调 e2m2e → 返回结果 + 落盘"。线程管理由表现层的 QThread 包装处理。
- **表现层不调 e2m2e**。它只和数据层、执行层的接口交互。
- **入口层只做组装**。它把数据层、执行层、表现层粘在一起，不包含业务逻辑。

## 顶层结构（最终形态）

```
transfer-orbit-design/
├── src/                   # 核心代码（src layout）
│   ├── model/             # 第1层 数据层
│   │   ├── project.py     # Project 容器
│   │   ├── artifact.py    # Artifact 数据类
│   │   └── discovery.py   # output/ 扫描与 Artifact 重建
│   ├── engine/            # 第2层 执行层
│   │   ├── facade_bridge.py # Facade API 桥接（薄封装）
│   │   ├── workers.py     # QThread 工作线程（设计/保持/族生成/稳定性）
│   │   ├── persistence.py # 结果落盘（写 output/ + 元数据 JSON）
│   │   └── viz_adapter.py # 画布绘图适配（地月/L 点/坐标系变换）
│   ├── view/              # 第3层 表现层
│   │   ├── project_tree.py  # 项目树（Artifact 分组展示 + 右键操作）
│   │   ├── canvas.py      # 内嵌 matplotlib 画布（FigureCanvasQTAgg）
│   │   ├── canvas_toolbar.py # 可视化工具栏（投影/坐标系/图层/动画）
│   │   ├── params_panel.py # 参数面板（从 Pydantic 模型自动生成）
│   │   ├── chart_settings.py # 图表设置（QSettings 持久化）
│   │   ├── gif_exporter.py # GIF 动画导出
│   │   └── log_panel.py   # 日志面板（结构化输出）
│   ├── app/               # 第4层 入口
│   │   ├── main.py        # QApplication 启动 + SPICE 内核引导 + 窗口组装
│   │   ├── main_window.py # 主窗口（三栏 Splitter 布局 + 工具调度）
│   │   ├── kernel_setup.py # 首次启动内核缺失弹窗引导（下载/指定/跳过）
│   │   └── i18n/          # 国际化资源（尚未接入，界面固定中文）
│   ├── commons/           # 跨层常量与共享工具
│   │   ├── constants.py   # DU/TU/物理常量
│   │   ├── units.py       # 单位换算（年/月/日/TU、km/DU）
│   │   ├── kernels.py     # 内核下载/可用性判断（CLI 与 GUI 共用）
│   │   ├── paths.py       # 内核目录探测与配置持久化
│   │   ├── orbits.py      # GEO/LEO 轨道几何
│   │   └── viz/           # 收编自 e2m2e tools/viz 的绘图组件（自维护）
│   └── __init__.py
├── docs/                  # 文档
│   ├── adr/               # 架构决策记录
│   ├── architecture/      # 架构说明
│   └── source/            # Sphinx 源（docs/README.md 说明维护流程）
├── tests/                 # 测试（app/commons/engine/model/view 分层）
├── scripts/               # 独立工具脚本（download_kernels.py）
├── output/                # 运行时输出（数据持久化源）
└── pyproject.toml
```

**删除的旧代码**（大爆炸替换）：

| 旧目录 | 原因 |
|---|---|
| `tod/gui/` | 被 `src/view/` + `src/app/` 替代 |
| `tod/generates/` | 被 e2m2e Facade API 直调替代 |
| `tod/transfers/` | 被 e2m2e Facade API 直调替代 |
| `tod/scripting/` | SCRIPT_ENTRY 机制废弃 |
| `tod/commons/e2m2e_compat.py` | 不再需要旧路径兼容 |
| `plot/`（顶层） | v3.2.1 起 e2m2e 删除 `tools/viz`，绘图组件收编为 `src/commons/viz/` 由本项目自维护 |

## 第1层 数据层 `src/model/`

### Artifact

一次计算的产出物。纯数据类，不依赖 Qt 或 e2m2e。

```python
@dataclass
class Artifact:
    artifact_id: str        # UUID 前 8 位
    artifact_type: str      # "orbit" | "family" | "transfer" | "ephemeris"
    label: str              # 用户可见名称
    orbit_type: str         # DRO/Halo/NRHO/...
    source_tool: str        # 产生此 Artifact 的 Facade 方法名
    state_data: ndarray     # 状态矩阵 (n, 6)，用于可视化
    times: ndarray          # 时间向量 (n,)
    output_path: Path | None # 对应的 output/ 文件（自动落盘后填入）
    extra: dict             # 元数据（Jacobi、收敛信息、初始状态等）
    created_at: datetime    # 创建时间
```

### Project

管理一次工作会话的全部 Artifact。**Project 不做持久化**——持久化由 `output/` 目录承担。

```python
class Project:
    name: str
    artifacts: list[Artifact]

    def add(artifact) -> None
    def remove(artifact_id) -> bool
    def get_by_id(artifact_id) -> Artifact | None
    def get_by_type(type) -> list[Artifact]
    def get_by_orbit_type(orbit_type) -> list[Artifact]
    def find_upstream(artifact) -> Artifact | None  # 按 output_path 因果链追溯
```

### Discovery

GUI 启动时扫描 `output/` 目录，重建 Project。

```python
def discover_artifacts(output_dir: Path) -> list[Artifact]:
    """扫描 output/ 下所有 JSON，按文件名约定识别类型，
    读取元数据，构建 Artifact 列表。"""
```

文件命名约定（与现有 output/ 结构兼容）：

| 子目录 | 文件名模式 | Artifact 类型 |
|---|---|---|
| `output/<type>/`（dro/halo/nrho/lissajous/l4/l5） | `<type>_<14位时间戳>.json` | orbit |
| `output/family/` | `family_<ts>.json` | family（Halo 族） |
| `output/ephemeris/` | `orbit_ephemeris_<ts>.json` | ephemeris（轨道保持） |
| `output/stability/` | `<label>_stability_<ts>.json` | 不进项目树（对话框展示） |
| `output/dro/` | `dro_*_family_*.json`（遗留） | family（旧 GUI 的 DRO 族，兼容识别） |

## 第2层 执行层 `src/engine/`

### FacadeBridge

e2m2e Facade API 的薄封装。处理配置注入、异常翻译、结果落盘。

```python
class FacadeBridge:
    def __init__(self, config: Config): ...

    def design_orbit(self, **params) -> OrbitDesignResultData:
        """调 e2m2e.algorithm.design.design_orbit，
        返回可跨线程传递的结果 DTO，同时写 output/。"""

    def generate_family(self, **params) -> FamilyResultData: ...
    def analyze_stability(self, **params) -> StabilityResultData: ...
    def control_orbit(self, **params) -> ControlResultData: ...
```

**关键设计**：

- **直接调用 algorithm 层，不经过 Facade 门面**。原因：`Facade.design_orbit()` 返回的 `DesignOrbitResponse` 剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 `OrbitDesignResult`（含 `cr3bp_orbit`、`ephemeris`）用于可视化。Facade 门面是 MCP/CLI 的接口层，GUI 作为 e2m2e 的深度集成者直接使用算法层（ADR-0011）。
- **e2m2e 5.6.5 起 `design_orbit` 首参为 `DesignOrbitRequest`**（散字段不再支持），facade 把 GUI 收集的 kwargs 包成 request 再调用；`duration` 由面板年单位换算为秒。
- **结果 DTO（Data Transfer Object）**：可跨线程边界传递的纯数据类，不持有 e2m2e 对象引用。包含 numpy 数组（状态矩阵、时间向量）和标量元数据。
- **异常翻译**：e2m2e 异常 → 结构化错误码 + 用户友好消息（`src/engine/exceptions.py`）。

### Workers

QThread 工作线程，每个 Facade 方法一个 Worker 类。

```python
class OrbitDesignWorker(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal(OrbitDesignResultData)
    error = pyqtSignal(str)
```

Workers 是**执行层与表现层的边界**：它们使用 PyQt6 的 QThread 和 pyqtSignal，因此在技术上依赖 Qt。这是有意的设计选择——避免引入额外的线程-通信抽象层。

### Persistence

结果落盘。利用 e2m2e 算法层自身的 `write_ephemeris()` / `save_to_file()` 方法。

```python
def save_artifact(result_data, output_dir: Path) -> Path:
    """将计算结果写入 output/ 对应子目录，
    返回文件路径。同时生成元数据 JSON。"""
```

## 第3层 表现层 `src/view/`

### 项目树 `project_tree.py`

主窗口左侧。**项目主导**：按 Artifact 类型分组展示，右键菜单暴露可用操作。

```
📁 项目: Transfer Orbit Design
├─ 🪐 轨道
│  ├─ DRO (20260813...)        ← 点击 → 渲染到画布
│  └─ Halo (20260813...)
├─ 🌀 轨道族
│  └─ Halo Family (20 orbits)
└─ 📡 星历
   └─ orbit_ephemeris_...
```

右键菜单上下文感知：

| 选中 Artifact 类型 | 右键可用操作 |
|---|---|
| orbit（含星历） | 轨道保持、稳定性分析、删除 |
| orbit（仅 CR3BP） | 稳定性分析、删除 |
| family | 删除 |
| ephemeris（保持结果） | 删除 |

### 可视化画布 `canvas.py`

主窗口中央。内嵌 `FigureCanvasQTAgg` + `NavigationToolbar2QT`。

**标准可视化能力**：

| 能力 | 说明 |
|---|---|
| 3D 轨道图 | CR3BP 旋转坐标系下的轨道，可拖拽旋转 |
| 2D 投影切换 | XY / XZ / YZ 三视图 + 四视图（2×2 网格），工具栏按钮切换 |
| 坐标系切换 | 会合系（CR3BP 旋转系，无量纲）/ 惯性系（GCRS，km），惯性系下月球沿真实轨迹移动 |
| 中心切换 | 质心 / 月球 / L1 / L2（会合系），惯性系以地球为原点 |
| 绘制内容 | 初猜 / 星历 / 叠加三选一（轨道设计产物同时携带两份轨迹） |
| 多轨道叠加 | 选中多个 Artifact 时叠加渲染，自动分配颜色 |
| 地月系统标注 | 地球、月球位置 + 五个拉格朗日点，`viz_adapter` 提供 |
| 轨道族渲染 | 族成员逐条渲染，`viz` 组件提供 |
| 图表设置 | 线宽/颜色方案/标注大小/字号/Z 区间比例，QSettings 持久化 |
| GIF 动画导出 | 按时间等分采样逐帧渲染，Pillow 合成，累积/滑动窗口 |
| 导航工具栏 | 缩放/平移/旋转/保存图片 |

**画布状态**：

```python
class CanvasState:
    projection: str         # "3d" | "xy" | "xz" | "yz" | "quad"（四视图）
    frame: str              # "synodic"（会合系） | "inertial"（GCRS）
    center: str             # "barycenter" | "moon" | "L1" | "L2"（会合系）
    plot_content: str       # "guess" | "ephemeris" | "overlay"（绘制内容，与 frame 正交）
    visible_artifacts: list[str]  # 当前显示的 artifact_id 列表
    show_bodies: bool       # 是否显示地月
    show_libration: bool    # 是否显示拉格朗日点
    equal_aspect: bool      # 是否等比例（默认 True；False 各轴独立缩放填满）
```

### 参数面板 `params_panel.py`

主窗口右侧。**从 e2m2e Pydantic 模型自动生成**。

生成规则：

| Pydantic 字段类型 | Qt 控件 |
|---|---|
| `float` (有 ge/le) | `QDoubleSpinBox` (range=ge..le) |
| `int` (有 ge/le) | `QSpinBox` (range=ge..le)；字段在 `_INT_COMBO_OPTIONS` 时改 `QComboBox`（值存 itemData） |
| `str` (有 enum) | `QComboBox` |
| `str` (无 enum) | `QLineEdit` |
| `list[float]` | 多个 `QDoubleSpinBox` |
| `Any` (可选) | `QLineEdit` (JSON 输入) |

字段元数据映射：

| Pydantic Field 信息 | Qt 属性 |
|---|---|
| `description` | 控件 tooltip（数值控件附加"可填范围"提示） |
| `default` | 控件默认值 |
| `ge/le/gt/lt` | 控件范围；也是框内清空时的"可填范围"占位提示 |
| `FIELD_UNIT_OPTIONS[field]` | 单位下拉（首个=标准单位，切换仅改显示值；收集时换算回标准单位，换算缓存保证多次切换精确往返） |

单位下拉覆盖所有可换算参数：距离 km/m/DU、时间 年/月/日/时/秒/TU（或 秒/时/日/TU、天/秒/TU）、角度 度/rad、相位 周期份额/度/弧度、SRP 偏移 m/DU（list 容器整体换算）。无量纲计数（阶数/圈数/样本数）与字典/JSON 字段无可换算单位。

每个工具类型注册一个参数面板生成函数：

```python
# src/engine/facade_bridge.py 中的注册表（与 e2m2e facade 工具清单对齐）
TOOL_REGISTRY: dict[str, ToolSpec] = {
    "design_orbit": ToolSpec(request_model=DesignOrbitRequest, ...),
    "control_orbit": ToolSpec(request_model=ControlOrbitRequest, ...),
    "orbit_family_generation": ToolSpec(request_model=FamilyGenerationRequest, ...),
    "orbit_stability": ToolSpec(request_model=None, ...),  # 右键触发，不进工具下拉
    "transfer_design": ToolSpec(request_model=None, enabled=False, ...),  # 即将提供
    # ... 其余 e2m2e facade 工具同构灰显
}
```

`TOOL_REGISTRY` 从 `e2m2e.api.Facade.mcp_tools()` 自动派生全量清单：已接入的
工具 enabled；e2m2e 已实现但 GUI 未接入、e2m2e 占位的工具灰显"即将提供"。
e2m2e 新增工具时 GUI 清单零改动跟随。`ToolSpec.description`（工具说明）展示在
工具选择器下方。稳定性分析无参数面板（右键轨道触发），`enabled=False` 仅表示
下拉灰显，右键菜单另行启用。轨道族生成使用本地 `FamilyGenerationRequest` 模型
（e2m2e 无对应 Request，已提上游 issue）。

### 日志面板 `log_panel.py`

主窗口中央标签页（与可视化画布并列）。显示当前任务的结构化日志：

```
[14:32:01] 开始设计 DRO 轨道...
[14:32:01] 参数: amplitude=40000.0 km, duration=1.0 yr
[14:32:15] 微分修正收敛 (3 次迭代, 残差 2.3e-12)
[14:32:18] 星历修正完成 (two_level, max_res=1.6e-02 km)
[14:32:20] ✓ 设计完成: DRO, C_J=3.005811
```

## 第4层 入口 `src/app/`

### 主窗口布局 `main_window.py`

```
┌─ 左侧 (20%) ────┬─ 中间 (55%) ─────────────┬─ 右侧 (25%) ─────┐
│                  │                           │                   │
│  项目树          │  [📊 可视化 | 📋 日志]     │  选择工具 [▾]      │
│  (QTreeWidget)   │                           │  轨道设计          │
│                  │  ┌───────────────────┐    │  轨道保持          │
│  🪐 轨道         │  │                   │    │  轨道族生成        │
│   ├ DRO ...      │  │   3D 轨道图       │    │                   │
│   └ Halo ...     │  │   (可交互)        │    │  ─────────────    │
│                  │  │                   │    │  轨道类型  [DRO ▾] │
│  🌀 轨道族       │  └───────────────────┘    │  振幅    [60000]   │
│  📡 星历         │  [3D|XY|XZ|YZ|四视图]      │  历元    [...]    │
│                  │  [会合系|惯性系] [质心|月球]│  时长    [1 月]    │
│                  │  [叠加|初猜|星历]          │                   │
│                  │  [地月] [L1-L5] [等比]     │  [▶ 运行]          │
└──────────────────┴───────────────────────────┴───────────────────┘
│ 状态栏: 就绪 | SPICE: ...                                           │
└──────────────────────────────────────────────────────────────────┘
```

**Splitter 布局**：三栏可拖拽调整比例。默认 20:55:25。

### 设置与配置

| 设置项 | 存储位置 | 说明 |
|---|---|---|
| SPICE 内核目录 | 配置文件 `kernels_dir.txt`（`~/.config/transfer-orbit-design/`） | 首次启动缺失内核时弹窗引导（下载/指定/跳过），探测顺序见 `src/commons/paths.py` |
| 图表设置（线宽/颜色/标注/字号/Z 比例） | QSettings | `src/view/chart_settings.py`，菜单"设置 → 图表设置…" |
| 界面语言 | — | i18n 基础设施已就位但未接入，界面固定中文 |

### 入口 `main.py`

```python
def main():
    app = QApplication(sys.argv)
    # 1. 探测 SPICE 内核（缺失时弹窗引导下载/指定/跳过）
    # 2. 扫描 output/ 重建 Project (Discovery)
    # 3. 创建 MainWindow (组装 project_tree + canvas + params + log)
    # 4. show()
    sys.exit(app.exec())
```

## 依赖方向规则

```
src/app/     →  src/view/ + src/engine/ + src/model/
src/view/    →  src/model/ + src/engine/（仅 workers 的信号类型）
src/engine/  →  src/model/（仅 Artifact/Project 类型）+ e2m2e
src/model/   →  numpy（纯数据）
src/commons/ → 无依赖（常量）；其中 `src/commons/viz/` 为收编的第三方绘图组件，仅依赖 e2m2e 数据类型（不承担本仓类型标准，见 `pyproject.toml` 的 pyright exclude）
```

**硬规则**：

1. `src/model/` 不 import `src/view/` 或 `src/engine/`。
2. `src/view/` 不直接 import e2m2e。所有 e2m2e 调用经 `src/engine/` 桥接。
3. `src/engine/` 不 import `src/view/`（Workers 的信号是技术性例外，仅 import PyQt6.QtCore）。
4. `src/commons/` 不被 `src/model/`、`src/engine/`、`src/view/` 反向依赖（commons 是叶子）。

## 可视化架构

### 画布内部结构

```
FigureCanvasQTAgg
└── Figure (8x6, dpi=100)
    └── Axes (3d 或 2d，由 projection 切换)
        ├── 轨道线 (Line3D / Line2D)
        ├── 起点标记 (scatter)
        ├── 地球 (scatter + icon, show_bodies=True)
        ├── 月球 (scatter + icon, show_bodies=True)
        └── 拉格朗日点 L1-L5 (scatter + label, show_libration=True)
```

### 渲染流程

```
用户点击 Artifact
  → Project.get_by_id()
  → CanvasState 更新 visible_artifacts
  → canvas.render(CanvasState)
    → 根据 projection 创建 Axes (3d / 2d / quad)
    → 根据 frame 选择坐标系（synodic：无量纲；inertial：GCRS km）
    → 遍历 visible_artifacts，按 plot_content 绑定 state_data / 星历数组
    → 如果 show_bodies: 绘制地月位置（inertial 下月球沿 SPICE 轨迹移动）
    → 如果 show_libration: 绘制 L1-L5（仅 synodic）
    → fig.tight_layout() + canvas.draw()
```

### 颜色策略

- 单轨道：tab10 调色板首个颜色
- 多轨道叠加：tab10 调色板自动分配；颜色方案可在图表设置中切换
- 轨道族：m 条成员按 viridis colormap 渐变着色
- 叠加视图：初猜实线、星历虚线，TAB10 相邻色区分
- 起点：绿色圆点；终点：红色圆点
- 地球：蓝色大圆 + 图标；月球：灰色大圆 + 图标；L 点：黑色三角 + 标签

## 管线串联

用户操作一个 Artifact 后，项目树的右键菜单展示可用的下一步操作。

**因果链**：

```
Artifact A (DRO orbit, 含星历)
  → 右键 → "轨道保持" → 调 control_orbit(ephemeris=A.extra["ephemeris"])
    → 注册 Artifact B (ephemeris)
  → 右键 → "稳定性分析" → 调 analyze_stability(states=A.state_data)
    → 显示结果弹窗 + 落盘 output/stability/
```

**数据流**：Artifact 的 `state_data` / 星历数组在内存中传递（numpy 数组引用），不经过文件 I/O。落盘是并行行为（Persistence 模块异步写 output/）。

## 工具范围（当前）

GUI 的工具范围固定为四件：轨道设计、轨道保持、轨道族生成（Halo 北族）、
稳定性分析（右键）。e2m2e 的转移设计、低推力、流形分析等能力**不在 GUI
范围内**——需要脚本化工作流时直接使用
[e2m2e CLI](https://github.com/cislunarspace/e2m2e)。这与早期版本"灰显
占位等待 e2m2e 实现"的策略不同：不承诺 GUI 承载全部算法能力，避免维护
一批永远点不亮的按钮。

## 依赖

- **运行时**：PyQt6, PyQt6-WebEngine, matplotlib, numpy, scipy, pillow（GIF 合成）
- **e2m2e**：PyPI 依赖（`e2m2e>=5.6.8`），运行时经 `src/engine/facade_bridge.py` 调用 algorithm 层
- **calcephpy**：经 e2m2e→r2s2 传递依赖（Windows 用预编译 wheel，见 `pyproject.toml` 的 `[tool.uv.sources]`）
- **可选**：PyInstaller（打包为 Windows 便携版）

## 测试策略

| 层级 | 测试类型 | 覆盖目标 |
|---|---|---|
| model/ | 单元测试 | Artifact CRUD、Project 查询、Discovery 扫描 |
| engine/ | 集成测试 | FacadeBridge → e2m2e（真实参数模型签名）、持久化落盘、异常翻译 |
| view/ | 控件测试 | 参数面板生成/收集、画布渲染、项目树交互、图表设置 |
| app/ | 集成测试 | 内核引导、主窗口工具调度、i18n 加载 |
| commons/ | 单元测试 | 单位换算、内核下载/可用性判断、路径探测 |

e2m2e 本身已通过其自身测试套件验证，tod 不重复测试 e2m2e 的计算正确性。tod 的测试关注 GUI 行为和数据流。
