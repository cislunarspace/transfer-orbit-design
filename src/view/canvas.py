"""内嵌 matplotlib 画布。

FigureCanvasQTAgg 嵌入 PyQt6 主窗口，支持 3D 轨道可视化和导航工具栏。
使用 QtAgg 后端（交互式，支持鼠标缩放/平移/旋转）。

渲染状态由 ``CanvasState`` 描述，``render()`` 是全量重绘单入口：
- 投影切换（3d/xy/xz/yz）会重建 Axes，无法增量，故全量重绘。
- 轨道数组复用内存注册表（``_initial_guess_by_id`` 等），切换投影/开关时
  不从磁盘/NPZ 重读——验收标准 #5（数据复用）的可测形式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import matplotlib
import numpy as np

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
        frame: 坐标系，``"synodic" | "inertial"``。``"synodic"`` 复用 CR3BP 旋转
            系（无量纲，月球固定在 1−μ）；``"inertial"`` 画 GCRS/J2000 真视图：
            地球原点 + 月球 SPICE 真实轨迹 + position_km（km），不画平动点。
        plot_content: 绘制内容（与 frame 正交），``"guess" | "ephemeris" | "overlay"``。
            会合系下三选一可选；惯性系下``"guess"`` 不可用（CR3BP 无量纲无惯性系表示）。
            默认 ``"overlay"``：design_orbit 产物同时画初猜与星历。
    """

    projection: str = "3d"
    visible_artifacts: list[str] = field(default_factory=list)
    show_bodies: bool = True
    show_libration: bool = True
    frame: str = "synodic"
    plot_content: str = "overlay"

    def copy(self) -> CanvasState:
        """返回副本（不可变更新模式：读当前 state → 改字段 → 传新 state）。"""
        return CanvasState(
            projection=self.projection,
            visible_artifacts=list(self.visible_artifacts),
            show_bodies=self.show_bodies,
            show_libration=self.show_libration,
            frame=self.frame,
            plot_content=self.plot_content,
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
        # artifact_id -> 渲染数据，由 main_window 经 set_artifacts_provider()
        # 注入查询回调后按需填充。四个并列槽位（ADR 0013 + #359 数据契约）：
        #   initial_guess_states: CR3BP 周期轨道（无量纲会合系，质心归一）。
        #                         仅 design_orbit 产物有；control_orbit 为 None。
        #   ephemeris_synodic: 星历会合系位置（质心归一，已减 μ）。
        #                       design_orbit 的标称星历与 control_orbit 的受控星历共用此槽。
        #   ephemeris_position_km: 星历惯性系 GCRS km 位置。
        #   ephemeris_times_et: 物理时间（ET 秒），与上面两个星历槽同源。
        self._initial_guess_by_id: dict[str, Any] = {}
        self._ephemeris_synodic_by_id: dict[str, Any] = {}
        self._ephemeris_position_km_by_id: dict[str, Any] = {}
        self._ephemeris_times_et_by_id: dict[str, Any] = {}
        self._labels_by_id: dict[str, str] = {}
        self._mu_by_id: dict[str, float | None] = {}
        self._artifacts_provider = None

    def _setup_axes(self, projection: str = "3d", *, title: str = "选择一个工件以可视化") -> None:
        ax = self._ax
        if projection == "3d":
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            # projection=="3d" 时 add_subplot 返回 Axes3D，但 matplotlib
            # stubs 按基类 Axes 推断，无法按字符串收窄，故显式忽略此属性。
            ax.set_zlabel("Z")  # type: ignore[attr-defined]
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
        """注入 artifact 数据回调（main_window 提供，返回 dict 或 None）。

        provider(artifact_id) -> dict | None，dict 的契约字段（#359）：
            - ``label``: str
            - ``mu``: float | None
            - ``initial_guess_states``: ndarray (n,6) | None  -- CR3BP 周期轨道（无量纲会合系）
            - ``ephemeris_synodic``: ndarray (n,3|6) | None   -- 星历会合系位置（质心归一，已减 μ）
            - ``ephemeris_position_km``: ndarray (n,3) | None -- 星历惯性系 GCRS km
            - ``ephemeris_times_et``: ndarray (n,) | None     -- 物理时间 ET 秒
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

        四个并列槽位按 contract 显式读取（缺失对应槽位不写入注册表，
        渲染分支按 plot_content 选择消费）。
        """
        self._state = state
        state.visible_artifacts = list(artifact_ids)
        self._initial_guess_by_id = {}
        self._ephemeris_synodic_by_id = {}
        self._ephemeris_position_km_by_id = {}
        self._ephemeris_times_et_by_id = {}
        self._labels_by_id = {}
        self._mu_by_id = {}
        for aid in artifact_ids:
            data = self._artifacts_provider(aid) if self._artifacts_provider else None
            if data is None:
                continue
            label = data.get("label", "")
            mu = data.get("mu")
            initial = data.get("initial_guess_states")
            eph_syn = data.get("ephemeris_synodic")
            eph_pos = data.get("ephemeris_position_km")
            eph_t = data.get("ephemeris_times_et")
            # 显式契约：任一星历槽存在即认为该 Artifact 有内容；纯 CR3BP 初猜
            # 的旧 Artifact 仅 initial_guess 非 None。完全无内容则跳过。
            if initial is None and eph_syn is None and eph_pos is None:
                continue
            self._labels_by_id[aid] = label
            self._mu_by_id[aid] = mu
            if initial is not None:
                self._initial_guess_by_id[aid] = initial
            if eph_syn is not None:
                self._ephemeris_synodic_by_id[aid] = eph_syn
            if eph_pos is not None:
                self._ephemeris_position_km_by_id[aid] = eph_pos
            if eph_t is not None:
                self._ephemeris_times_et_by_id[aid] = eph_t

    # -- 渲染入口 ----------------------------------------------------------

    def render(self, state: CanvasState | None = None) -> None:
        """根据 CanvasState 全量重绘画布。

        调用方（main_window）在 CanvasState 变化时调此方法。
        数据复用：轨道数组来自内存注册表，不从磁盘/NPZ 重读。

        渲染按 ``frame × plot_content`` 组合（#359）：

        - ``frame="synodic"``：
          - ``plot_content="guess"``：仅画 ``initial_guess_states``（无量纲会合系）。
          - ``plot_content="ephemeris"``：仅画 ``ephemeris_synodic``（质心归一）。
          - ``plot_content="overlay"``：两者同画，初猜用实线、星历用虚线，
            各取 TAB10 相邻色以视觉区分。
        - ``frame="inertial"``：仅画 ``ephemeris_position_km``（GCRS km）；
          ``plot_content="guess"`` 在惯性系无几何意义，由 main_window 灰显控件并
          切到 ``"ephemeris"``，本层不再单独分支。

        投影（3d/xy/xz/yz）与 frame × plot_content 正交。
        """
        state = state or self._state
        self._state = state
        self._fig.clear()
        projection = "3d" if state.projection == "3d" else None
        ax = self._fig.add_subplot(111, projection=projection)
        self._ax = ax

        if state.frame == "inertial":
            # 1. 轨道（ephemeris_position_km）
            if state.projection == "3d":
                self._draw_3d_inertial_orbits(ax, state)
            else:
                self._draw_2d_inertial_orbits(ax, state)
            # 2. 地球原点 + 月球 SPICE 轨迹（依赖 show_bodies，与 synodic 一致）
            if state.show_bodies:
                self._draw_inertial_bodies(ax, state)
            # inertial 不画平动点（A3 决策）
        else:
            # 1. 轨道（按 plot_content 选初猜/星历/叠加）
            if state.projection == "3d":
                self._draw_3d_synodic_orbits(ax, state)
            else:
                self._draw_2d_synodic_orbits(ax, state)
            # 2. 地月标注（依赖 mu）
            if state.show_bodies:
                self._draw_bodies(ax, state)
            # 3. L1-L5 标注
            if state.show_libration:
                self._draw_libration(ax, state)

        if state.frame == "inertial":
            has_orbits = bool(self._ephemeris_position_km_by_id)
        else:
            has_orbits = bool(self._initial_guess_by_id) or bool(self._ephemeris_synodic_by_id)
        self._setup_axes(
            state.projection,
            title="" if has_orbits else "选择一个工件以可视化",
        )
        if state.projection == "3d":
            # 3D 等比例 box：按各轴数据范围设 box_aspect。mpl 3D 默认把 Figure
            # 宽高比塞进 3D 盒子（与数据无关），近平面轨道（DRO 等，Z 振幅远
            # 小于 XY）的 Z 会被放大约一个数量级，看起来大幅鼓起。
            ax.set_box_aspect(
                tuple(np.ptp(lim) for lim in (ax.get_xlim(), ax.get_ylim(), ax.get_zlim()))
            )
        else:
            # 2D 等比例：mpl 默认 aspect='auto' 让每轴独立填满画面，XZ/YZ 下
            # Z 数据远小于 X/Y 会被拉伸填满画面高度（同样约 9x 放大），与 3D
            # box_aspect 失真同类。等比例后如实反映轨道几何（DRO 显示为近平面）。
            ax.set_aspect("equal")
        self._fig.tight_layout()
        self.draw()

    # -- 内部绘制 ----------------------------------------------------------

    @staticmethod
    def _positions(states_or_pos: Any) -> Any:
        """取前 3 列作为位置（接受 (n,6) 状态矩阵或 (n,3) 位置数组）。"""
        arr = np.asarray(states_or_pos)
        return arr[:, :3] if arr.ndim == 2 and arr.shape[1] >= 3 else arr

    def _draw_3d_synodic_orbits(self, ax, state) -> None:
        """会合系轨道：按 plot_content 选 initial_guess / ephemeris_synodic / 两者叠加。

        叠加时初猜用实线、星历用虚线，相邻 TAB10 色区分；非叠加模式同一 artifact
        的两条数据按 TAB10 顺序着色（与现有约定一致）。
        """
        content = state.plot_content
        for i, aid in enumerate(state.visible_artifacts):
            label = self._labels_by_id.get(aid, "")
            base_color = self._TAB10_COLORS[(2 * i) % len(self._TAB10_COLORS)]
            eph_color = self._TAB10_COLORS[(2 * i + 1) % len(self._TAB10_COLORS)]
            if content in ("guess", "overlay"):
                initial = self._initial_guess_by_id.get(aid)
                if initial is not None:
                    pos = self._positions(initial)
                    ax.plot(
                        pos[:, 0],
                        pos[:, 1],
                        pos[:, 2],
                        linewidth=0.8,
                        color=base_color,
                        linestyle="-",
                        label=f"{label}（初猜）" if content == "overlay" else label,
                    )
                    ax.scatter(*pos[0], s=30, c=base_color, zorder=5)
            if content in ("ephemeris", "overlay"):
                eph_syn = self._ephemeris_synodic_by_id.get(aid)
                if eph_syn is not None:
                    pos = self._positions(eph_syn)
                    suffix = "（星历）" if content == "overlay" else ""
                    ax.plot(
                        pos[:, 0],
                        pos[:, 1],
                        pos[:, 2],
                        linewidth=0.8,
                        color=eph_color,
                        linestyle="--" if content == "overlay" else "-",
                        label=f"{label}{suffix}",
                    )
                    if content == "ephemeris":
                        ax.scatter(*pos[0], s=30, c=eph_color, zorder=5)

    def _draw_2d_synodic_orbits(self, ax, state) -> None:
        plane = _PROJECTION_PLANE_AXES[state.projection]
        content = state.plot_content
        for i, aid in enumerate(state.visible_artifacts):
            label = self._labels_by_id.get(aid, "")
            base_color = self._TAB10_COLORS[(2 * i) % len(self._TAB10_COLORS)]
            eph_color = self._TAB10_COLORS[(2 * i + 1) % len(self._TAB10_COLORS)]
            if content in ("guess", "overlay"):
                initial = self._initial_guess_by_id.get(aid)
                if initial is not None:
                    pos = self._positions(initial)
                    ax.plot(
                        pos[:, plane[0]],
                        pos[:, plane[1]],
                        linewidth=0.8,
                        color=base_color,
                        linestyle="-",
                        label=f"{label}（初猜）" if content == "overlay" else label,
                    )
            if content in ("ephemeris", "overlay"):
                eph_syn = self._ephemeris_synodic_by_id.get(aid)
                if eph_syn is not None:
                    pos = self._positions(eph_syn)
                    suffix = "（星历）" if content == "overlay" else ""
                    ax.plot(
                        pos[:, plane[0]],
                        pos[:, plane[1]],
                        linewidth=0.8,
                        color=eph_color,
                        linestyle="--" if content == "overlay" else "-",
                        label=f"{label}{suffix}",
                    )

    def _draw_bodies(self, ax, state) -> None:
        # 经 viz_adapter 调用 e2m2e，view 不直接 import e2m2e
        from src.engine.viz_adapter import draw_primary_bodies

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_primary_bodies(ax, mu, is_3d=is_3d, plane=plane)
                break  # 只画一次（同一 CR3BP 系统）

    def _draw_libration(self, ax, state) -> None:
        from src.engine.viz_adapter import draw_libration_points

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_libration_points(ax, mu, is_3d=is_3d, plane=plane)
                break

    # -- inertial 分支（GCRS/J2000，km）-----------------------------------

    def _draw_3d_inertial_orbits(self, ax, state) -> None:
        for i, aid in enumerate(state.visible_artifacts):
            position_km = self._ephemeris_position_km_by_id.get(aid)
            if position_km is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            ax.plot(
                position_km[:, 0],
                position_km[:, 1],
                position_km[:, 2],
                linewidth=0.8,
                color=color,
                label=self._labels_by_id.get(aid, ""),
            )
            ax.scatter(*position_km[0], s=30, c=color, zorder=5)

    def _draw_2d_inertial_orbits(self, ax, state) -> None:
        plane = _PROJECTION_PLANE_AXES[state.projection]
        for i, aid in enumerate(state.visible_artifacts):
            position_km = self._ephemeris_position_km_by_id.get(aid)
            if position_km is None:
                continue
            color = self._TAB10_COLORS[i % len(self._TAB10_COLORS)]
            ax.plot(
                position_km[:, plane[0]],
                position_km[:, plane[1]],
                linewidth=0.8,
                color=color,
                label=self._labels_by_id.get(aid, ""),
            )

    def _draw_inertial_bodies(self, ax, state) -> None:
        # 经 viz_adapter 调 SPICE 查月球 GCRS 位置；地球在原点（惯性系定义）
        from src.engine.viz_adapter import draw_earth_origin_marker, draw_moon_gcrs_trajectory

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        draw_earth_origin_marker(ax, is_3d=is_3d, plane=plane)
        # 月球轨迹用任一可见 Artifact 的 times_et（同一物理时段，月球轨迹唯一）
        for aid in state.visible_artifacts:
            times_et = self._ephemeris_times_et_by_id.get(aid)
            if times_et is not None:
                draw_moon_gcrs_trajectory(ax, times_et, is_3d=is_3d, plane=plane)
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
