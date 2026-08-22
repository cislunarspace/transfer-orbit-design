"""内嵌 matplotlib 画布。

FigureCanvasQTAgg 嵌入 PyQt6 主窗口，支持 3D 轨道可视化和导航工具栏。
使用 QtAgg 后端（交互式，支持鼠标缩放/平移/旋转）。

渲染状态由 ``CanvasState`` 描述，``render()`` 是全量重绘单入口：
- 投影切换（3d/xy/xz/yz）会重建 Axes，无法增量，故全量重绘。
- 轨道数组复用内存注册表（``_initial_guess_by_id`` 等），切换投影/开关时
  不从磁盘/NPZ 重读——验收标准 #5（数据复用）的可测形式。
- 视图保持：布局（投影 × 坐标系 × 中心）不变的重绘（如增添/移除轨道
  条目、开关标注）在重建前后捕获/恢复用户视角与坐标范围，不重置窗口。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("QtAgg")  # noqa: E402 -- 必须在 pyplot 导入前设置

from src.commons.font_config import apply_cjk_font_fallback

apply_cjk_font_fallback()

from matplotlib.backends.backend_qt import NavigationToolbar2QT  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402

from src.view.chart_settings import ChartSettings  # noqa: E402

_PROJECTION_PLANE_AXES: dict[str, tuple[int, int]] = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}

# 轨迹线标记：fit_to_data() 只按带此标记的轨道线适配视图，
# 标注（地月/平动点/月球轨迹）不打标记即不参与（CONTEXT.md: 视图适配）
_ORBIT_GID = "orbit"

# 时间轴 marker：飞行器/月球此刻位置（ADR 0014）。不参与视图适配
# （同标注待遇），测试经此 gid 断言。
_MARKER_GID = "timeline-marker"


@dataclass
class CanvasState:
    """画布渲染状态（architecture.md:247-252）。

    Attributes:
        projection: 投影平面，``"3d" | "xy" | "xz" | "yz" | "quad"``。``"quad"`` 为四视图
            布局（2x2 网格同时显示 3D + XY/XZ/YZ），面向大窗口/全屏减少留白。
        visible_artifacts: 当前显示的 artifact_id 列表。
        show_bodies: 是否显示地月标注。
        show_libration: 是否显示 L1-L5 拉格朗日点标注。
        frame: 坐标系，``"synodic" | "inertial"``。``"synodic"`` 复用 CR3BP 旋转
            系（无量纲，月球固定在 1−μ）；``"inertial"`` 画 GCRS/J2000 真视图：
            地球原点 + 月球 SPICE 真实轨迹 + position_km（km），不画平动点。
        plot_content: 绘制内容（与 frame 正交），``"guess" | "ephemeris" | "overlay"``。
            会合系下三选一可选；惯性系下``"guess"`` 不可用（CR3BP 无量纲无惯性系表示）。
            默认 ``"overlay"``：design_orbit 产物同时画初猜与星历。
        equal_aspect: 是否等比例显示。``True``（默认）时 3D 按数据范围设 box_aspect、
            2D 设 aspect='equal'，如实反映轨道几何；近平面轨道（Z 振幅远小于 XY）的
            Z 轴区间会扩大到 XY 的 ``z_ratio`` 倍（默认 0.5），避免压成一条线。
            ``False`` 时各轴独立缩放填满画面。
        center: 绘图中心，``"barycenter" | "moon" | "L1" | "L2"``（会合系）。
            渲染时整体平移使所选点成为坐标原点。惯性系下 ``"L1"/"L2"`` 无意义
            （由 main_window 灰显），``"barycenter"`` 即地球原点、``"moon"`` 为
            月球中心。
    """

    projection: str = "3d"
    visible_artifacts: list[str] = field(default_factory=list)
    show_bodies: bool = True
    show_libration: bool = True
    frame: str = "synodic"
    plot_content: str = "overlay"
    equal_aspect: bool = True
    center: str = "barycenter"
    # 时间轴选中的物理时刻（ET 秒，ADR 0014）；None 表示时间轴未激活，
    # 不画飞行器/月球此刻 marker。两坐标系共享同一时刻。
    current_et: float | None = None

    def copy(self) -> CanvasState:
        """返回副本（不可变更新模式：读当前 state → 改字段 → 传新 state）。"""
        return CanvasState(
            projection=self.projection,
            visible_artifacts=list(self.visible_artifacts),
            show_bodies=self.show_bodies,
            show_libration=self.show_libration,
            frame=self.frame,
            plot_content=self.plot_content,
            equal_aspect=self.equal_aspect,
            center=self.center,
            current_et=self.current_et,
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
        # 图表设置（线宽/颜色方案/标注大小/字号/Z 区间比例），
        # 由 main_window 经 set_chart_settings() 注入；先于 _setup_axes 初始化
        self._chart = ChartSettings()
        self._fig = Figure(figsize=(8, 6), dpi=100)
        super().__init__(self._fig)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._setup_axes(self._ax)
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
        self._family_by_id: dict[str, Any] = {}
        self._initial_guess_times_by_id: dict[str, Any] = {}
        self._family_times_by_id: dict[str, Any] = {}
        self._artifacts_provider = None
        # 视图保持：_layout_key 记录上次渲染的 (projection, frame, center)，
        # _view_valid 标记当前 Axes 是否承载过数据。main_window 原地修改
        # CanvasState，布局变化只能靠 render 末尾记录的键识别。
        self._layout_key: tuple[str, str, str] | None = None
        self._view_valid = False
        # 各 Axes 对应的投影（单视图一个元素；四视图 ["3d","xy","xz","yz"]），
        # fit_to_data 按子图投影应用等比/z_ratio 约束
        self._axes_projections: list[str] = ["3d"]

    def _setup_axes(
        self, ax, projection: str = "3d", *, title: str = "选择一个工件以可视化"
    ) -> None:
        fontsize = self._chart.label_fontsize
        if projection == "3d":
            ax.set_xlabel("X", fontsize=fontsize)
            ax.set_ylabel("Y", fontsize=fontsize)
            # projection=="3d" 时 add_subplot 返回 Axes3D，但 matplotlib
            # stubs 按基类 Axes 推断，无法按字符串收窄，故显式忽略此属性。
            ax.set_zlabel("Z", fontsize=fontsize)  # type: ignore[attr-defined]
        else:
            # 2D 投影：轴标签与 _PROJECTION_PLANE_AXES 对齐
            labels = {"xy": ("X", "Y"), "xz": ("X", "Z"), "yz": ("Y", "Z")}
            xlabel, ylabel = labels[projection]
            ax.set_xlabel(xlabel, fontsize=fontsize)
            ax.set_ylabel(ylabel, fontsize=fontsize)
        ax.set_title(title, fontsize=fontsize + 2)
        ax.tick_params(labelsize=fontsize - 1)

    def clear(self) -> None:
        self._fig.clear()
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._setup_axes(self._ax)
        self._layout_key = None
        self._view_valid = False
        self.draw()

    # -- 数据提供 ----------------------------------------------------------

    def set_artifacts_provider(self, provider) -> None:
        """注入 artifact 数据回调（main_window 提供，返回 dict 或 None）。

        provider(artifact_id) -> dict | None，dict 的契约字段（#359）：
            - ``label``: str
            - ``mu``: float | None
            - ``initial_guess_states``: ndarray (n,6) | None  -- CR3BP 周期轨道（无量纲会合系）
            - ``initial_guess_times``: ndarray (n,) | None   -- 无量纲会合系时间（θ=角度）
            - ``ephemeris_synodic``: ndarray (n,3|6) | None   -- 星历会合系位置（质心归一，已减 μ）
            - ``ephemeris_position_km``: ndarray (n,3) | None -- 星历惯性系 GCRS km
            - ``ephemeris_times_et``: ndarray (n,) | None     -- 物理时间 ET 秒
            - ``family_states``: ndarray (m,n,6) | None       -- 轨道族（无量纲会合系）
            - ``family_times``: ndarray (m,n) | None          -- 族各成员无量纲时间
        """
        self._artifacts_provider = provider

    def set_chart_settings(self, settings: ChartSettings) -> None:
        """注入图表设置（线宽/颜色方案/标注大小/字号/Z 区间比例）。"""
        self._chart = settings

    def _orbit_color(self, index: int) -> Any:
        """按设置的颜色方案取第 index 条轨道的颜色。"""
        name = self._chart.colormap
        if name == "tab10":
            return self._TAB10_COLORS[index % len(self._TAB10_COLORS)]
        cmap = matplotlib.colormaps[name]
        return cmap(index % cmap.N)

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
        self._family_by_id = {}
        self._initial_guess_times_by_id = {}
        self._family_times_by_id = {}
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
            family = data.get("family_states")
            initial_t = data.get("initial_guess_times")
            family_t = data.get("family_times")
            # 显式契约：任一星历槽存在即认为该 Artifact 有内容；纯 CR3BP 初猜
            # 的旧 Artifact 仅 initial_guess 非 None。完全无内容则跳过。
            if initial is None and eph_syn is None and eph_pos is None and family is None:
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
            if family is not None:
                self._family_by_id[aid] = family
            if initial_t is not None:
                self._initial_guess_times_by_id[aid] = initial_t
            if family_t is not None:
                self._family_times_by_id[aid] = family_t

    def ephemeris_time_union(self) -> tuple[float, float] | None:
        """可见星历产物 times_et 的并集区间；无星历产物为 None（ADR 0014）。"""
        spans = [
            (float(np.min(t)), float(np.max(t)))
            for t in self._ephemeris_times_et_by_id.values()
            if t is not None and len(np.asarray(t)) > 0
        ]
        if not spans:
            return None
        return min(s[0] for s in spans), max(s[1] for s in spans)

    # -- 渲染入口 ----------------------------------------------------------

    def render(self, state: CanvasState | None = None, *, preserve_view: bool = True) -> None:
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

        视图保持：布局（projection × frame × center）不变且当前 Axes 承载过
        数据时，重建前捕获各 Axes 的视角与坐标范围、绘制后恢复——增添/移除
        轨道条目、开关标注等重绘不重置窗口；布局切换改变视图空间，仍走
        自动缩放与居中调整。

        Args:
            state: 新渲染状态；None 沿用当前。
            preserve_view: False 时关闭视图保持，每帧按自身数据自动缩放
                （GIF 导出逐帧渲染用，各帧数据是增长前缀/滑动窗口）。
        """
        state = state or self._state
        self._state = state
        layout_key = (state.projection, state.frame, state.center)
        views = (
            [self._capture_view(ax) for ax in self._fig.axes]
            if preserve_view and self._view_valid and self._layout_key == layout_key
            else None
        )
        self._fig.clear()
        if state.projection == "quad":
            # 四视图：2x2 网格（3D + XY/XZ/YZ），充分利用大窗口/全屏空间，
            # 避免单图等比例缩在中间造成四周大量留白。
            for i, proj in enumerate(("3d", "xy", "xz", "yz"), start=1):
                ax = self._fig.add_subplot(2, 2, i, projection="3d" if proj == "3d" else None)
                sub_state = replace(state, projection=proj)
                self._render_axes(ax, sub_state)
            # 供 fit_to_data 区分四视图各子图的投影（等比/z_ratio 逻辑依赖）
            self._axes_projections = ["3d", "xy", "xz", "yz"]
        else:
            projection = "3d" if state.projection == "3d" else None
            ax = self._fig.add_subplot(111, projection=projection)
            self._ax = ax
            self._render_axes(ax, state)
            self._axes_projections = [state.projection]
        if views is not None:
            # 布局不变：恢复用户视角与坐标范围（覆盖 _render_axes 的自动
            # 缩放/居中/等比调整——用户的窗口是最终裁决）
            for ax, view in zip(self._fig.axes, views, strict=True):
                self._restore_view(ax, state, view)
        self._fig.tight_layout()
        # 记录本次布局与数据状态，供下次 render 判断是否保持视图
        self._layout_key = layout_key
        self._view_valid = (
            bool(self._ephemeris_position_km_by_id)
            or bool(self._initial_guess_by_id)
            or bool(self._ephemeris_synodic_by_id)
            or bool(self._family_by_id)
        )
        self.draw()

    def _capture_view(self, ax) -> dict[str, Any]:
        """捕获单个 Axes 的视图快照（用户旋转/缩放后的窗口状态）。

        3D：相机角（elev/azim/roll）+ 三轴范围；2D：两轴范围。mpl 3.10 起
        3D 的缩放/平移都落在轴范围上（相机距离 dist 已移除），故范围加
        相机角即完整视图状态。
        """
        view: dict[str, Any] = {"xlim": ax.get_xlim(), "ylim": ax.get_ylim()}
        if isinstance(ax, Axes3D):
            view["zlim"] = ax.get_zlim()
            view["elev"] = ax.elev
            view["azim"] = ax.azim
            view["roll"] = ax.roll
        return view

    def _restore_view(self, ax, state: CanvasState, view: dict[str, Any]) -> None:
        """把视图快照恢复到重建后的 Axes。"""
        ax.set_xlim(view["xlim"])
        ax.set_ylim(view["ylim"])
        if isinstance(ax, Axes3D):
            ax.set_zlim(view["zlim"])
            ax.view_init(elev=view["elev"], azim=view["azim"], roll=view["roll"])
            if state.equal_aspect:
                # 等比例的 box_aspect 在 _render_axes 按自动缩放范围计算，
                # 恢复用户范围后须按恢复范围重设，否则几何失真
                ax.set_box_aspect(
                    tuple(np.ptp(lim) for lim in (view["xlim"], view["ylim"], view["zlim"]))
                )

    def _render_axes(self, ax, state: CanvasState) -> None:
        """在单个 Axes 上按 state 绘制轨道 + 标注（单视图与四视图共用）。"""
        moon_shift: dict[str, Any] = {}
        center = np.zeros(3)
        if state.frame == "synodic" and state.center != "barycenter":
            center = self._center_offset(state)
        if state.frame == "inertial":
            # 月球位置（center=moon 平移、月球/地球轨迹共用；不可用为 None）
            moon_shift = self._inertial_moon_positions(state)
            # 1. 轨道：优先真惯性系 position_km；无则用会合系旋转近似视图
            #    （轨道族/旧初猜等纯 CR3BP 产物，历元对齐取 θ(t=0)=0）
            if state.projection == "3d":
                self._draw_3d_inertial_orbits(ax, state, moon_shift)
            else:
                self._draw_2d_inertial_orbits(ax, state, moon_shift)
            # 2. 地球原点 + 月球轨迹（依赖 show_bodies，与 synodic 一致）
            if state.show_bodies:
                self._draw_inertial_bodies(ax, state, moon_shift)
            # inertial 不画平动点（A3 决策）
        else:
            # 1. 轨道（按 plot_content 选初猜/星历/叠加）
            if state.projection == "3d":
                self._draw_3d_synodic_orbits(ax, state, center)
            else:
                self._draw_2d_synodic_orbits(ax, state, center)
            # 2. 地月标注（依赖 mu）
            if state.show_bodies:
                self._draw_bodies(ax, state, center)
            # 3. L1-L5 标注
            if state.show_libration:
                self._draw_libration(ax, state, center)

        has_orbits = (
            bool(self._ephemeris_position_km_by_id)
            or bool(self._initial_guess_by_id)
            or bool(self._ephemeris_synodic_by_id)
            or bool(self._family_by_id)
        )
        moon_unavailable = (
            state.frame == "inertial"
            and state.center == "moon"
            and not any(v is not None for v in moon_shift.values())
        )
        if moon_unavailable:
            title = "月球位置不可用（SPICE 查询失败），无法使用月球中心视图"
        elif has_orbits:
            title = ""
        elif state.frame == "inertial":
            title = "所选记录没有惯性系星历数据"
        else:
            title = "在左侧项目树中选择一条记录以显示轨道"
        self._setup_axes(ax, state.projection, title=title)
        # 自定义中心视图（月球/L1/L2；惯性系月球中心）：坐标轴范围对称于
        # 中心点（平移后即原点），使所选中心位于画面正中央。否则 mpl
        # autoscale 会按平移后的数据重新居中，视觉上“中心没变”。
        is_custom_center = (state.frame == "synodic" and state.center != "barycenter") or (
            state.frame == "inertial" and state.center == "moon"
        )
        self._adjust_axes_limits(ax, state, symmetrize=is_custom_center)
        self._add_legend(ax)

    def _adjust_axes_limits(self, ax, state: CanvasState, *, symmetrize: bool = False) -> None:
        """按当前轴范围应用对称居中/等比/z_ratio 约束（渲染与视图适配共用）。

        调用前提：轴范围已由 autoscale 或 fit_to_data 按数据设好。
        symmetrize=True 时先把各轴范围对称化到 0（自定义中心视图，平移后
        中心即原点），再做等比约束。
        """
        if symmetrize:
            ax.set_xlim(*self._symmetrize(*ax.get_xlim()))
            ax.set_ylim(*self._symmetrize(*ax.get_ylim()))
            if state.projection == "3d":
                ax.set_zlim(*self._symmetrize(*ax.get_zlim()))  # type: ignore[attr-defined]
        if state.projection == "3d":
            # 3D 等比例：按各轴显示区间设 box_aspect。Z 区间先“多取一些”
            # （至少为 XY 较小范围的 z_ratio 倍），避免近平面
            # 轨道（DRO 等，Z 振幅远小于 XY）被压成一条线。
            if state.equal_aspect:
                xspan = np.ptp(ax.get_xlim())
                yspan = np.ptp(ax.get_ylim())
                zlim = ax.get_zlim()  # type: ignore[attr-defined]
                target = max(np.ptp(zlim), min(xspan, yspan) * self._chart.z_ratio)
                zmid = (zlim[0] + zlim[1]) / 2
                ax.set_zlim(zmid - target / 2, zmid + target / 2)  # type: ignore[attr-defined]
                ax.set_box_aspect(
                    tuple(np.ptp(lim) for lim in (ax.get_xlim(), ax.get_ylim(), ax.get_zlim()))  # type: ignore[attr-defined, arg-type]
                )
            # equal_aspect=False 时保留 mpl 默认（各轴独立缩放填满画面）。
        else:
            # 2D 等比例：XZ/YZ 投影纵轴是 Z，同样“多取一些”避免压成细条。
            if state.equal_aspect:
                plane = _PROJECTION_PLANE_AXES[state.projection]
                if plane[1] == 2:
                    xspan = np.ptp(ax.get_xlim())
                    ylim = ax.get_ylim()
                    target = max(np.ptp(ylim), xspan * self._chart.z_ratio)
                    ymid = (ylim[0] + ylim[1]) / 2
                    ax.set_ylim(ymid - target / 2, ymid + target / 2)
                ax.set_aspect("equal")
            else:
                # 非等比：每轴独立 autoscale 填满画面，Z 细节清晰可见。
                ax.set_aspect("auto")

    def fit_to_data(self) -> None:
        """视图适配：按当前可见轨道轨迹的坐标范围重设各轴显示窗口。

        轴范围 = 轨道数据范围 + 每轴 5% 余量（对称展开）；标注
        （地月/平动点/月球轨迹，未打 gid=_ORBIT_GID 标记）不参与。
        不重建 Figure、不清 3D 相机角；适配结果成为后续 render 的
        视图保持基准。无轨道数据时不做任何事。
        """
        for ax, proj in zip(self._fig.axes, self._axes_projections, strict=True):
            stacked: list[np.ndarray] = []
            for line in ax.lines:
                if line.get_gid() != _ORBIT_GID:
                    continue
                if isinstance(ax, Axes3D):
                    # Line3D 才有 get_data_3d；stubs 按基类 Line2D 推断
                    stacked.append(np.asarray(line.get_data_3d()).T)  # type: ignore[attr-defined]
                else:
                    xdata, ydata = line.get_data()
                    stacked.append(np.column_stack((xdata, ydata)))
            if not stacked:
                continue
            pts = np.vstack(stacked)
            lo = pts.min(axis=0)
            hi = pts.max(axis=0)
            # 5% 余量：每轴总跨度 × 1.05，对称展开
            mids = (lo + hi) / 2
            half = (hi - lo) * 1.05 / 2
            lims = [(m - h, m + h) for m, h in zip(mids, half, strict=True)]
            ax.set_xlim(*lims[0])
            ax.set_ylim(*lims[1])
            if isinstance(ax, Axes3D):
                ax.set_zlim(*lims[2])  # type: ignore[attr-defined]
            # 与 _render_axes 末尾同一套收尾：自定义中心对称化 + 等比/z_ratio
            sub_state = replace(self._state, projection=proj)
            is_custom_center = (
                sub_state.frame == "synodic" and sub_state.center != "barycenter"
            ) or (sub_state.frame == "inertial" and sub_state.center == "moon")
            self._adjust_axes_limits(ax, sub_state, symmetrize=is_custom_center)
        self.draw()

    def _add_legend(self, ax) -> None:
        """为已标记的轨迹和天体自动生成图例。"""
        handles, labels = ax.get_legend_handles_labels()
        if not handles:
            return
        ax.legend(
            handles,
            labels,
            loc="upper left",
            fontsize=max(self._chart.label_fontsize - 1, 6),
            ncol=2 if len(labels) > 4 else 1,
        )

    # -- 内部绘制 ----------------------------------------------------------

    @staticmethod
    def _positions(states_or_pos: Any) -> Any:
        """取前 3 列作为位置（接受 (n,6) 状态矩阵或 (n,3) 位置数组）。"""
        arr = np.asarray(states_or_pos)
        return arr[:, :3] if arr.ndim == 2 and arr.shape[1] >= 3 else arr

    @staticmethod
    def _position_at(times_et: Any, pos: Any, et: float):
        """时间轴插值（ADR 0014）：et 处的线性插值位置；超出范围为 None。"""
        t = np.asarray(times_et, dtype=np.float64)
        p = np.asarray(pos)[:, :3]
        if et < t[0] or et > t[-1]:
            return None
        return np.array([np.interp(et, t, p[:, k]) for k in range(3)])

    def _draw_timeline_marker_3d(self, ax, state, times, pos, color, center) -> None:
        """会合系/惯性系 3D 飞行器此刻 marker（时间轴激活时）。"""
        if state.current_et is None or times is None:
            return
        here = self._position_at(times, pos, state.current_et)
        if here is None:
            return
        xyz = here - center
        ax.plot(
            [xyz[0]],
            [xyz[1]],
            [xyz[2]],
            "o",
            color=color,
            markersize=6,
            markeredgecolor="black",
            markeredgewidth=0.8,
            zorder=6,
            gid=_MARKER_GID,
            label="飞行器（此刻）",
        )

    def _draw_timeline_marker_2d(self, ax, state, times, pos, color, plane) -> None:
        """会合系/惯性系 2D 飞行器此刻 marker。"""
        if state.current_et is None or times is None:
            return
        here = self._position_at(times, pos, state.current_et)
        if here is None:
            return
        ax.scatter(
            here[plane[0]],
            here[plane[1]],
            s=45,
            c=color,
            edgecolors="black",
            linewidths=0.8,
            zorder=6,
            gid=_MARKER_GID,
            label="飞行器（此刻）",
        )

    @staticmethod
    def _symmetrize(lo: float, hi: float) -> tuple[float, float]:
        """把 (lo, hi) 展成以 0 为中心的对称区间，保持覆盖原范围。"""
        r = max(abs(lo), abs(hi))
        return (-r, r)

    def _center_offset(self, state: CanvasState) -> Any:
        """会合系中心点（无量纲，质心归一）——渲染时整体平移用。

        ``center="barycenter"`` 返回零向量；其余经 viz_adapter 计算
        （月球 (1-μ,0,0)；L1/L2 由 e2m2e 解算）。无 mu 可用时回退质心。
        """
        if state.center == "barycenter":
            return np.zeros(3)
        mu: float | None = None
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                break
        if mu is None:
            return np.zeros(3)
        from src.engine.viz_adapter import body_center_offset

        return np.asarray(body_center_offset(mu, state.center))

    def _draw_3d_synodic_orbits(self, ax, state, center) -> None:
        """会合系轨道：按 plot_content 选 initial_guess / ephemeris_synodic / 两者叠加。

        叠加时初猜用实线、星历用虚线，相邻 TAB10 色区分；非叠加模式同一 artifact
        的两条数据按 TAB10 顺序着色（与现有约定一致）。所有坐标整体减去 ``center``
        （中心视图平移）。
        """
        content = state.plot_content
        for i, aid in enumerate(state.visible_artifacts):
            label = self._labels_by_id.get(aid, "")
            base_color = self._orbit_color(2 * i)
            eph_color = self._orbit_color(2 * i + 1)
            if aid in self._family_by_id:
                # 轨道族：m 条成员按 viridis 渐变色逐条绘制，覆盖普通槽。
                self._draw_family_3d(ax, self._family_by_id[aid], label, center)
                continue
            if content in ("guess", "overlay"):
                initial = self._initial_guess_by_id.get(aid)
                if initial is not None:
                    pos = self._positions(initial) - center
                    ax.plot(
                        pos[:, 0],
                        pos[:, 1],
                        pos[:, 2],
                        linewidth=self._chart.orbit_linewidth,
                        color=base_color,
                        linestyle="-",
                        gid=_ORBIT_GID,
                        label=f"{label}（初猜）" if content == "overlay" else label,
                    )
                    ax.scatter(*pos[0], s=30, c=base_color, zorder=5)
            if content in ("ephemeris", "overlay"):
                eph_syn = self._ephemeris_synodic_by_id.get(aid)
                if eph_syn is not None:
                    pos = self._positions(eph_syn) - center
                    suffix = "（星历）" if content == "overlay" else ""
                    ax.plot(
                        pos[:, 0],
                        pos[:, 1],
                        pos[:, 2],
                        linewidth=self._chart.orbit_linewidth,
                        color=eph_color,
                        linestyle="--" if content == "overlay" else "-",
                        gid=_ORBIT_GID,
                        label=f"{label}{suffix}",
                    )
                    if content == "ephemeris":
                        ax.scatter(*pos[0], s=30, c=eph_color, zorder=5)
                    self._draw_timeline_marker_3d(
                        ax, state, self._ephemeris_times_et_by_id.get(aid), pos, eph_color, center
                    )

    def _draw_family_3d(self, ax, family_states: Any, label: str, center) -> None:
        """轨道族 3D 渲染：m 条成员按 viridis 渐变色逐条绘制。

        ``family_states`` 为 ``(m, n, 6)``（无量纲会合系，质心归一）。
        颜色从浅到深映射成员 z 振幅递增，起点小点标记族起始端。
        """
        import matplotlib.colors as mcolors

        arr = np.asarray(family_states)
        if arr.ndim != 3:
            return
        m = arr.shape[0]
        norm = mcolors.Normalize(vmin=0.0, vmax=max(m - 1, 1))
        cmap = matplotlib.colormaps["viridis"]
        for j in range(m):
            pos = arr[j][:, :3] - center
            color = cmap(norm(j))
            ax.plot(
                pos[:, 0],
                pos[:, 1],
                pos[:, 2],
                linewidth=self._chart.orbit_linewidth,
                color=color,
                gid=_ORBIT_GID,
                label=label if j == 0 else None,
            )
        ax.scatter(*(arr[0][0, :3] - center), s=20, color=cmap(norm(0)), zorder=5)

    def _draw_family_2d(
        self, ax, family_states: Any, label: str, plane: tuple[int, int], center
    ) -> None:
        """轨道族 2D 投影渲染（渐变色逐条，逻辑同 _draw_family_3d）。"""
        import matplotlib.colors as mcolors

        arr = np.asarray(family_states)
        if arr.ndim != 3:
            return
        m = arr.shape[0]
        norm = mcolors.Normalize(vmin=0.0, vmax=max(m - 1, 1))
        cmap = matplotlib.colormaps["viridis"]
        for j in range(m):
            pos = arr[j][:, :3] - center
            ax.plot(
                pos[:, plane[0]],
                pos[:, plane[1]],
                linewidth=self._chart.orbit_linewidth,
                color=cmap(norm(j)),
                gid=_ORBIT_GID,
                label=label if j == 0 else None,
            )

    def _draw_2d_synodic_orbits(self, ax, state, center) -> None:
        plane = _PROJECTION_PLANE_AXES[state.projection]
        content = state.plot_content
        for i, aid in enumerate(state.visible_artifacts):
            label = self._labels_by_id.get(aid, "")
            base_color = self._orbit_color(2 * i)
            eph_color = self._orbit_color(2 * i + 1)
            if aid in self._family_by_id:
                # 轨道族：2D 投影逐条绘制
                self._draw_family_2d(ax, self._family_by_id[aid], label, plane, center)
                continue
            if content in ("guess", "overlay"):
                initial = self._initial_guess_by_id.get(aid)
                if initial is not None:
                    pos = self._positions(initial) - center
                    ax.plot(
                        pos[:, plane[0]],
                        pos[:, plane[1]],
                        linewidth=self._chart.orbit_linewidth,
                        color=base_color,
                        gid=_ORBIT_GID,
                        linestyle="-",
                        label=f"{label}（初猜）" if content == "overlay" else label,
                    )
            if content in ("ephemeris", "overlay"):
                eph_syn = self._ephemeris_synodic_by_id.get(aid)
                if eph_syn is not None:
                    pos = self._positions(eph_syn) - center
                    suffix = "（星历）" if content == "overlay" else ""
                    ax.plot(
                        pos[:, plane[0]],
                        pos[:, plane[1]],
                        linewidth=self._chart.orbit_linewidth,
                        color=eph_color,
                        gid=_ORBIT_GID,
                        linestyle="--" if content == "overlay" else "-",
                        label=f"{label}{suffix}",
                    )
                    self._draw_timeline_marker_2d(
                        ax,
                        state,
                        self._ephemeris_times_et_by_id.get(aid),
                        pos,
                        eph_color,
                        plane,
                    )

    def _draw_bodies(self, ax, state, center) -> None:
        # 经 viz_adapter 调用 e2m2e，view 不直接 import e2m2e
        from src.engine.viz_adapter import draw_primary_bodies

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_primary_bodies(
                    ax,
                    mu,
                    is_3d=is_3d,
                    plane=plane,
                    center=tuple(center),
                    earth_size=self._chart.earth_size,
                    moon_size=self._chart.moon_size,
                    fontsize=self._chart.label_fontsize,
                )
                break  # 只画一次（同一 CR3BP 系统）

    def _draw_libration(self, ax, state, center) -> None:
        from src.engine.viz_adapter import draw_libration_points

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        for aid in state.visible_artifacts:
            mu = self._mu_by_id.get(aid)
            if mu is not None:
                draw_libration_points(
                    ax,
                    mu,
                    is_3d=is_3d,
                    plane=plane,
                    center=tuple(center),
                    color=self._chart.lp_color,
                    size=self._chart.lp_size,
                    fontsize=self._chart.label_fontsize,
                )
                break

    # -- inertial 分支（GCRS/J2000，km）-----------------------------------

    def _draw_3d_inertial_orbits(self, ax, state, moon_shift) -> None:
        for i, aid in enumerate(state.visible_artifacts):
            color = self._orbit_color(i)
            label = self._labels_by_id.get(aid, "")
            position_km = self._ephemeris_position_km_by_id.get(aid)
            if position_km is not None:
                pos = np.asarray(position_km)[:, :3]
                if state.center == "moon":
                    moon = moon_shift.get(aid)
                    if moon is None:
                        # 月球位置不可用：跳过轨道，避免地心/月心坐标同屏错位
                        continue
                    pos = pos - moon
                ax.plot(
                    pos[:, 0],
                    pos[:, 1],
                    pos[:, 2],
                    linewidth=self._chart.orbit_linewidth,
                    color=color,
                    gid=_ORBIT_GID,
                    label=label,
                )
                ax.scatter(*pos[0], s=30, c=color, zorder=5)
                # marker 对平移后的 pos 插值即可（moon 中心分支 pos 已含平移）
                self._draw_timeline_marker_3d(
                    ax,
                    state,
                    self._ephemeris_times_et_by_id.get(aid),
                    pos,
                    color,
                    np.zeros(3),
                )
                continue
            # 无 position_km：会合系旋转近似视图（轨道族/旧初猜等纯 CR3BP 产物）
            self._draw_inertial_approx(ax, aid, state, color, plane=None)

    def _draw_2d_inertial_orbits(self, ax, state, moon_shift) -> None:
        plane = _PROJECTION_PLANE_AXES[state.projection]
        for i, aid in enumerate(state.visible_artifacts):
            color = self._orbit_color(i)
            label = self._labels_by_id.get(aid, "")
            position_km = self._ephemeris_position_km_by_id.get(aid)
            if position_km is not None:
                pos = np.asarray(position_km)[:, :3]
                if state.center == "moon":
                    moon = moon_shift.get(aid)
                    if moon is None:
                        # 月球位置不可用：跳过轨道，避免地心/月心坐标同屏错位
                        continue
                    pos = pos - moon
                ax.plot(
                    pos[:, plane[0]],
                    pos[:, plane[1]],
                    linewidth=self._chart.orbit_linewidth,
                    color=color,
                    gid=_ORBIT_GID,
                    label=label,
                )
                self._draw_timeline_marker_2d(
                    ax,
                    state,
                    self._ephemeris_times_et_by_id.get(aid),
                    pos,
                    color,
                    plane,
                )
                continue
            self._draw_inertial_approx(ax, aid, state, color, plane=plane)

    def _inertial_moon_positions(self, state) -> dict[str, Any]:
        """各可见 Artifact 的月球 GCRS 位置（km）；不可用为 None。

        近似视图（轨道族/旧初猜）用解析正圆位置（无需 SPICE）；真惯性系
        用 SPICE 查询。返回 dict 供轨道平移与月球/地球轨迹共用，避免
        同一时间轴多次 SPICE 查询。
        """
        from src.engine.viz_adapter import approx_moon_gcrs_km, moon_position_gcrs

        out: dict[str, Any] = {}
        for aid in state.visible_artifacts:
            family_times = self._family_times_by_id.get(aid)
            if family_times is not None:
                out[aid] = approx_moon_gcrs_km(np.asarray(family_times)[0])
                continue
            initial_times = self._initial_guess_times_by_id.get(aid)
            if initial_times is not None:
                out[aid] = approx_moon_gcrs_km(np.asarray(initial_times))
                continue
            times_et = self._ephemeris_times_et_by_id.get(aid)
            out[aid] = moon_position_gcrs(times_et) if times_et is not None else None
        return out

    def _draw_inertial_approx(self, ax, aid: str, state, color: str, *, plane) -> None:
        """会合系数据旋转到惯性系 km 的近似视图（历元对齐取 θ(t=0)=0）。

        用于无 position_km 的纯 CR3BP 产物（轨道族/旧初猜）：r_gcrs =
        R(θ)·(r_syn + (μ,0,0))·DU。moon 中心时再减月球解析位置 R(θ)·(1,0,0)·DU。
        """
        from src.engine.viz_adapter import approx_moon_gcrs_km, synodic_to_gcrs_km

        mu = self._mu_by_id.get(aid)
        if mu is None:
            return
        moon_center = state.center == "moon"

        def _shift(pos3: Any, th: Any) -> Any:
            out = synodic_to_gcrs_km(pos3, th, mu)
            if moon_center:
                out = out - approx_moon_gcrs_km(th)
            return out

        family = self._family_by_id.get(aid)
        family_times = self._family_times_by_id.get(aid)
        if family is not None and family_times is not None:
            import matplotlib.colors as mcolors

            arr = np.asarray(family)
            t = np.asarray(family_times)
            m = arr.shape[0]
            norm = mcolors.Normalize(vmin=0.0, vmax=max(m - 1, 1))
            cmap = matplotlib.colormaps["viridis"]
            label = self._labels_by_id.get(aid, "")
            for j in range(m):
                pos = _shift(arr[j][:, :3], t[j])
                if plane is None:
                    ax.plot(
                        pos[:, 0],
                        pos[:, 1],
                        pos[:, 2],
                        linewidth=self._chart.orbit_linewidth,
                        color=cmap(norm(j)),
                        gid=_ORBIT_GID,
                        label=label if j == 0 else None,
                    )
                else:
                    ax.plot(
                        pos[:, plane[0]],
                        pos[:, plane[1]],
                        linewidth=self._chart.orbit_linewidth,
                        color=cmap(norm(j)),
                        gid=_ORBIT_GID,
                        label=label if j == 0 else None,
                    )
            return
        initial = self._initial_guess_by_id.get(aid)
        initial_times = self._initial_guess_times_by_id.get(aid)
        if initial is not None and initial_times is not None:
            pos = _shift(np.asarray(initial)[:, :3], np.asarray(initial_times))
            label = self._labels_by_id.get(aid, "")
            if plane is None:
                ax.plot(
                    pos[:, 0],
                    pos[:, 1],
                    pos[:, 2],
                    linewidth=self._chart.orbit_linewidth,
                    color=color,
                    gid=_ORBIT_GID,
                    label=label,
                )
            else:
                ax.plot(
                    pos[:, plane[0]],
                    pos[:, plane[1]],
                    linewidth=self._chart.orbit_linewidth,
                    color=color,
                    gid=_ORBIT_GID,
                    label=label,
                )

    def _draw_inertial_bodies(self, ax, state, moon_shift) -> None:
        """惯性系天体标注：地球/月球 marker + 月球（或月球中心的地球）轨迹。

        ``moon_shift`` 来自 ``_inertial_moon_positions``；月球位置不可用时
        （SPICE 失败/无时间轴）不画依赖它的标注，避免坐标系错位。
        """
        from src.engine.viz_adapter import draw_earth_origin_marker

        is_3d = state.projection == "3d"
        plane = None if is_3d else _PROJECTION_PLANE_AXES[state.projection]
        chart = self._chart
        moon_available = any(v is not None for v in moon_shift.values())
        if state.center == "moon":
            # 月球中心视图：月球 marker 在原点（仅当月球位置可用，否则无坐标基准）
            if moon_available:
                if is_3d:
                    ax.plot(
                        [0],
                        [0],
                        [0],
                        "o",
                        color="#95A5A6",
                        markersize=chart.moon_size**0.5,
                        markeredgecolor="black",
                        markeredgewidth=0.8,
                        label="Moon",
                    )
                else:
                    ax.scatter(
                        0,
                        0,
                        color="#95A5A6",
                        s=chart.moon_size,
                        edgecolors="#566573",
                        linewidth=1.2,
                        zorder=10,
                    )
                    ax.annotate(
                        "Moon",
                        (0, 0),
                        xytext=(6, 6),
                        textcoords="offset points",
                        fontsize=chart.label_fontsize,
                    )
        else:
            draw_earth_origin_marker(
                ax,
                is_3d=is_3d,
                plane=plane,
                earth_size=chart.earth_size,
                fontsize=chart.label_fontsize,
            )
        # 月球（或月球中心的地球）轨迹：用任一可见 Artifact 的月球位置
        for aid in state.visible_artifacts:
            moon = moon_shift.get(aid)
            if moon is None:
                continue
            # 时间轴（ADR 0014）：地心视图下月球此刻位置 marker 随 t 移动；
            # SPICE 不可用时 moon 为 None 已在上游跳过，不另降级
            if state.current_et is not None and state.center != "moon":
                times = self._ephemeris_times_et_by_id.get(aid)
                here = (
                    self._position_at(times, moon, state.current_et) if times is not None else None
                )
                if here is not None:
                    if is_3d:
                        ax.plot(
                            [here[0]],
                            [here[1]],
                            [here[2]],
                            "o",
                            color="#95A5A6",
                            markersize=chart.moon_size**0.5 * 0.6,
                            markeredgecolor="black",
                            markeredgewidth=0.8,
                            zorder=6,
                            gid=_MARKER_GID,
                            label="月球（此刻）",
                        )
                    else:
                        assert plane is not None
                        ax.scatter(
                            here[plane[0]],
                            here[plane[1]],
                            s=chart.moon_size * 0.6,
                            c="#95A5A6",
                            edgecolors="#566573",
                            linewidths=0.8,
                            zorder=6,
                            gid=_MARKER_GID,
                            label="月球（此刻）",
                        )
            if state.center == "moon":
                # 月球中心：地球相对月球 = -moon_pos(t)，深蓝虚线轨迹
                earth = -moon
                if is_3d:
                    ax.plot(
                        earth[:, 0],
                        earth[:, 1],
                        earth[:, 2],
                        linewidth=chart.orbit_linewidth,
                        color="#2E86AB",
                        linestyle="--",
                        label="Earth",
                    )
                else:
                    assert plane is not None
                    ax.plot(
                        earth[:, plane[0]],
                        earth[:, plane[1]],
                        linewidth=chart.orbit_linewidth,
                        color="#2E86AB",
                        linestyle="--",
                        label="Earth",
                    )
            else:
                # 地球中心：月球轨迹灰色虚线
                if is_3d:
                    ax.plot(
                        moon[:, 0],
                        moon[:, 1],
                        moon[:, 2],
                        linewidth=chart.orbit_linewidth,
                        color="gray",
                        linestyle="--",
                        label="Moon",
                    )
                else:
                    assert plane is not None
                    ax.plot(
                        moon[:, plane[0]],
                        moon[:, plane[1]],
                        linewidth=chart.orbit_linewidth,
                        color="gray",
                        linestyle="--",
                        label="Moon",
                    )
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
        ax.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=self._chart.orbit_linewidth, label=label)

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
            ax.legend(loc="upper left", fontsize=max(self._chart.label_fontsize - 1, 6))

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
            ax.plot(
                pos[:, 0],
                pos[:, 1],
                pos[:, 2],
                linewidth=self._chart.orbit_linewidth,
                label=orb_label,
            )

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        if label:
            ax.set_title(label)

        if orbits_data:
            ax.legend(loc="upper left", fontsize=max(self._chart.label_fontsize - 1, 6), ncol=2)

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
            color = self._orbit_color(i)
            pos = states[:, :3]
            ax.plot(
                pos[:, 0],
                pos[:, 1],
                pos[:, 2],
                linewidth=self._chart.orbit_linewidth,
                color=color,
                label=label,
            )
            ax.scatter(*pos[0], s=30, c=color, zorder=5)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.set_title(f"叠加显示 ({len(orbits)} 条轨道)")

        if orbits:
            ax.legend(loc="upper left", fontsize=max(self._chart.label_fontsize - 1, 6))
        self._fig.tight_layout()
        self.draw()


