# Issue #339 实施方案：可视化增强（地月系统 + 多轨道 + 2D 投影）

> 审查用。确认无误后开始实施。

## 0. Issue 描述修订（提交前先同步到 GitHub issue）

原 issue 有三处需修订，理由见下方 1.3 修订依据：

1. **交付清单划掉多轨道自动配色（tab10）**：已在 #335（PR #343）完成。
2. **验收标准 #5（增量重绘）重定义为全量重绘 + 数据复用**：投影切换是结构性变化，增量重绘在当前架构下不可达。
3. **补上 mu 数据流决策**：`CR3BP_System` 构造需要 `mu`，现有 DTO/持久化均不含。
4. **交付清单补上 `src/engine/viz_adapter.py`**：`src/view/` 不能直接 import e2m2e（硬规则）。

## 1. 架构约束与设计决策

### 1.1 分层约束（来自 architecture.md 硬规则）

- `src/model/` 不 import `src/view/`、`src/engine/`（第1层）
- `src/view/` **不直接 import e2m2e**（第2层硬规则）：`OrbitVisualizer` / `CR3BP_System` 都在 e2m2e 包内，必须经 `src/engine/` 适配
- `src/engine/` 不 import `src/view/`（Workers 信号是技术性例外）
- 表现层只和数据层、执行层的接口交互

### 1.2 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| **mu 数据流** | 在 `Artifact.extra` + 持久化 JSON 携带 `mu`；`engine` 侧从 e2m2e 结果提取 | 单一事实来源；GUI 侧硬编码违背 tod 不实现轨道力学定位 |
| **投影切换实现** | CanvasState 变化 → `render()` 单入口**全量重绘**（清 ax + 重画） | 3D/2D 需不同 Axes 对象，无法增量切换 |
| **OrbitVisualizer 集成方式** | `src/engine/viz_adapter.py` 薄封装，向 view 暴露纯数组接口 | 遵守硬规则，view 不碰 e2m2e |
| **数据复用** | 切换投影/开关时复用内存 `state_data`，不从 NPZ 重读 | 性能 + 验收标准 #5 的可测形式 |
| **投影枚举** | `"3d" / "xy" / "xz" / "yz"` 字符串常量 | 与 architecture.md:248 一致 |
| **默认投影** | `"3d"` | 现状行为 |

### 1.3 修订依据（针对原 issue）

| 原 issue 内容 | 问题 | 修订 |
|---|---|---|
| 多轨道叠加渲染自动配色（tab10 调色板） | 已在 #335 完成（`canvas.py` `_TAB10_COLORS` + `plot_multiple`） | 划掉，改为将 tab10 配色策略接入 CanvasState 渲染 |
| CanvasState 变化时只重绘受影响的部分（不全量清除重建） | 投影切换需要重建 Axes，增量不可达 | 改为 CanvasState 变化时通过 render() 单入口全量重绘，轨道数据复用内存 |
| 集成 e2m2e OrbitVisualizer（传入 CR3BP_System） | 数据流无 mu 来源；view 不能直接 import e2m2e | 补 `src/engine/viz_adapter.py` + mu 数据流决策 |

## 2. 文件变更清单

| 文件 | 动作 | 行数估算 |
|---|---|---|
| `src/engine/viz_adapter.py` | **新增** | ~80 行 |
| `src/engine/facade_bridge.py` | **修改** | +3 行（DTO 加 `mu` 字段） |
| `src/model/artifact.py` | **修改** | +1 行（`extra` 已存在，无需改） |
| `src/engine/persistence.py` | **修改** | +1 行（JSON 元数据加 mu） |
| `src/view/canvas.py` | **修改** | +120 行（CanvasState + render + 标注） |
| `src/view/canvas_toolbar.py` | **新增** | ~100 行 |
| `src/app/main_window.py` | **修改** | +40 行（接入 CanvasState 流） |
| `tests/view/test_canvas_state.py` | **新增** | ~120 行 |
| `tests/engine/test_viz_adapter.py` | **新增** | ~80 行 |
| `tests/view/test_canvas_overlay.py` | **修改** | +20 行（补充 render 相关断言） |

## 3. 详细设计

### 3.1 `src/engine/viz_adapter.py`（新增）

