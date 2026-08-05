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
│   │   ├── workers.py     # QThread 工作线程（设计/族生成/保持/稳定性）
│   │   └── persistence.py # 结果落盘（写 output/ + 元数据 JSON）
│   ├── view/              # 第3层 表现层
│   │   ├── project_tree.py  # 项目树（Artifact 分组展示 + 右键操作）
│   │   ├── canvas.py      # 内嵌 matplotlib 画布（FigureCanvasQTAgg）
│   │   ├── canvas_toolbar.py # 可视化工具栏（3D/2D 切换、投影选择）
│   │   ├── params_panel.py # 参数面板（从 Pydantic 模型自动生成）
│   │   ├── log_panel.py   # 日志面板（结构化输出）
│   │   └── widgets/       # 通用 Qt 控件
│   │       ├── artifact_card.py      # Artifact 详情卡片
│   │       └── progress_indicator.py # 任务进度指示
│   ├── app/               # 第4层 入口
│   │   ├── main.py        # QApplication 启动 + 窗口组装
│   │   ├── main_window.py # 主窗口（三栏 Splitter 布局）
│   │   ├── settings.py    # 设置（SPICE 内核路径、主题、语言、字体）
│   │   └── i18n/          # 国际化资源
│   ├── commons/           # 跨层常量（保留）
│   │   ├── constants.py   # DU/TU/物理常量
│   │   └── orbits.py      # GEO/LEO 轨道几何
│   └── __init__.py
├── plot/                  # 绘图工具（保留，供高级用户独立使用）
├── docs/                  # 文档
│   ├── adr/               # 架构决策记录
│   └── architecture/      # 架构说明
├── tests/                 # 测试
├── output/                # 运行时输出（数据持久化源）
└── pyproject.toml
```

**删除的旧代码**（大爆炸替换）：

| 旧目录 | 原因 |
|---|---|
| `tod/gui/` | 被 `src/view/` + `src/app/` 替代 |
| `tod/generates/` | 被 e2m2e Facade API 直调替代 |
| `tod/transfers/` | 被 e2m2e Facade API 直调替代（未实现的灰掉） |
| `tod/scripting/` | SCRIPT_ENTRY 机制废弃 |
| `tod/commons/e2m2e_compat.py` | 不再需要旧路径兼容 |

**保留的代码**（迁入 `src/`）：

| 保留目录 | 迁入 | 原因 |
|---|---|---|
| `tod/plot/` | `plot/`（顶层） | 独立绘图脚本，高级用户可直接命令行使用 |
| `tod/commons/` | `src/commons/` | 物理常量、轨道几何计算，不依赖 e2m2e 内部结构 |

`src/` 是 Python src layout 约定：`pyproject.toml` 中 `[tool.setuptools.packages.find]` 通过 `include = ["src*", "plot*"]` 发现包，import 时为 `from src.model import ...`、`from plot.transfer.common import ...`。

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
| `output/dro/` | `dro_<timestamp>.json` | orbit |
| `output/halo/` | `halo_<type>_<params>_<ts>.json` | orbit |
| `output/halo/` | `halo_*_family_*.json` | family |
| `output/transfer/` | `search_*_<ts>.json` | transfer |
| `output/transfer/` | `optimization_*_<ts>.json` | transfer |
| `output/ephemeris/` | `orbit_ephemeris_*.json` | ephemeris |

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

- **直接调用 algorithm 层，不经过 Facade 门面**。原因：`Facade.design_orbit()` 返回的 `DesignOrbitResponse` 剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 `OrbitDesignResult`（含 `cr3bp_orbit`、`ephemeris`）用于可视化。Facade 门面是 MCP/CLI 的接口层，GUI 作为 e2m2e 的深度集成者直接使用算法层。
- **结果 DTO（Data Transfer Object）**：可跨线程边界传递的纯数据类，不持有 e2m2e 对象引用。包含 numpy 数组（状态矩阵、时间向量）和标量元数据。
- **异常翻译**：e2m2e 异常 → 结构化错误码 + 用户友好消息。

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
📁 项目: DRO-GEO 转移设计
├─ 🪐 轨道
│  ├─ DRO (C_J=3.0058)        ← 点击 → 渲染到画布
│  └─ DRO (C_J=3.0062, t=2yr)
├─ 🌀 轨道族
│  └─ DRO Family (50 orbits)
├─ 🚀 转移
│  └─ DRO→GEO Search (Δv=1.2km/s)
└─ 📡 星历
   └─ DRO Ephemeris (2024-2025)
```

