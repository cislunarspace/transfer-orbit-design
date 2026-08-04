"""主窗口 -- 三栏 Splitter 布局。

组装 project_tree + canvas + params + log，连接 signals/slots。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.engine.facade_bridge import OrbitDesignResultData
from src.engine.workers import OrbitDesignWorker
from src.model import Artifact, Project
from src.view.canvas import OrbitCanvasWithToolbar
from src.view.log_panel import LogPanel


class MainWindow(QMainWindow):
    """生产版主窗口。

    布局：
        左侧 (20%): 项目树 (QTreeWidget)
        中间 (55%): 可视化画布 + 日志标签页
        右侧 (25%): design_orbit 参数面板 + 运行按钮
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._project = Project(name="Transfer Orbit Design")
        self._worker: OrbitDesignWorker | None = None
        self._param_widgets: dict[str, QWidget] = {}

        self.setWindowTitle("Transfer Orbit Design v2")
        self.resize(1400, 900)

        self._build_ui()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

    # -- UI 构建 -----------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())

        splitter.setStretchFactor(0, 1)  # 左侧
        splitter.setStretchFactor(1, 3)  # 中间
        splitter.setStretchFactor(2, 1)  # 右侧

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("项目"))
        self._project_tree = QTreeWidget()
        self._project_tree.setHeaderLabels(["名称", "类型"])
        self._project_tree.itemClicked.connect(self._on_artifact_clicked)
        layout.addWidget(self._project_tree)

        return panel

    def _build_center_panel(self) -> QWidget:
        tabs = QTabWidget()

        # 可视化标签页
        self._viz = OrbitCanvasWithToolbar()
        tabs.addTab(self._viz.widget, "可视化")

        # 日志标签页
        self._log = LogPanel()
        tabs.addTab(self._log, "日志")

        self._center_tabs = tabs
        return tabs

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._build_design_orbit_params(layout)

        return panel

    # -- 参数面板 -----------------------------------------------------------

    def _build_design_orbit_params(self, layout: QVBoxLayout) -> None:
        # 轨道类型
        layout.addWidget(QLabel("轨道类型"))
        combo = QComboBox()
        combo.addItems(["DRO", "Halo", "NRHO", "Lissajous", "L4", "L5"])
        layout.addWidget(combo)
        self._param_widgets["orbit_type"] = combo

        # 振幅
        layout.addWidget(QLabel("振幅 (km)"))
        amp = QDoubleSpinBox()
        amp.setRange(1.0, 110000.0)
        amp.setValue(40000.0)
        amp.setSingleStep(1000.0)
        layout.addWidget(amp)
        self._param_widgets["amplitude"] = amp

        # 持续时间
        layout.addWidget(QLabel("持续时间 (年)"))
        dur = QDoubleSpinBox()
        dur.setRange(0.01, 20.0)
        dur.setValue(1.0)
        dur.setSingleStep(0.1)
        layout.addWidget(dur)
        self._param_widgets["duration"] = dur

        # 输出步长
        layout.addWidget(QLabel("输出步长 (秒)"))
        step = QDoubleSpinBox()
        step.setRange(1.0, 86400.0)
        step.setValue(3600.0)
        step.setSingleStep(60.0)
        layout.addWidget(step)
        self._param_widgets["output_step"] = step

        # SPICE 内核目录
        layout.addWidget(QLabel("SPICE 内核目录"))
        spice_edit = QLineEdit()
        spice_edit.setText(self._detect_kernel_dir())
        spice_edit.setPlaceholderText("留空使用 $SPICE_KERNEL_DIR")
        layout.addWidget(spice_edit)
        self._param_widgets["kernel_dir"] = spice_edit

        layout.addStretch()

        # 运行按钮
        run_btn = QPushButton("运行设计")
        run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        run_btn.clicked.connect(self._on_run_design)
        layout.addWidget(run_btn)

    @staticmethod
    def _detect_kernel_dir() -> str:
        """自动探测 SPICE 内核目录。

        优先级：$SPICE_KERNEL_DIR 环境变量 -> ../e2m2e/kernels/。
        """
        env_val = os.environ.get("SPICE_KERNEL_DIR", "")
        if env_val and Path(env_val).is_dir():
            return env_val

        # 从 worktree 根目录向上找 e2m2e/kernels/
        here = Path(__file__).resolve()
        # src/app/main_window.py -> 项目根是 here.parent.parent.parent
        repo_root = here.parent.parent.parent
        candidate = repo_root.parent / "e2m2e" / "kernels"
        if candidate.is_dir():
            return str(candidate)

        return ""

    # -- 信号槽 -------------------------------------------------------------

    def _on_artifact_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not artifact_id:
            return
        artifact = self._project.get_by_id(artifact_id)
        if artifact and artifact.state_data is not None:
            self._render_artifact(artifact)
            self._center_tabs.setCurrentIndex(0)

    def _on_run_design(self) -> None:
        orbit_type_widget: QComboBox = self._param_widgets["orbit_type"]  # type: ignore[assignment]
        orbit_type = orbit_type_widget.currentText()
        amplitude: float = self._param_widgets["amplitude"].value()  # type: ignore[union-attr]
        duration: float = self._param_widgets["duration"].value()  # type: ignore[union-attr]
        output_step: float = self._param_widgets["output_step"].value()  # type: ignore[union-attr]
        kernel_dir_text: str = self._param_widgets["kernel_dir"].text().strip()  # type: ignore[union-attr]
        kernel_dir = kernel_dir_text or None

        params: dict[str, Any] = {
            "amplitude": amplitude,
            "duration": duration,
            "output_step": output_step,
        }

        self._log.clear()
        self._log.append_log(f"开始 {orbit_type} 轨道设计")
        self._log.append_log(
            f"参数: amplitude={amplitude}, duration={duration}, output_step={output_step}"
        )
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
        self._log.append_log(msg)

    def _on_design_finished(self, result: OrbitDesignResultData) -> None:
        artifact = Artifact(
            artifact_type="orbit",
            label=f"{result.orbit_type} (C_J={result.cr3bp_jacobi:.4f})",
            orbit_type=result.orbit_type,
            source_tool="design_orbit",
            state_data=result.cr3bp_orbit.states if result.cr3bp_orbit else None,
            times=result.cr3bp_orbit.times if result.cr3bp_orbit else None,
            extra={
                "jacobi": result.cr3bp_jacobi,
                "epoch": result.epoch_utc,
                "converged": result.correction_converged,
                "iterations": result.correction_iterations,
            },
        )
        self._project.add(artifact)
        self._refresh_project_tree()

        if artifact.state_data is not None:
            self._render_artifact(artifact)

        self._log.append_log(f"设计完成: {result.orbit_type}, C_J={result.cr3bp_jacobi:.6f}")
        self._status_bar.showMessage(f"{result.orbit_type} 设计完成", 5000)

    def _on_design_error(self, error_msg: str) -> None:
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("设计失败", 5000)

    # -- 渲染 ---------------------------------------------------------------

    def _render_artifact(self, artifact: Artifact) -> None:
        if artifact.state_data is None:
            return
        self._viz.plot_orbit(
            states=artifact.state_data,
            label=artifact.label,
            orbit_type=artifact.orbit_type,
        )

    # -- 项目树 -------------------------------------------------------------

    def _refresh_project_tree(self) -> None:
        self._project_tree.clear()

        type_groups: dict[str, list[Artifact]] = {}
        for a in self._project.artifacts:
            type_groups.setdefault(a.artifact_type, []).append(a)

        type_labels = {
            "orbit": "轨道",
            "family": "轨道族",
            "transfer": "转移",
            "ephemeris": "星历",
        }

        for atype, items in type_groups.items():
            group = QTreeWidgetItem(self._project_tree, [type_labels.get(atype, atype)])
            group.setExpanded(True)
            for artifact in items:
                child = QTreeWidgetItem(group, [artifact.label, artifact.orbit_type])
                child.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)
