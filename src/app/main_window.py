"""主窗口 -- 三栏 Splitter 布局。

组装 project_tree + canvas + params + log，连接 signals/slots。
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.engine.facade_bridge import TOOL_REGISTRY, OrbitDesignResultData
from src.engine.workers import OrbitDesignWorker
from src.model import Artifact, Project
from src.view.canvas import OrbitCanvasWithToolbar
from src.view.log_panel import LogPanel
from src.view.params_panel import build_params_from_model, collect_params

_design_tool = TOOL_REGISTRY.get("design_orbit")
_DesignOrbitRequest = _design_tool.request_model if _design_tool else None


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
        if _DesignOrbitRequest is None:
            layout.addWidget(QLabel("e2m2e 未安装，参数面板不可用"))
            return

        self._param_widgets = build_params_from_model(_DesignOrbitRequest, parent=None)

        field_labels: dict[str, str] = {
            "orbit_type": "轨道类型",
            "amplitude": "振幅 (km)",
            "phase": "初始相位 (周期份额)",
            "collinear_point": "共线平动点",
            "north_south": "北/南 (1=北, 2=南)",
            "perilune_height": "近月点高度 (km)",
            "amplitude_in": "面内振幅 (km)",
            "amplitude_out": "面外振幅 (km)",
            "phase_in": "面内相位",
            "phase_out": "面外相位",
            "epoch": "历元",
            "duration": "持续时间 (年)",
            "output_step": "输出步长 (秒)",
            "correction_method": "修正方法",
        }
        for name, widget in self._param_widgets.items():
            layout.addWidget(QLabel(field_labels.get(name, name)))
            layout.addWidget(widget)

        layout.addStretch()

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

    def _on_artifact_clicked(self, artifact_id: str) -> None:
        artifact = self._project.get_by_id(artifact_id)
        if artifact and artifact.state_data is not None:
            self._render_artifact(artifact)
            self._center_tabs.setCurrentIndex(0)

    def _on_run_design(self) -> None:
        orbit_type_widget: QComboBox = self._param_widgets["orbit_type"]  # type: ignore[assignment]
        orbit_type = orbit_type_widget.currentText()

        params = collect_params(self._param_widgets, _DesignOrbitRequest)  # type: ignore[reportArgumentType]
        params.pop("orbit_type", None)  # orbit_type 单独传给 Worker

        kernel_dir = self._detect_kernel_dir() or None

        self._log.clear()
        self._log.append_log(f"开始 {orbit_type} 轨道设计")
        self._log.append_log(f"参数: {params}")
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
            state_data=result.states,
            times=result.times,
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
        self._tree_view.refresh(self._project)

    def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
        orbits: list[tuple] = []
        for aid in artifact_ids:
            artifact = self._project.get_by_id(aid)
            if artifact and artifact.state_data is not None:
                orbits.append((artifact.state_data, artifact.label))
        if orbits:
            self._viz.plot_multiple(orbits=orbits)
            self._center_tabs.setCurrentIndex(0)