```python
"""e2m2e 可视化适配层 -- view 与 OrbitVisualizer 之间的薄封装。

职责：
- 构造 CR3BP_System（从 mu 提取，地月质量比）
- 调用 e2m2e OrbitVisualizer 绘制地月标注 / L1-L5 / 2D 投影
- 向 view 暴露纯数组接口（不泄漏 e2m2e 类型）

架构：src/view/ 不直接 import e2m2e（硬规则），此模块是唯一桥接点。
"""

from __future__ import annotations

from typing import Any


def build_cr3bp_system(mu: float) -> Any:
    """构造 e2m2e CR3BP_System（地月系统，主天体 Earth，次天体 Moon）。"""
    from e2m2e.core import CR3BP_System
    return CR3BP_System(mu=mu, primary="Earth", secondary="Moon")


def draw_primary_bodies(ax, mu: float, *, is_3d: bool = True) -> None:
    """在 ax 上绘制地球/月球位置标注。

    Args:
        ax: 目标 matplotlib Axes。
        mu: CR3BP 质量比。地球在 (-mu,0,0)，月球在 (1-mu,0,0)。
    """
    from e2m2e.tools.viz import OrbitVisualizer
    system = build_cr3bp_system(mu)
    viz = OrbitVisualizer(system)
    viz.plot_primary_bodies(ax=ax, is_3d=is_3d)


def draw_libration_points(ax, mu: float, *, is_3d: bool = True) -> None:
    """在 ax 上绘制 L1-L5 拉格朗日点标注。"""
    from e2m2e.tools.viz import OrbitVisualizer
    system = build_cr3bp_system(mu)
    viz = OrbitVisualizer(system)
    viz.plot_libration_points(ax=ax, show_labels=True, is_3d=is_3d)
```

**设计要点**：

1. **函数式薄封装**，无状态。每次调用构造 `CR3BP_System`，开销可忽略（μ 固定，L 点数值求解约毫秒级）。
2. **`build_cr3bp_system` 独立导出**：主窗口若需持有 system 复用于多轨道场景，可在此构造一次。
3. **`draw_primary_bodies` / `draw_libration_points` 返回 None**：view 不依赖任何 e2m2e 类型。
4. 若 e2m2e `plot_primary_bodies` 在 `mu is None` 时静默返回（base.py:395-396），本适配层**不传 None**，直接传 mu。

### 3.2 `src/engine/facade_bridge.py`（修改）

`OrbitDesignResultData` 增加 `mu: float` 字段，`design_orbit()` 中从 e2m2e 结果提取：

```python
# facade_bridge.py
class OrbitDesignResultData:
    ...
    cr3bp_jacobi: float
    mu: float        # 新增：CR3BP 质量比
    states: Any      # np.ndarray (n, 6)
    times: Any       # np.ndarray (n,)

# design_orbit() 内
cr3bp_orbit = result.cr3bp_orbit
mu = getattr(getattr(cr3bp_orbit, "system", None), "mu", None)
return OrbitDesignResultData(
    orbit_type=result.orbit_type,
    epoch_utc=result.epoch_utc,
    duration_day=result.duration_day,
    initial_state=result.initial_state,
    cr3bp_jacobi=result.cr3bp_jacobi,
    mu=mu,  # 已验证：cr3bp_orbit.system.mu（design_orbit.py:460 绑定 system）
    states=np.asarray(cr3bp_orbit.states),
    times=np.asarray(cr3bp_orbit.times),
    ...
)
```

**已验证（2026-08-04 实测）**：
- `OrbitDesignResult` **没有 `mu` 字段**（`design_orbit.py:138-165`，只有 `cr3bp_orbit: Orbit`、`cr3bp_jacobi`）。
- 但 `cr3bp_orbit.system.mu` 可用：`design_orbit.py:460` 构造 `Orbit(..., system=dynamics.system)` 绑定了 `CR3BP_System`，其 `.mu` 是普通属性（`cr3bp_system.py:89`）。
- 实测：`Orbit(states, times, system=dyn.system)` 后 `orbit.system.mu` 返回 `0.012153645822478` ✓。
- **防御**：用 `getattr(getattr(cr3bp_orbit, "system", None), "mu", None)` 三重防护（`system` 可能为 None，鸭子类型绑定）。

### 3.3 `src/model/artifact.py` / `src/engine/persistence.py`（修改）

`_on_design_finished` 构造 Artifact 时，把 `mu` 写入 `extra`：

