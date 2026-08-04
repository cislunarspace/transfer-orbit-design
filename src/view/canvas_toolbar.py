"""画布工具栏 -- 投影切换 + 地月/L 点开关（architecture.md:49 规划）。

纯 UI 控件，不含业务逻辑。信号由 main_window 连接，统一更新 CanvasState
并触发 ``render()``。MVP 不做投影按钮状态互斥高亮（计划 3.5）。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget


class CanvasToolbar(QWidget):
    """投影切换按钮组 + show_bodies/show_libration 复选框。

    Attributes:
        projection_3d:  切换到 3D 视图。
        projection_xy:  切换到 XY 平面投影。
        projection_xz:  切换到 XZ 平面投影。
        projection_yz:  切换到 YZ 平面投影。
        show_bodies:    是否显示地球/月球标注。
        show_libration: 是否显示 L1-L5 拉格朗日点标注。
    """

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
