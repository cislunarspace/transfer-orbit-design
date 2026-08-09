"""画布工具栏 -- 投影/坐标系切换 + 地月/L 点开关（architecture.md:49 规划）。

纯 UI 控件，不含业务逻辑。信号由 main_window 连接，统一更新 CanvasState
并触发 ``render()``。MVP 不做投影按钮状态互斥高亮（计划 3.5）。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget


class CanvasToolbar(QWidget):
    """投影切换按钮组 + 坐标系切换按钮组 + 绘制内容按钮组 + 复选框。

    Attributes:
        projection_3d:  切换到 3D 视图。
        projection_xy:  切换到 XY 平面投影。
        projection_xz:  切换到 XZ 平面投影。
        projection_yz:  切换到 YZ 平面投影。
        frame_synodic:  切换到会合系（CR3BP 旋转系，无量纲）。
        frame_inertial: 切换到惯性系（GCRS/J2000，km）。
        plot_overlay:   绘制内容：叠加（初猜 + 星历，默认）。
        plot_guess:     绘制内容：仅 CR3BP 初猜。
        plot_ephemeris: 绘制内容：仅标称星历。
        show_bodies:    是否显示地球/月球标注。
        show_libration: 是否显示 L1-L5 拉格朗日点标注。
        export_animation: 弹出 GIF 导出对话框（P2，从选中的星历 Artifact 导出）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projection_3d = QPushButton("3D")
        self.projection_xy = QPushButton("XY")
        self.projection_xz = QPushButton("XZ")
        self.projection_yz = QPushButton("YZ")
        self.frame_synodic = QPushButton("会合系")
        self.frame_inertial = QPushButton("惯性系")
        self.plot_overlay = QPushButton("叠加")
        self.plot_guess = QPushButton("初猜")
        self.plot_ephemeris = QPushButton("星历")
        self.show_bodies = QCheckBox("地月")
        self.show_libration = QCheckBox("L1-L5")
        self.export_animation = QPushButton("导出动画")

        self.show_bodies.setChecked(True)
        self.show_libration.setChecked(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.projection_3d)
        layout.addWidget(self.projection_xy)
        layout.addWidget(self.projection_xz)
        layout.addWidget(self.projection_yz)
        layout.addSpacing(16)
        layout.addWidget(self.frame_synodic)
        layout.addWidget(self.frame_inertial)
        layout.addSpacing(16)
        layout.addWidget(self.plot_overlay)
        layout.addWidget(self.plot_guess)
        layout.addWidget(self.plot_ephemeris)
        layout.addSpacing(16)
        layout.addWidget(self.show_bodies)
        layout.addWidget(self.show_libration)
        layout.addStretch()
        layout.addWidget(self.export_animation)
