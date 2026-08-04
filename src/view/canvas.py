"""内嵌 matplotlib 画布。

FigureCanvasQTAgg 嵌入 PyQt6 主窗口，支持 3D 轨道可视化和导航工具栏。
使用 QtAgg 后端（交互式，支持鼠标缩放/平移/旋转）。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")  # noqa: E402 -- 必须在 pyplot 导入前设置

from src.commons.font_config import apply_cjk_font_fallback

apply_cjk_font_fallback()

from matplotlib.backends.backend_qt import NavigationToolbar2QT  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402


class OrbitCanvas(FigureCanvasQTAgg):
    """显示轨道的内嵌 matplotlib 画布。

    内部维护一个 Figure + 3D Axes。调用 plot_orbit() 更新内容。
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

    def _setup_axes(self) -> None:
        ax = self._ax
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_title("选择一个工件以可视化")

    def clear(self) -> None:
        self._fig.clear()
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._setup_axes()
        self.draw()

    def plot_orbit(
        self,
        states,
        label: str = "",
        orbit_type: str = "",
    ) -> None:
        """绘制单条轨道。

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
        """叠加渲染多条轨道。

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
    """画布 + 导航工具栏的组合控件。"""

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QVBoxLayout, QWidget

        self.widget = QWidget(parent)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = OrbitCanvas(self.widget)
        self.toolbar = NavigationToolbar2QT(self.canvas, self.widget)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def plot_orbit(self, **kwargs) -> None:
        self.canvas.plot_orbit(**kwargs)

    def plot_family(self, **kwargs) -> None:
        self.canvas.plot_family(**kwargs)

    def plot_multiple(self, **kwargs) -> None:
        self.canvas.plot_multiple(**kwargs)

    def clear(self) -> None:
        self.canvas.clear()