```python
# main_window.py 现有 extra dict 新增一行
extra={
    "cr3bp_jacobi": result.cr3bp_jacobi,
    "mu": result.mu,          # 新增
    "epoch_utc": result.epoch_utc,
    "arrays_file": npz_name,
    ...
},
```

`persistence.save_artifact` 的 JSON 元数据同步写入 `mu`，保证启动恢复的 Artifact 也能拿到 mu：

```python
# persistence.py save_artifact 的 json_data
json_data = {
    "artifact_type": "orbit",
    ...
    "mu": result_data.mu,  # 新增
    ...
}
```

**向后兼容**：旧 NPZ/JSON 无 `mu` 时，`extra.get("mu")` 返回 None。此时画布 fallback：不绘制地月/L 点标注（而非崩溃）。这在 `_on_artifact_clicked` 的懒加载分支已覆盖：`load_artifact_arrays` 只填 `state_data`/`times`，`extra` 从 JSON 读。若 `extra` 无 `mu`，则投影/开关可用但标注不显示，且日志提示旧 Artifact 无 mu，跳过地月标注。

### 3.4 `src/view/canvas.py`（修改）：核心

引入 `CanvasState`（与 architecture.md:247-252 一致）与 `render()` 单入口：

```python
class CanvasState:
    """画布渲染状态（architecture.md:247-252）。"""

    projection: str = "3d"              # "3d" | "xy" | "xz" | "yz"
    visible_artifacts: list[str] = field(default_factory=list)  # artifact_id 列表
    show_bodies: bool = True
    show_libration: bool = True

    def copy(self) -> CanvasState:
        return CanvasState(
            projection=self.projection,
            visible_artifacts=list(self.visible_artifacts),
            show_bodies=self.show_bodies,
            show_libration=self.show_libration,
        )


class OrbitCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        ...
        self._state = CanvasState()
        # state 数据注册表：canvas 不自持 Project，由 main_window 通过
        # set_artifacts_provider() 注入一个回调（见 3.6）

    # -- 渲染入口 --------------------------------------------------------

    def render(self, state: CanvasState | None = None) -> None:
        """根据 CanvasState 全量重绘画布。

        调用方（main_window）在 CanvasState 变化时调此方法。
        数据复用：轨道数组来自内存注册表，不从磁盘/NPZ 重读。
        """
        state = state or self._state
        self._fig.clear()
        ax = self._fig.add_subplot(
            111, projection="3d" if state.projection == "3d" else None
        )

        # 1. 轨道
        if state.projection == "3d":
            self._draw_3d_orbits(ax, state)
        else:
            self._draw_2d_orbits(ax, state)

        # 2. 地月标注（依赖 mu）
        if state.show_bodies:
            self._draw_bodies(ax, state)

        # 3. L1-L5 标注
        if state.show_libration:
            self._draw_libration(ax, state)

        self._fig.tight_layout()
        self.draw()

    # -- 内部 ------------------------------------------------------------

    def _draw_3d_orbits(self, ax, state) -> None:
        for i, aid in enumerate(state.visible_artifacts):
            states = self._states_by_id.get(aid)
            if states is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            pos = states[:, :3]
            ax.plot(pos[:, 0], pos[:, 1], pos[:, 2],
                    linewidth=0.8, color=color,
                    label=self._labels_by_id.get(aid, ""))
            ax.scatter(*pos[0], s=30, c=color, zorder=5)

    def _draw_2d_orbits(self, ax, state) -> None:
        plane = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}[state.projection]
        for i, aid in enumerate(state.visible_artifacts):
            states = self._states_by_id.get(aid)
            if states is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            pos = states[:, :3]
            ax.plot(pos[:, plane[0]], pos[:, plane[1]],
                    linewidth=0.8, color=color,
                    label=self._labels_by_id.get(aid, ""))

    def _draw_bodies(self, ax, state) -> None:
        # 经 viz_adapter 调用 e2m2e，view 不直接 import e2m2e
        from src.engine.viz_adapter import draw_primary_bodies
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_primary_bodies(ax, mu, is_3d=(state.projection == "3d"))
                break  # 只画一次（同一 CR3BP 系统）

    def _draw_libration(self, ax, state) -> None:
        from src.engine.viz_adapter import draw_libration_points
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_libration_points(ax, mu, is_3d=(state.projection == "3d"))
                break
```