右键菜单上下文感知：

| 选中 Artifact 类型 | 右键可用操作 |
|---|---|
| orbit (DRO) | 设计新轨道、生成轨道族、查看稳定性、删除 |
| orbit (任意) | 查看稳定性、叠加显示、删除 |
| family | 展开/折叠成员、删除 |
| transfer | 优化（待 e2m2e 实现）、删除 |

**多选**：Ctrl+点击选中多个 Artifact，画布叠加渲染。

### 可视化画布 `canvas.py`

主窗口中央。内嵌 `FigureCanvasQTAgg` + `NavigationToolbar2QT`。

**标准可视化能力**：

| 能力 | 说明 |
|---|---|
| 3D 轨道图 | CR3BP 旋转坐标系下的轨道 |
| 2D 投影切换 | XY / XZ / YZ 三视图，工具栏按钮切换 |
| 多轨道叠加 | 选中多个 Artifact 时叠加渲染，自动分配颜色 |
| 地月系统标注 | 地球、月球位置 + 五个拉格朗日点，`OrbitVisualizer` 提供 |
| 轨道族热力图 | Jacobi 常数着色，`FamilyPlotter` 提供 |
| 导航工具栏 | 缩放/平移/旋转/保存图片 |

**画布状态**：

```python
class CanvasState:
    projection: str         # "3d" | "xy" | "xz" | "yz"
    visible_artifacts: list[str]  # 当前显示的 artifact_id 列表
    show_bodies: bool       # 是否显示地月
    show_libration: bool    # 是否显示拉格朗日点
```

### 参数面板 `params_panel.py`

主窗口右侧。**从 e2m2e Pydantic 模型自动生成**。

生成规则：

| Pydantic 字段类型 | Qt 控件 |
|---|---|
| `float` (有 ge/le) | `QDoubleSpinBox` (range=ge..le) |
| `int` (有 ge/le) | `QSpinBox` (range=ge..le) |
| `str` (有 enum) | `QComboBox` |
| `str` (无 enum) | `QLineEdit` |
| `list[float]` | 多个 `QDoubleSpinBox` |
| `Any` (可选) | `QLineEdit` (JSON 输入) |

字段元数据映射：

| Pydantic Field 信息 | Qt 属性 |
|---|---|
| `description` | 控件 tooltip |
| `default` | 控件默认值 |
| `ge/le/gt/lt` | 控件范围 |
| `Field(json_schema_extra={"unit": "km"})` | 单位标签 |

每个工具类型注册一个参数面板生成函数：

```python
# src/engine/facade_bridge.py 中的注册表
TOOL_REGISTRY: dict[str, ToolSpec] = {
    "design_orbit": ToolSpec(
        request_model=DesignOrbitRequest,
        facade_method="design_orbit",
        label="轨道设计",
    ),
    "generate_family": ToolSpec(...),
    "analyze_stability": ToolSpec(...),
    "control_orbit": ToolSpec(...),
}
```

未实现的工具（transfer_search 等）在注册表中标记 `enabled=False`，参数面板显示"即将推出"占位。

### 日志面板 `log_panel.py`

主窗口中央标签页（与可视化画布并列）。显示当前任务的结构化日志：

```
[14:32:01] 开始设计 DRO 轨道...
[14:32:01] 参数: amplitude=40000.0 km, duration=1.0 yr
[14:32:15] 微分修正收敛 (3 次迭代, 残差 2.3e-12)
[14:32:18] 星历修正完成 (two_level, 5 段)
[14:32:20] ✓ 设计完成: DRO, C_J=3.005811
```

## 第4层 入口 `src/app/`

### 主窗口布局 `main_window.py`

```
┌─ 左侧 (20%) ────┬─ 中间 (55%) ─────────────┬─ 右侧 (25%) ─────┐
│                  │                           │                   │
│  项目树          │  [📊 可视化 | 📋 日志]     │  参数面板          │
│  (QTreeWidget)   │                           │  (自动生成)        │
│                  │  ┌───────────────────┐    │                   │
│  🪐 轨道         │  │                   │    │  轨道类型  [DRO ▾] │
│   ├ DRO ...      │  │   3D 轨道图       │    │  振幅    [40000]   │
│   └ Halo ...     │  │   (可交互)        │    │  持续    [1.0]     │
│                  │  │                   │    │  步长    [3600]    │
│  🌀 轨道族       │  └───────────────────┘    │                   │
│  🚀 转移         │  [缩放|旋转|2D|投影|保存]   │  SPICE [...]      │
│  📡 星历         │                           │                   │
│                  │                           │  [▶ 运行]          │
└──────────────────┴───────────────────────────┴───────────────────┘
│ 状态栏: 就绪 | 0 个任务运行中 | SPICE: D:/codes/e2m2e/kernels     │
└──────────────────────────────────────────────────────────────────┘
```

