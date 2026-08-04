"""内嵌 matplotlib 画布。

FigureCanvasQTAgg 嵌入 PyQt6 主窗口，支持 3D 轨道可视化和导航工具栏。
使用 QtAgg 后端（交互式，支持鼠标缩放/平移/旋转）。

渲染状态由 ``CanvasState`` 描述，``render()`` 是全量重绘单入口：
- 投影切换（3d/xy/xz/yz）会重建 Axes，无法增量，故全量重绘。
- 轨道数组复用内存注册表（``_states_by_id`` 等），切换投影/开关时
  不从磁盘/NPZ 重读——验收标准 #5（数据复用）的可测形式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("QtAgg")  # noqa: E402 -- 必须在 pyplot 导入前设置

from src.commons.font_config import apply_cjk_font_fallback

apply_cjk_font_fallback()

from matplotlib.backends.backend_qt import NavigationToolbar2QT  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

_PROJECTION_PLANE_AXES: dict[str, tuple[int, int]] = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}


@dataclass
class CanvasState:
    """画布渲染状态（architecture.md:247-252）。

    Attributes:
        projection: 投影平面，``"3d" | "xy" | "xz" | "yz"``。
        visible_artifacts: 当前显示的 artifact_id 列表。
        show_bodies: 是否显示地月标注。
        show_libration: 是否显示 L1-L5 拉格朗日点标注。
    """

    projection: str = "3d"
    visible_artifacts: list[str] = field(default_factory=list)
    show_bodies: bool = True
    show_libration: bool = True

    def copy(self) -> CanvasState:
        """返回副本（不可变更新模式：读当前 state → 改字段 → 传新 state）。"""
        return CanvasState(
            projection=self.projection,
            visible_artifacts=list(self.visible_artifacts),
            show_bodies=self.show_bodies,
            show_libration=self.show_libration,
        )


class OrbitCanvas(FigureCanvasQTAgg):
    """显示轨道的内嵌 matplotlib 画布。

    内部维护一个 Figure。调用 render() 按 CanvasState 全量重绘；
    plot_orbit() / plot_multiple() 保留为便捷薄封装（向后兼容）。
    """

    # tab10 调色板（architecture.md:405）
    _TAB10_COLORS: list[str] = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(8, 6), dpi=100)
        super().__init__(self._fig)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._setup_axes()
        self.setMinimumSize(400, 300)

        # 渲染状态与数据注册表
        self._state = CanvasState()
        # artifact_id -> 渲染数据（states / label / mu），由 main_window 经
        # set_artifacts_provider() 注入查询回调后按需填充。
        self._states_by_id: dict[str, Any] = {}
        self._labels_by_id: dict[str, str] = {}
        self._mu_by_id: dict[str, float | None] = {}
        self._artifacts_provider = None

    def _setup_axes(self, projection: str = "3d", *, title: str = "选择一个工件以可视化") -> None:
        ax = self._ax
        if projection == "3d":
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")
        else:
            # 2D 投影：轴标签与 _PROJECTION_PLANE_AXES 对齐
            labels = {"xy": ("X", "Y"), "xz": ("X", "Z"), "yz": ("Y", "Z")}
            xlabel, ylabel = labels[projection]
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        ax.set_title(title)

    def clear(self) -> None:
        self._fig.clear()
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._setup_axes()
        self.draw()

    # -- 数据提供 ----------------------------------------------------------

    def set_artifacts_provider(self, provider) -> None:
        """注入 artifact 数据查询回调（main_window 提供，返回 dict 或 None）。

        provider(artifact_id) -> {"states": ndarray, "label": str, "mu": float | None} | None
        """
        self._artifacts_provider = provider

    def sync_state(
        self,
        state: CanvasState,
        artifact_ids: list[str],
    ) -> None:
        """同步渲染状态并预取可见 Artifact 的渲染数据。

        数据来自内存（provider 回调），不从 NPZ 重读——切换投影/开关时
        数组已在内存，这是验收标准 #5 的实现方式。
        """
        self._state = state
        state.visible_artifacts = list(artifact_ids)
        self._states_by_id = {}
        self._labels_by_id = {}
        self._mu_by_id = {}
        for aid in artifact_ids:
            data = self._artifacts_provider(aid) if self._artifacts_provider else None
            if data is None:
                continue
            states = data.get("states")
            if states is None:
                continue
            self._states_by_id[aid] = states
            self._labels_by_id[aid] = data.get("label", "")
            self._mu_by_id[aid] = data.get("mu")

    # -- 渲染入口 ----------------------------------------------------------

    def render(self, state: CanvasState | None = None) -> None:
        """根据 CanvasState 全量重绘画布。

        调用方（main_window）在 CanvasState 变化时调此方法。
        数据复用：轨道数组来自内存注册表，不从磁盘/NPZ 重读。
        """
        state = state or self._state
        self._state = state
        self._fig.clear()
        projection = "3d" if state.projection == "3d" else None
        ax = self._fig.add_subplot(111, projection=projection)
        self._ax = ax

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

        has_orbits = bool(self._states_by_id)
        self._setup_axes(
            state.projection,
            title="" if has_orbits else "选择一个工件以可视化",
        )
        self._fig.tight_layout()
        self.draw()

    # -- 内部绘制 ----------------------------------------------------------

    def _draw_3d_orbits(self, ax, state) -> None:
        for i, aid in enumerate(state.visible_artifacts):
            states = self._states_by_id.get(aid)
            if states is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            pos = states[:, :3]
            ax.plot(
                pos[:, 0],
                pos[:, 1],
                pos[:, 2],
                linewidth=0.8,
                color=color,
                label=self._labels_by_id.get(aid, ""),
            )
            ax.scatter(*pos[0], s=30, c=color, zorder=5)

    def _draw_2d_orbits(self, ax, state) -> None:
        plane = _PROJECTION_PLANE_AXES[state.projection]
        for i, aid in enumerate(state.visible_artifacts):
            states = self._states_by_id.get(aid)
            if states is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            pos = states[:, :3]
            ax.plot(
                pos[:, plane[0]],
                pos[:, plane[1]],
                linewidth=0.8,
                color=color,
                label=self._labels_by_id.get(aid, ""),
            )

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

    # -- 便捷封装（向后兼容） -----------------------------------------------

    def plot_orbit(
        self,
        states,
        label: str = "",
        orbit_type: str = "",
    ) -> None:
        """绘制单条轨道（便捷封装，行为与 #335 之前一致）。

        Args:
            states:  形状 (n, 3) 或 (n, 6) 的状态数组。
            label:  图例标签。
            orbit_type:  轨道类型（影响标题和颜色）。
        """
        self._fig.clear()
        ax = self._fig.add_subplot(111, projection="3d")

        pos = states[:, :3]
        ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=0.8, label=label)

        # 标记起点
        ax.scatter(*pos[0], s=40, c="green", zorder=5, label="起点")

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        if orbit_type:
            ax.set_title(f"{orbit_type} 轨道")
        elif label:
            ax.set_title(label)

        if label:
            ax.legend(loc="upper left", fontsize=8)

        self._fig.tight_layout()
        self.draw()

    def plot_family(self, orbits_data: list, label: str = "") -> None:
        """绘制轨道族（多条轨道叠加）。

        Args:
            orbits_data:  列表，每项为 (states_array, orbit_label)。
        """
        self._fig.clear()
        ax = self._fig.add_subplot(111, projection="3d")

        for states, orb_label in orbits_data:
            pos = states[:, :3]
            ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=0.5, label=orb_label)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        if label:
            ax.set_title(label)

        if orbits_data:
            ax.legend(loc="upper left", fontsize=7, ncol=2)

        self._fig.tight_layout()
        self.draw()

    def plot_multiple(
        self,
        orbits: list[tuple],  # list[(ndarray, str)]
    ) -> None:
        """叠加渲染多条轨道（便捷封装）。

        每条轨道使用 tab10 调色板中不同颜色。

        Args:
            orbits: [(states_array, label), ...] 列表。
        """
        self._fig.clear()
        ax = self._fig.add_subplot(111, projection="3d")

        for i, (states, label) in enumerate(orbits):
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            pos = states[:, :3]
            ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=0.8, color=color, label=label)
            ax.scatter(*pos[0], s=30, c=color, zorder=5)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_title(f"叠加显示 ({len(orbits)} 条轨道)")

        if orbits:
            ax.legend(loc="upper left", fontsize=8)
        self._fig.tight_layout()
        self.draw()


class OrbitCanvasWithToolbar:
    """画布 + 导航工具栏 + 投影/标注工具栏的组合控件。"""

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QVBoxLayout, QWidget

        from src.view.canvas_toolbar import CanvasToolbar

        self.widget = QWidget(parent)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = OrbitCanvas(self.widget)
        self.toolbar = NavigationToolbar2QT(self.canvas, self.widget)
        self.projection_toolbar = CanvasToolbar(self.widget)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.projection_toolbar)
        layout.addWidget(self.canvas)

    def plot_orbit(self, **kwargs) -> None:
        self.canvas.plot_orbit(**kwargs)

    def plot_family(self, **kwargs) -> None:
        self.canvas.plot_family(**kwargs)

    def plot_multiple(self, **kwargs) -> None:
        self.canvas.plot_multiple(**kwargs)

    def clear(self) -> None:
        self.canvas.clear()