**设计要点**：

1. **`render()` 是全量重绘单入口**，从 `_fig.clear()` 开始，不保留旧 Axes 增量。3D/2D 用不同 `projection` 参数创建 Axes。
2. **数据注册表**（`_states_by_id` / `_labels_by_id` / `_mu_by_id`）：main_window 在渲染前把当前可见 Artifact 的数组灌进去。**切换投影/开关时数组已在内存，不从 NPZ 重读**，这正是验收标准 #5 的可测形式。
3. **`_draw_bodies` / `_draw_libration` 只画一次**：同一 CR3BP 系统（地月 mu 相同），多轨道时避免重复画。
4. **`CanvasState.copy()`**：main_window 用读取当前 state、修改字段并传入新 state 的不可变模式，避免 canvas 内部状态被外部直接改。也可简化为 `self._canvas.state = new_state; self._canvas.render()`。
5. **向后兼容**：`plot_orbit()` / `plot_multiple()` 保留（#335 已实现、有测试），内部改为委托 `render()` 或保持不变。**建议保留**：`_on_artifact_clicked` / `_on_artifacts_multi_selected` 可逐步迁移到 `render()`。

**明确决策**：`plot_orbit()` / `plot_multiple()` 是否保留。
- 方案 A（推荐）：保留，作为 `render()` 的便捷薄封装。改动最小，旧测试不破。
- 方案 B：删除，全部迁到 `render()`。更干净，但 `test_canvas_overlay.py` 6 个测试全要改。

### 3.5 `src/view/canvas_toolbar.py`（新增）

```python
"""画布工具栏 -- 投影切换 + 地月/L 点开关（architecture.md:49 规划）。"""

from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QPushButton


class CanvasToolbar(QWidget):
    """投影切换按钮组 + show_bodies/show_libration 复选框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projection_3d = QPushButton("3D")
        self.projection_xy = QPushButton("XY")
        self.projection_xz = QPushButton("XZ")
        self.projection_yz = QPushButton("YZ")
        self.show_bodies = QCheckBox("地月")
        self.show_libration = QCheckBox("L1-L5")

        self.show_bodies.setChecked(True)
        self.show_libration.setChecked(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.projection_3d)
        layout.addWidget(self.projection_xy)
        layout.addWidget(self.projection_xz)
        layout.addWidget(self.projection_yz)
        layout.addSpacing(16)
        layout.addWidget(self.show_bodies)
        layout.addWidget(self.show_libration)
        layout.addStretch()
```

**设计要点**：无业务逻辑，纯 UI。信号连接到 main_window 的 slot（见 3.6），由 main_window 统一更新 CanvasState 并调 `render()`。**工具栏按钮不做状态互斥高亮**（如 QButtonGroup 检查当前投影），MVP 不引入，简化 scope。

### 3.6 `src/app/main_window.py`（修改）

**画布持有回调而非 Project**（view 层不 import Project 业务逻辑以外的耦合）：

```python
def _build_center_panel(self) -> None:
    tabs = QTabWidget()
    self._viz = OrbitCanvasWithToolbar()
    # 注入数据回调：main_window 提供 state_data / label / mu 查询
    self._viz.canvas.set_artifacts_provider(self._artifact_for_id)
    tabs.addTab(self._viz.widget, "可视化")
    ...
```

```python
def _artifact_for_id(self, artifact_id: str) -> dict | None:
    """返回画布渲染所需的 Artifact 数组数据（不含 e2m2e 类型）。"""
    a = self._project.get_by_id(artifact_id)
    if a is None or a.state_data is None:
        return None
    return {
        "states": a.state_data,
        "label": a.label,
        "mu": a.extra.get("mu"),
    }
```

**CanvasState 更新 + render 调用**：

```python
def _on_projection_changed(self, projection: str) -> None:
    self._canvas_state.projection = projection
    self._render_canvas()

def _on_toggle_bodies(self, checked: bool) -> None:
    self._canvas_state.show_bodies = checked
    self._render_canvas()

def _on_toggle_libration(self, checked: bool) -> None:
    self._canvas_state.show_libration = checked
    self._render_canvas()

def _render_canvas(self) -> None:
    """同步 CanvasState 并触发 render()。数据在内存，不从 NPZ 重读。"""
    self._viz.canvas.sync_state(self._canvas_state, self._selected_artifact_ids())
    self._viz.canvas.render()
```