class OrbitCanvasWithToolbar:
    """画布 + 导航工具栏 + 投影/标注工具栏的组合控件。"""

    def __init__(self, parent=None):
        from PyQt6.QtCore import QSize
        from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

        from src.view.canvas_toolbar import CanvasToolbar

        self.widget = QWidget(parent)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.canvas = OrbitCanvas(self.widget)
        # FigureCanvas 默认 Preferred 策略（停在 sizeHint 800x600），显式
        # Expanding 才能随面板拉伸填满——固定尺寸居中会在大窗口四周留白
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar = NavigationToolbar2QT(self.canvas, self.widget)
        # 默认 24x24 图标偏大，收紧到 16x16 与紧凑按钮密度一致
        self.toolbar.setIconSize(QSize(16, 16))
        self.projection_toolbar = CanvasToolbar(self.widget)
        from src.view.timeline_bar import TimelineBar

        self.timeline = TimelineBar(self.widget)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.projection_toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.timeline)

    def plot_orbit(self, **kwargs) -> None:
        self.canvas.plot_orbit(**kwargs)

    def plot_family(self, **kwargs) -> None:
        self.canvas.plot_family(**kwargs)

    def plot_multiple(self, **kwargs) -> None:
        self.canvas.plot_multiple(**kwargs)

    def clear(self) -> None:
        self.canvas.clear()