**Splitter 布局**：三栏可拖拽调整比例。默认 20:55:25。

### 设置 `settings.py`

| 设置项 | 存储位置 | 默认值 |
|---|---|---|
| SPICE 内核目录 | `gui_defaults.json` | `$SPICE_KERNEL_DIR` 或 `../e2m2e/kernels/` |
| 主题 (light/dark/system) | `gui_defaults.json` | system |
| 语言 (zh/en) | `gui_defaults.json` | zh |
| 可视化字体大小 | `gui_defaults.json` | 12 |
| 地月图标缩放 | `gui_defaults.json` | 1.0 |

### 入口 `main.py`

```python
def main():
    app = QApplication(sys.argv)
    # 1. 初始化 FacadeBridge (Config from settings)
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
src/commons/ → 无依赖（常量）
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
    → 根据 projection 创建 Axes (3d / 2d)
    → 遍历 visible_artifacts，绑定 state_data 到 axes.plot()
    → 如果 show_bodies: 绘制地月位置
    → 如果 show_libration: 绘制 L1-L5
    → fig.tight_layout() + canvas.draw()
```

### 颜色策略

- 单轨道：蓝色 (#1f77b4)
- 多轨道叠加：tab10 调色板自动分配
- 轨道族：按 Jacobi 常数 colormap (viridis) 着色
- 起点：绿色圆点
- 终点：红色圆点
- 地球：蓝色大圆 + 图标
- 月球：灰色大圆 + 图标
- L 点：黑色三角 + 标签

## 管线串联

用户操作一个 Artifact 后，项目树的右键菜单展示可用的下一步操作。

**因果链**：

```
Artifact A (DRO orbit)
  → 右键 → "生成轨道族" → 调 generate_family(dro_orbit=A.state_data)
    → 注册 Artifact B (family)
  → 右键 → "分析稳定性" → 调 analyze_stability(orbit=A.state_data)
    → 显示结果弹窗
```

**数据流**：Artifact 的 `state_data` 在内存中传递（numpy 数组引用），不经过文件 I/O。落盘是并行行为（Persistence 模块异步写 output/）。

## 未实现能力（灰色占位）

以下 e2m2e Facade 方法尚未实现，在 GUI 中显示为禁用状态：

| 工具 | Facade 方法 | 显示状态 |
|---|---|---|
| 转移搜索 | `transfer_search` | 🔒 即将推出 |
| 转移设计 | `transfer_design` | 🔒 即将推出 |
| 轨道预报 | `orbit_propagation` | 🔒 即将推出 |
| 低推力设计 | `low_thrust_design` | 🔒 即将推出 |
| 流形分析 | `manifold_analysis` | 🔒 即将推出 |
| 低能转移 | `low_energy_transfer` | 🔒 即将推出 |
| 相对运动 | `relative_motion` | 🔒 即将推出 |
| 坐标转换 | `spacetime_transform` | 🔒 即将推出 |

当 e2m2e 实现对应 Facade 方法后，只需在 `TOOL_REGISTRY` 中将 `enabled=True`，GUI 自动启用（参数面板从 Pydantic 模型自动生成）。

## 依赖

- **运行时**：PyQt6, PyQt6-WebEngine（文档渲染）, matplotlib, numpy
- **e2m2e**：本地路径依赖（editable install），通过 `src/engine/facade_bridge.py` 调用 algorithm 层
- **可选**：PyInstaller（打包为 Windows 便携版）

## 测试策略

| 层级 | 测试类型 | 覆盖目标 |
|---|---|---|
| model/ | 单元测试 | Artifact CRUD、Project 查询、Discovery 扫描 |
| engine/ | 集成测试 | FacadeBridge → e2m2e 端到端（需 SPICE 内核） |
| view/ | 控件测试 | 参数面板生成、画布渲染、项目树交互 |
| app/ | E2E 测试 | 启动 → 选工具 → 运行 → 验证 Artifact 注册 + 画布更新 |

e2m2e 本身已通过其自身测试套件验证，tod 不重复测试 e2m2e 的计算正确性。tod 的测试关注 GUI 行为和数据流。