**选中集合维护**：单选/多选回调统一维护 `self._selected_artifact_ids`（list[str]），替代现在各自调 `plot_orbit`/`plot_multiple` 的分散逻辑：

```python
def _on_artifact_clicked(self, artifact_id: str) -> None:
    artifact = self._project.get_by_id(artifact_id)
    if artifact is None:
        return
    if artifact.state_data is None and artifact.output_path is not None:
        loaded = load_artifact_arrays(artifact)  # 懒加载 NPZ
        if not loaded:
            self._log.append_log(...)
    if artifact.state_data is not None:
        self._selected_artifact_ids = [artifact_id]
        self._render_canvas()
        self._center_tabs.setCurrentIndex(0)

def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
    # 多选分支补上懒加载（现状缺失，见审查意见）
    for aid in artifact_ids:
        artifact = self._project.get_by_id(aid)
        if artifact and artifact.state_data is None and artifact.output_path is not None:
            load_artifact_arrays(artifact)
    self._selected_artifact_ids = artifact_ids
    self._render_canvas()
    self._center_tabs.setCurrentIndex(0)
```

**toolbar 连接**（在 `_build_center_panel` 中）：

```python
self._viz.toolbar.projection_3d.clicked.connect(
    lambda: self._on_projection_changed("3d"))
self._viz.toolbar.projection_xy.clicked.connect(
    lambda: self._on_projection_changed("xy"))
...
self._viz.toolbar.show_bodies.toggled.connect(self._on_toggle_bodies)
self._viz.toolbar.show_libration.toggled.connect(self._on_toggle_libration)
```

**设计要点**：

1. **单一状态源**：`self._canvas_state`（CanvasState 实例）是 main_window 的成员，画布通过 `sync_state()` 接收。
2. **`_selected_artifact_ids` 统一维护**：重构了此前点击调用 plot_orbit 与多选调用 plot_multiple 的分散逻辑，投影/开关变化时无需重新选择，直接重绘当前选中。
3. **多选分支补懒加载**：修复现有 `_on_artifacts_multi_selected` 不懒加载的缺口（审查发现）。

### 3.7 测试计划

#### `tests/engine/test_viz_adapter.py`（新增）

```
class TestVizAdapter:
    test_build_cr3bp_system_with_mu
        → build_cr3bp_system(0.012153645822478) 返回 CR3BP_System
        → system.mu == 0.012153645822478

    test_draw_primary_bodies_adds_artists
        → 创建 fig + ax(3d)，draw_primary_bodies(ax, mu)
        → ax 上的 artist 数量增加（scatter/text）

    test_draw_libration_points_adds_artists
        → draw_libration_points(ax, mu) → ax 上有 L1-L5 相关 artist

    test_no_import_e2m2e_at_module_import
        → import src.engine.viz_adapter 不触发 import e2m2e
        （e2m2e 延迟 import，保证 src/view 层不泄漏）
```

#### `tests/view/test_canvas_state.py`（新增）

```
class TestCanvasState:
    test_default_projection_is_3d
    test_copy_returns_new_instance
    test_copy_shares_visible_artifacts_list_immutably

class TestOrbitCanvasRender:
    test_render_single_artifact_3d
        → sync_state + render → ax 有 Line3D

    test_render_multiple_artifacts_tab10_colors
        → 两条轨道颜色不同

    test_switch_projection_xy_creates_2d_axes
        → sync_state(projection="xy") + render → ax 不是 3d projection
        → 有 Line2D

    test_toggle_bodies_off_hides_body_artists
        → show_bodies=False → 无地月 artist

    test_toggle_libration_off_hides_libration
        → show_libration=False → 无 L 点 artist

    test_render_reuses_in_memory_arrays
        → 记录 NPZ 读取次数（mock load_artifact_arrays）
        → 切换投影不触发新读

    test_old_artifact_without_mu_no_crash
        → extra 无 mu → render 不崩，无地月标注
```

#### `tests/view/test_canvas_overlay.py`（修改）

- 现有 6 个测试（`plot_multiple`）保留（方案 A：plot_multiple 保留为 render 的薄封装）。
- 若采用方案 B（删除 plot_multiple），此文件测试改为针对 `render()`。

