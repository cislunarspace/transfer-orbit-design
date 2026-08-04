# Issue #335 实施方案：项目树 + Artifact 注册

> 审查用。确认无误后开始实施。

## 1. 架构约束与设计决策

### 1.1 分层约束（来自 architecture.md 硬规则）

- `src/model/` 不 import `src/view/` — Project **不加 QObject 信号**
- `src/view/` 不直接 import e2m2e
- 自动刷新在 main_window 的 slot 中通过 `tree_view.refresh(project)` 实现

### 1.2 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| Project 信号机制 | 不引入，保持纯 Python | 架构第1层硬规则 |
| 多选模式 | `QTreeWidget.setSelectionMode(ExtendedSelection)` | Qt 原生 Ctrl+多选 |
| 颜色策略 | `matplotlib.cm.tab10` 循环分配 | architecture.md:405 |
| CanvasState | 不引入，直接传 artifact list | 简化 scope，后续 issue 引入 |
| 右键菜单 | 不在范围内 | 后续独立 issue |

## 2. 文件变更清单

| 文件 | 动作 | 行数估算 |
|---|---|---|
| `src/view/project_tree.py` | **新增** | ~120 行 |
| `src/view/canvas.py` | **修改** | +40 行 |
| `src/app/main_window.py` | **修改** | -15 行 / +10 行 |
| `tests/view/__init__.py` | **新增** | 0 行 |
| `tests/view/test_project_tree.py` | **新增** | ~100 行 |
| `tests/view/test_canvas_overlay.py` | **新增** | ~60 行 |

## 3. 详细设计

### 3.1 `src/view/project_tree.py`（新增）

```python
"""项目树 -- 按 Artifact 类型分组展示，支持 Ctrl+多选。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

from src.model import Artifact, Project

# 分组标签（含 Emoji 前缀，与 architecture.md:203-216 对齐）
_TYPE_GROUP_LABELS: dict[str, str] = {
    "orbit":      "\U0001FA90 轨道",       # 🪐
    "family":     "\U0001F300 轨道族",     # 🌀
    "transfer":   "\U0001F680 转移",       # 🚀
    "ephemeris":  "\U0001F4E1 星历",       # 📡
}


class ProjectTreeView(QWidget):
    """项目树封装。

    Signals:
        artifact_selected(str):     单击单个 artifact_id
        artifacts_selected(list[str]): Ctrl+多选 artifact_id 列表
    """

    artifact_selected = pyqtSignal(str)
    artifacts_selected = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        # itemClicked → 单选信号
        self._tree.itemClicked.connect(self._on_item_clicked)

        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    # -- 公共 API -----------------------------------------------------------

    def refresh(self, project: Project) -> None:
        """从 Project 重建树结构。"""
        self._tree.clear()
        type_groups: dict[str, list[Artifact]] = {}
        for a in project.artifacts:
            type_groups.setdefault(a.artifact_type, []).append(a)

        for atype, items in type_groups.items():
            label = _TYPE_GROUP_LABELS.get(atype, atype)
            group = QTreeWidgetItem(self._tree, [label])
            group.setExpanded(True)
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for artifact in items:
                child = QTreeWidgetItem(group, [artifact.label])
                child.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)

    def selected_artifact_ids(self) -> list[str]:
        """返回当前选中的所有 artifact_id。"""
        ids: list[str] = []
        for item in self._tree.selectedItems():
            aid = item.data(0, Qt.ItemDataRole.UserRole)
            if aid:
                ids.append(aid)
        return ids

    # -- 内部 ---------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not artifact_id:
            return  # 点击的是分组节点

        selected = self.selected_artifact_ids()
        if len(selected) > 1:
            self.artifacts_selected.emit(selected)
        else:
            self.artifact_selected.emit(artifact_id)
```

**设计要点**：

1. **QWidget 封装**而非 QTreeWidget 子类 — 组合优于继承，内部控制布局
2. **分组节点不可选**（`~ItemIsSelectable`）— 避免点击分组标题时误发信号
3. **信号分流**：单选发 `artifact_selected(str)`，多选发 `artifacts_selected(list[str])`
4. **`refresh(project)`** — 无状态，每次全量重建。Artifact 数量级在百级以内，性能无问题

### 3.2 `src/view/canvas.py`（修改）

新增 `plot_multiple()` 方法，保持 `plot_orbit()` / `plot_family()` 不变：

```python
# 在 OrbitCanvas 类中新增：

# tab10 调色板（architecture.md:405）
_TAB10_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

def plot_multiple(
    self,
    orbits: list[tuple[ndarray, str]],  # [(states, label), ...]
) -> None:
    """叠加渲染多条轨道。

    每条轨道使用 tab10 调色板中不同颜色。
    """
    self._fig.clear()
    ax = self._fig.add_subplot(111, projection="3d")

    for i, (states, label) in enumerate(orbits):
        color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
        pos = states[:, :3]
        ax.plot(pos[:, 0], pos[:, 1], pos[:, 2],
                linewidth=0.8, color=color, label=label)
        ax.scatter(*pos[0], s=30, c=color, zorder=5)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"叠加显示 ({len(orbits)} 条轨道)")

    if orbits:
        ax.legend(loc="upper left", fontsize=8)
    self._fig.tight_layout()
    self.draw()
```

