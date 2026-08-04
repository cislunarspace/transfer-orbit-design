"""新 GUI 主窗口 — 原型。

验证点：三栏布局（侧边栏 | 可视化+日志 | 参数面板）+ Project 数据模型 + Facade 直调。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tod.gui.prototype.embedded_canvas import OrbitCanvasWithToolbar
from tod.gui.prototype.facade_worker import OrbitDesignResultData, OrbitDesignWorker
from tod.gui.prototype.project_model import Artifact, Project


class PrototypeMainWindow(QMainWindow):
    """新架构原型主窗口。

    布局：
        左侧：项目树 + 可用工具列表
        中间：可视化画布 + 日志
        右侧：参数面板
    """

    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = repo_root
        self._project = Project(name="原型项目")
        self._worker: OrbitDesignWorker | None = None
        self._param_widgets: dict[str, QWidget] = {}

        self.setWindowTitle("e2m2e GUI 原型 — Transfer Orbit Design")
        self.resize(1400, 900)

        self._build_ui()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪 — 选择工具开始")

    # ── UI 构建 ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter = splitter

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())

        splitter.setStretchFactor(0, 1)  # 左侧
        splitter.setStretchFactor(1, 3)  # 中间（最宽）
        splitter.setStretchFactor(2, 1)  # 右侧

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # 项目树
        layout.addWidget(QLabel("📁 项目"))
        self._project_tree = QTreeWidget()
        self._project_tree.setHeaderLabels(["名称", "类型"])
        self._project_tree.itemClicked.connect(self._on_artifact_clicked)
        layout.addWidget(self._project_tree, stretch=2)

        # 工具列表
        layout.addWidget(QLabel("🔧 工具"))
        self._tools_list = QListWidget()
        self._tools_list.addItems([
            "轨道设计 (design_orbit)",
            "轨道族生成 (family_generation) — 占位",
            "转移搜索 (transfer_search) — 占位",
            "轨道保持 (control_orbit) — 占位",
        ])
        self._tools_list.currentRowChanged.connect(self._on_tool_selected)
        layout.addWidget(self._tools_list, stretch=1)

        return panel

    def _build_center_panel(self) -> QWidget:
        tabs = QTabWidget()

        # 可视化标签页
        self._viz = OrbitCanvasWithToolbar()
        tabs.addTab(self._viz.widget, "📊 可视化")

        # 日志标签页
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        tabs.addTab(self._log, "📋 日志")

        self._center_tabs = tabs
        return tabs

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        self._right_layout = QVBoxLayout(panel)
        self._right_layout.setContentsMargins(4, 4, 4, 4)
        self._right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._params_container = QWidget()
        self._params_layout = QVBoxLayout(self._params_container)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.addWidget(self._params_container)

        # 占位提示
        self._placeholder_label = QLabel("← 选择一个工具以显示参数")
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet("color: gray; font-size: 14px;")
        self._right_layout.addWidget(self._placeholder_label)

        return panel

    # ── 参数面板 ─────────────────────────────────────────────

    def _clear_params_panel(self) -> None:
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._param_widgets.clear()

    def _build_design_orbit_params(self) -> None:

        # 轨道类型
        self._params_layout.addWidget(QLabel("轨道类型"))
        combo = QComboBox()
        combo.addItems(["DRO", "Halo", "NRHO", "Lissajous", "L4", "L5"])
        self._params_layout.addWidget(combo)
        self._param_widgets["orbit_type"] = combo

        # 振幅
        self._params_layout.addWidget(QLabel("振幅 (km)"))
        amp = QDoubleSpinBox()
        amp.setRange(1.0, 110000.0)
        amp.setValue(40000.0)
        amp.setSingleStep(1000.0)
        self._params_layout.addWidget(amp)
        self._param_widgets["amplitude"] = amp

        # 持续时间
        self._params_layout.addWidget(QLabel("持续时间 (年)"))
        dur = QDoubleSpinBox()
        dur.setRange(0.01, 20.0)
        dur.setValue(1.0)
        dur.setSingleStep(0.1)
        self._params_layout.addWidget(dur)
        self._param_widgets["duration"] = dur

        # 输出步长
        self._params_layout.addWidget(QLabel("输出步长 (秒)"))
        step = QDoubleSpinBox()
        step.setRange(1.0, 86400.0)
        step.setValue(3600.0)
        step.setSingleStep(60.0)
        self._params_layout.addWidget(step)
        self._param_widgets["output_step"] = step

        # SPICE 内核目录
        self._params_layout.addWidget(QLabel("SPICE 内核目录"))
        spice_edit = QLineEdit()
        # 自动探测 e2m2e/kernels/ 或环境变量
        import os
        default_spice = os.environ.get("SPICE_KERNEL_DIR", "")
        if not default_spice:
            candidate = Path(self._repo_root).parent / "e2m2e" / "kernels"
            if candidate.is_dir():
                default_spice = str(candidate)
        spice_edit.setText(default_spice)
        spice_edit.setPlaceholderText("留空使用 $SPICE_KERNEL_DIR")
        self._params_layout.addWidget(spice_edit)
        self._param_widgets["kernel_dir"] = spice_edit

        self._params_layout.addStretch()

        # 运行按钮
        run_btn = QPushButton("▶ 运行设计")
        run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        run_btn.clicked.connect(self._on_run_design)
        self._params_layout.addWidget(run_btn)

    # ── 信号槽 ───────────────────────────────────────────────

    def _on_tool_selected(self, row: int) -> None:
        self._placeholder_label.hide()
        self._clear_params_panel()

        if row == 0:
            self._build_design_orbit_params()
        else:
            label = QLabel("此工具在原型中尚未实现")
            label.setStyleSheet("color: orange; font-style: italic;")
            self._params_layout.addWidget(label)

    def _on_artifact_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not artifact_id:
            return
        artifact = self._project.get_by_id(artifact_id)
        if artifact and artifact.state_data is not None:
            self._render_artifact(artifact)
            self._center_tabs.setCurrentIndex(0)  # 切到可视化

    def _on_run_design(self) -> None:
        orbit_type = self._param_widgets["orbit_type"].currentText()
        amplitude = self._param_widgets["amplitude"].value()
        duration = self._param_widgets["duration"].value()
        output_step = self._param_widgets["output_step"].value()
        kernel_dir = self._param_widgets["kernel_dir"].text().strip() or None

        params: dict[str, Any] = {
            "amplitude": amplitude,
            "duration": duration,
            "output_step": output_step,
        }

        self._log.clear()
        self._log.appendPlainText(f"=== 开始 {orbit_type} 轨道设计 ===")
        self._status_bar.showMessage(f"正在设计 {orbit_type}...")

        self._worker = OrbitDesignWorker(
            orbit_type=orbit_type,
            params=params,
            kernel_dir=kernel_dir,
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_design_finished)
        self._worker.error.connect(self._on_design_error)
        self._worker.start()

    def _on_worker_log(self, msg: str) -> None:
        self._log.appendPlainText(msg)

    def _on_design_finished(self, result: OrbitDesignResultData) -> None:
        # 注册到项目
        artifact = Artifact(
            artifact_type="orbit",
            label=f"{result.orbit_type} (C_J={result.cr3bp_jacobi:.4f})",
            orbit_type=result.orbit_type,
            state_data=result.cr3bp_orbit.states if result.cr3bp_orbit else None,
            times=result.cr3bp_orbit.times if result.cr3bp_orbit else None,
            extra={
                "jacobi": result.cr3bp_jacobi,
                "epoch": result.epoch_utc,
                "converged": result.correction_converged,
                "iterations": result.correction_iterations,
            },
        )
        self._project.add_artifact(artifact)
        self._refresh_project_tree()

        # 自动渲染
        if artifact.state_data is not None:
            self._render_artifact(artifact)

        self._status_bar.showMessage(
            f"✓ {result.orbit_type} 设计完成，已注册到项目", 5000
        )

    def _on_design_error(self, error_msg: str) -> None:
        self._log.appendPlainText(f"\n=== 错误 ===\n{error_msg}")
        self._status_bar.showMessage("设计失败", 5000)

    # ── 渲染 ─────────────────────────────────────────────────

    def _render_artifact(self, artifact: Artifact) -> None:
        if artifact.state_data is None:
            return
        self._viz.plot_orbit(
            states=artifact.state_data,
            label=artifact.label,
            orbit_type=artifact.orbit_type,
        )

    # ── 项目树 ───────────────────────────────────────────────

    def _refresh_project_tree(self) -> None:
        self._project_tree.clear()

        # 按类型分组
        type_groups: dict[str, list[Artifact]] = {}
        for a in self._project.artifacts:
            type_groups.setdefault(a.artifact_type, []).append(a)

        type_labels = {
            "orbit": "🪐 轨道",
            "family": "🌀 轨道族",
            "transfer": "🚀 转移",
            "ephemeris": "📡 星历",
        }

        for atype, items in type_groups.items():
            group = QTreeWidgetItem(self._project_tree, [type_labels.get(atype, atype)])
            group.setExpanded(True)
            for artifact in items:
                child = QTreeWidgetItem(group, [artifact.label, artifact.orbit_type])
                child.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)

    def _append_log(self, text: str) -> None:
        self._log.appendPlainText(text)