## 4. 实施顺序

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | **验证 e2m2e `OrbitDesignResult` 暴露 mu**（见 5.2）；决定 `OrbitVisualizer` 集成细节 | `python -c "from e2m2e.algorithm.design import ...; print(...)"` |
| 2 | 新建 `src/engine/viz_adapter.py` | `pytest tests/engine/test_viz_adapter.py -v` |
| 3 | 修改 `src/engine/facade_bridge.py`，DTO 加 mu；`persistence.py` JSON 加 mu | `pytest tests/engine/ -v` |
| 4 | 新建 `tests/engine/test_viz_adapter.py` | 步骤 2/3 的测试 |
| 5 | 修改 `src/view/canvas.py`，CanvasState + render + 标注 | `pytest tests/view/test_canvas_state.py -v` |
| 6 | 新建 `tests/view/test_canvas_state.py` | 步骤 5 的测试 |
| 7 | 新建 `src/view/canvas_toolbar.py` | 手动验证 import |
| 8 | 修改 `src/app/main_window.py`，接入 CanvasState + toolbar | `uv run python -m src.app.main` 手动验证 |
| 9 | 全量测试 | `pytest tests/ -v`（1195 passed 基线） |

## 5. 风险与待确认

### 5.1 需用户在审查时拍板的决策

| # | 决策点 | 选项 | 建议 |
|---|---|---|---|
| 1 | **`plot_orbit`/`plot_multiple` 是否保留** | A. 保留为 render 薄封装 / B. 删除全迁 render | **A**（改动小，旧测试不破） |
| 2 | **mu 数据流范围** | A. DTO + 持久化 JSON 都带 mu / B. 仅内存 extra | **A**（启动恢复的 Artifact 也要能画标注） |
| 3 | **旧 Artifact 无 mu 时行为** | A. 跳过标注 + 日志提示 / B. 用硬编码地月 μ 兜底 | **A**（不硬编码，遵循定位） |

### 5.2 技术风险（已部分验证）

- **~~e2m2e `OrbitDesignResult` 是否暴露 `mu`~~** ✅ **已解决**：`OrbitDesignResult` 无 `mu` 字段，但 `cr3bp_orbit.system.mu` 可用（`design_orbit.py:460` 绑定 `CR3BP_System`），实测返回 `0.012153645822478`。用 `getattr` 三重防护。
- **`OrbitVisualizer` 2D/3D 标注实际行为** ✅ **已验证**：`plot_primary_bodies` + `plot_libration_points` 在 3D ax 添加 23 个 artist、2D ax 添加 22 个 artist（Agg 后端实测，2026-08-04）。
- **`OrbitVisualizer.plot_primary_bodies` 在 2D 下的图标加载**：e2m2e 的 2D 图标走 `icons.add_2d_icon`，需要 PNG 资源。若加载失败会回退圆形 marker（base.py:124,139），可接受，但测试中注意别依赖图标存在。
- **matplotlib 3D→2D 切换**：每次 `render()` 重建 Axes。若高频切换（连点投影按钮）有性能顾虑，可加当前 projection 相同则复用 Axes 优化，MVP 不做。

### 5.3 范围外（明确不做）

- 右键菜单、扩展工具（#340，**依赖本 issue 完成**）
- 轨道族热力图（ADR 0010 能力 #5，后续 issue）
- 画布分屏 2x2（ADR 0010 后续）
- 投影按钮状态高亮互斥（MVP 不做，见 3.5）

## 6. 验收标准映射

| 验收标准（修订后） | 实现位置 |
|---|---|
| 单轨道渲染时显示地球、月球位置和 L1-L5 标注 | `canvas._draw_bodies` / `_draw_libration` → `viz_adapter` |
| 多轨道叠加时颜色自动区分（tab10） | 已在 #335 完成；`canvas._draw_3d_orbits` 沿用 tab10 |
| 切换 XY/XZ/YZ 投影 → 画布重绘为 2D 视图 | `render()` 按 `state.projection` 创建 2D/3D Axes |
| show_bodies/show_libration 复选框控制标注显示/隐藏 | `toolbar` → main_window slot → `_canvas_state` → `render()` |
| CanvasState 变化 → 全量重绘，数据复用内存（不从 NPZ 重读） | `sync_state()` + `render()`；`_artifact_for_id` 回调返回内存数组 |