在 `OrbitCanvasWithToolbar` 中透传：

```python
def plot_multiple(self, **kwargs) -> None:
    self.canvas.plot_multiple(**kwargs)
```

### 3.3 `src/app/main_window.py`（修改）

**替换** `_build_left_panel` 中的内联 QTreeWidget 为 ProjectTreeView：

```python
def _build_left_panel(self) -> QWidget:
    from src.view.project_tree import ProjectTreeView
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)

    layout.addWidget(QLabel("项目"))
    self._tree_view = ProjectTreeView()
    self._tree_view.artifact_selected.connect(self._on_artifact_clicked)
    self._tree_view.artifacts_selected.connect(self._on_artifacts_multi_selected)
    layout.addWidget(self._tree_view)

    return panel
```

**替换** `_refresh_project_tree` 为委托调用：

```python
def _refresh_project_tree(self) -> None:
    self._tree_view.refresh(self._project)
```

**新增** 多选处理 slot：

```python
def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
    orbits: list[tuple] = []
    for aid in artifact_ids:
        artifact = self._project.get_by_id(aid)
        if artifact and artifact.state_data is not None:
            orbits.append((artifact.state_data, artifact.label))
    if orbits:
        self._viz.plot_multiple(orbits=orbits)
        self._center_tabs.setCurrentIndex(0)
```

**删除**：
- `_project_tree` 相关的 import（`QTreeWidget`, `QTreeWidgetItem`）
- 旧的 `_on_artifact_clicked` 中的 `QTreeWidgetItem` 类型标注，改为 `str`

### 3.4 测试计划

#### `tests/view/test_project_tree.py`

```
qapp fixture 复用 test_params_panel.py 的模式。

class TestProjectTreeViewRefresh:
    test_empty_project_shows_no_items
        → refresh(Project("empty")) → tree 无 item

    test_groups_by_artifact_type
        → add orbit + family + transfer → 3 个分组节点

    test_emoji_prefix_in_group_label
        → 分组文本包含 "🪐"/"🌀"/"🚀"/"📡"

    test_group_not_selectable
        → 分组节点的 ItemIsSelectable flag 已清除

    test_child_has_artifact_id_in_user_role
        → child item 的 UserRole data == artifact.artifact_id

class TestProjectTreeViewSignals:
    test_single_click_emits_artifact_selected
        → 点击单个 item → artifact_selected 信号携带 artifact_id

    test_ctrl_multi_select_emits_artifacts_selected
        → 选中 2 个 item → artifacts_selected 信号携带 id 列表
        （注：模拟 Ctrl+click 需要 QTest.mouseClick + keyboard modifier，
          或直接调用 item.setSelected()）
```

#### `tests/view/test_canvas_overlay.py`

```
class TestPlotMultiple:
    test_renders_all_orbits
        → plot_multiple([(states1, "A"), (states2, "B")])
        → canvas.figure 上有 2 条 Line3D

    test_uses_different_colors
        → 两条轨道颜色不同

    test_empty_list_no_error
        → plot_multiple([]) 不抛异常

    test_title_shows_count
        → title 包含 "2 条轨道"
```

## 4. 实施顺序

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | 新建 `src/view/project_tree.py` | 手动检查 import 无误 |
| 2 | 新建 `tests/view/test_project_tree.py` | `pytest tests/view/test_project_tree.py -v` |
| 3 | 修改 `src/view/canvas.py` — 新增 `plot_multiple()` | 手动验证 import |
| 4 | 新建 `tests/view/test_canvas_overlay.py` | `pytest tests/view/test_canvas_overlay.py -v` |
| 5 | 修改 `src/app/main_window.py` — 集成 | `uv run python -m src.app.main` 手动验证 |
| 6 | 全量测试 | `pytest tests/ -v` |

## 5. 验收标准映射

| 验收标准 | 实现位置 |
|---|---|
| 运行设计后，新 Artifact 自动出现在项目树中 | main_window._on_design_finished → _refresh_project_tree → tree_view.refresh() |
| 点击单个 Artifact → 画布渲染 | tree_view.artifact_selected → _on_artifact_clicked → _render_artifact |
| Ctrl+点击多选 → 画布叠加渲染 | tree_view.artifacts_selected → _on_artifacts_multi_selected → _viz.plot_multiple() |
| 按类型分组展开/折叠正常 | ProjectTreeView.refresh() 按 artifact_type 分组，setExpanded(True) |
| 空项目时项目树为空，不报错 | refresh(Project("empty")) → tree.clear() + 无分组 |
