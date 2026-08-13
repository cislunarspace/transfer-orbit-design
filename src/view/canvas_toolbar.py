"""画布工具栏 -- 投影/坐标系切换 + 地月/L 点开关（architecture.md:49 规划）。

纯 UI 控件，不含业务逻辑。信号由 main_window 连接，统一更新 CanvasState
并触发 ``render()``。MVP 不做投影按钮状态互斥高亮（计划 3.5）。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QButtonGroup, QCheckBox, QGridLayout, QPushButton, QWidget


class CanvasToolbar(QWidget):
    """投影切换按钮组 + 坐标系切换按钮组 + 绘制内容按钮组 + 复选框。

    Attributes:
        projection_3d:  切换到 3D 视图。
        projection_xy:  切换到 XY 平面投影。
        projection_xz:  切换到 XZ 平面投影。
        projection_yz:  切换到 YZ 平面投影。
        projection_quad: 四视图（2x2 网格：3D + XY/XZ/YZ，适合大窗口/全屏）。
        frame_synodic:  切换到会合系（CR3BP 旋转系，无量纲）。
        frame_inertial: 切换到惯性系（GCRS/J2000，km）。
        center_barycenter: 中心视图：质心（会合系）/ 地球原点（惯性系）。
        center_moon:  中心视图：月球。
        center_l1:    中心视图：L1 平动点（仅会合系）。
        center_l2:    中心视图：L2 平动点（仅会合系）。
        plot_overlay:   绘制内容：叠加（初猜 + 星历，默认）。
        plot_guess:     绘制内容：仅 CR3BP 初猜。
        plot_ephemeris: 绘制内容：仅标称星历。
        show_bodies:    是否显示地球/月球标注。
        show_libration: 是否显示 L1-L5 拉格朗日点标注。
        equal_aspect:   是否等比例显示（默认勾选；取消后各轴独立缩放填满）。
        export_animation: 弹出 GIF 导出对话框（P2，从选中的星历 Artifact 导出）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projection_3d = QPushButton("3D")
        self.projection_xy = QPushButton("XY")
        self.projection_xz = QPushButton("XZ")
        self.projection_yz = QPushButton("YZ")
        self.projection_quad = QPushButton("四视图")
        self.frame_synodic = QPushButton("会合系")
        self.frame_inertial = QPushButton("惯性系")
        self.center_barycenter = QPushButton("质心")
        self.center_moon = QPushButton("月球")
        self.center_l1 = QPushButton("L1")
        self.center_l2 = QPushButton("L2")
        self.plot_overlay = QPushButton("叠加")
        self.plot_guess = QPushButton("初猜")
        self.plot_ephemeris = QPushButton("星历")
        self.show_bodies = QCheckBox("地月")
        self.show_libration = QCheckBox("L1-L5")
        self.equal_aspect = QCheckBox("等比")
        self.export_animation = QPushButton("导出动画")

        self.show_bodies.setChecked(True)
        self.show_libration.setChecked(True)
        self.equal_aspect.setChecked(True)  # 默认等比例（与 CanvasState 默认一致）

        # 三组互斥按钮：投影 / 坐标系 / 绘制内容。checked 态高亮（此前无选中态，
        # 用户看不出当前生效的投影/坐标系/内容）。QButtonGroup 互斥保证同组唯一选中。
        self._projection_group = QButtonGroup(self)
        self._projection_group.setExclusive(True)
        self._frame_group = QButtonGroup(self)
        self._frame_group.setExclusive(True)
        self._center_group = QButtonGroup(self)
        self._center_group.setExclusive(True)
        self._content_group = QButtonGroup(self)
        self._content_group.setExclusive(True)

        for btn in (
            self.projection_3d,
            self.projection_xy,
            self.projection_xz,
            self.projection_yz,
            self.projection_quad,
        ):
            btn.setCheckable(True)
            self._projection_group.addButton(btn)
        for btn in (self.frame_synodic, self.frame_inertial):
            btn.setCheckable(True)
            self._frame_group.addButton(btn)
        for btn in (self.center_barycenter, self.center_moon, self.center_l1, self.center_l2):
            btn.setCheckable(True)
            self._center_group.addButton(btn)
        for btn in (self.plot_overlay, self.plot_guess, self.plot_ephemeris):
            btn.setCheckable(True)
            self._content_group.addButton(btn)

        # 默认选中与 CanvasState 默认一致（3d / synodic / overlay / barycenter）
        self.projection_3d.setChecked(True)
        self.frame_synodic.setChecked(True)
        self.plot_overlay.setChecked(True)
        self.center_barycenter.setChecked(True)

        # 工具项按功能分多行。此前所有控件排在一个 QHBoxLayout，累加后的
        # minimumSizeHint 超过窄屏可用宽度，窗口无法在最大化/全屏间正确切换。
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(3)

        for column, button in enumerate(
            (
                self.projection_3d,
                self.projection_xy,
                self.projection_xz,
                self.projection_yz,
                self.projection_quad,
            )
        ):
            layout.addWidget(button, 0, column)

        for column, button in enumerate(
            (
                self.frame_synodic,
                self.frame_inertial,
                self.center_barycenter,
                self.center_moon,
            )
        ):
            layout.addWidget(button, 1, column)
        layout.addWidget(self.center_l1, 2, 0)
        layout.addWidget(self.center_l2, 2, 1)

        for column, widget in enumerate(
            (
                self.plot_overlay,
                self.plot_guess,
                self.plot_ephemeris,
                self.show_bodies,
            )
        ):
            layout.addWidget(widget, 3, column)
        layout.addWidget(self.show_libration, 4, 0)
        layout.addWidget(self.equal_aspect, 4, 1)
        layout.addWidget(self.export_animation, 4, 2)

        # 选中态：灰色加深（低调不突兀，仍能看出当前生效项）
        self.setStyleSheet("QPushButton:checked {  background-color: #b0b0b0;}")
