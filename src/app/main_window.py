"""主窗口 -- 三栏 Splitter 布局。

组装 project_tree + canvas + params + log，连接 signals/slots。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.commons.paths import OUTPUT_DIR, detect_kernel_dir
from src.engine.facade_bridge import (
    TOOL_REGISTRY,
    ControlResultData,
    OrbitDesignResultData,
    ToolSpec,
)
from src.engine.persistence import load_artifact_arrays, save_artifact, save_control_result
from src.engine.workers import ControlOrbitWorker, OrbitDesignWorker
from src.model import Artifact, Project
from src.model.discovery import discover_artifacts
from src.view.canvas import OrbitCanvasWithToolbar
from src.view.log_panel import LogPanel
from src.view.params_panel import (
    ORBIT_TYPE_FIELDS,
    apply_orbit_type_defaults,
    build_params_from_model,
    collect_params,
    get_field_units,
    set_spinbox_unit,
)

# G4+G5: 工具选择器 + 灰色占位

_RIGHT_PANEL_TOOL_COMBO_LABEL = "选择工具"

# 状态栏消息自动消失时长（毫秒）
_STATUS_MSG_TIMEOUT_MS = 5000


def _get_default_tool_key() -> str | None:
    """返回第一个 enabled 工具的 key，若无则 None。"""
    for key, spec in TOOL_REGISTRY.items():
        if spec.enabled:
            return key
    return None


# G4+G5: 字段标签（_FIELD_LABELS 已提取为模块级常量）

_DESIGN_ORBIT_LABELS: dict[str, str] = {
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
    "epoch": "历元 (年/月/日 时:分:秒)",
    "duration": "持续时间 (年)",
    "output_step": "输出步长 (秒)",
    "correction_method": "修正方法",
}

#: design_orbit 所有分支字段的并集（不在其中的字段视为通用字段，始终显示）
_ORBIT_TYPE_ALL_BRANCH_FIELDS: set[str] = set().union(*ORBIT_TYPE_FIELDS.values())


def _base_field_label(name: str) -> str:
    """剥离 _DESIGN_ORBIT_LABELS 里的标准单位后缀，得到基础标签。"""
    options = get_field_units(name)
    if not options:
        return _DESIGN_ORBIT_LABELS.get(name, name)
    suffix = f" ({options[0].label})"
    label = _DESIGN_ORBIT_LABELS.get(name, name)
    return label[: -len(suffix)] if label.endswith(suffix) else label


def _field_label_with_unit(name: str, unit: str) -> str:
    return f"{_base_field_label(name)} ({unit})"


class MainWindow(QMainWindow):
    """生产版主窗口。

    布局：
        左侧 (20%): 项目树 (QTreeWidget)
        中间 (55%): 可视化画布 + 日志标签页
        右侧 (25%): 工具选择器 + 参数面板 + 运行按钮
    """

    def __init__(self, parent=None, *, project: Project | None = None) -> None:
        super().__init__(parent)
        self._project = project if project is not None else Project(name="Transfer Orbit Design")
        self._worker: OrbitDesignWorker | ControlOrbitWorker | None = None
        self._current_tool_key: str | None = None
        self._param_widgets: dict[str, QWidget] = {}
        self._param_rows: dict[str, tuple[QLabel, QWidget, QComboBox | None]] = {}
        self._param_container: QWidget | None = None
        self._param_container_layout: QVBoxLayout | None = None
        self._run_btn = QPushButton("运行")  # G1: 非 Optional，_build_right_panel 中配置

        # Issue #339: 画布渲染状态（CanvasState）与当前选中 Artifact 集合
        from src.view.canvas import CanvasState

        self._canvas_state = CanvasState()
        self._selected_artifact_ids: list[str] = []

        self.setWindowTitle("Transfer Orbit Design v2")
        self.resize(1400, 900)

        self._build_ui()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

        # Issue #338: 启动时从 OUTPUT_DIR 恢复已有 Artifact
        # PR #345: 也允许 caller 传入预先填充的 Project（避免重复扫描）
        if not self._project.artifacts:
            self._restore_artifacts_from_disk()
        else:
            self._refresh_project_tree()

    def _restore_artifacts_from_disk(self) -> None:
        """扫描 OUTPUT_DIR 并将历史 Artifact 加入 Project。"""
        try:
            artifacts = discover_artifacts(OUTPUT_DIR)
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"恢复历史 Artifact 失败: {exc}")
            return
        if not artifacts:
            return
        for artifact in artifacts:
            self._project.add(artifact)
        self._refresh_project_tree()
        self._status_bar.showMessage(
            f"已恢复 {len(artifacts)} 个历史 Artifact", _STATUS_MSG_TIMEOUT_MS
        )

    # -- UI 构建 -----------------------------------------------------------

    def show_scan_time(self, seconds: float, count: int) -> None:
        """Display artifact scan timing in the status bar."""
        self._status_bar.showMessage(f"启动扫描: {count} 个 Artifact, 耗时 {seconds:.2f}s")

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
        self._tree_view.context_action.connect(self._on_context_action)
        layout.addWidget(self._tree_view)

        return panel

    def _build_center_panel(self) -> QWidget:
        tabs = QTabWidget()

        # 可视化标签页
        self._viz = OrbitCanvasWithToolbar()
        # Issue #339: 注入数据回调 -- main_window 提供 state_data / label / mu 查询，
        # canvas 不自持 Project（view 只经接口与数据层交互）。
        self._viz.canvas.set_artifacts_provider(self._artifact_for_id)
        tabs.addTab(self._viz.widget, "可视化")

        # Issue #339: 投影切换 + 地月/L 点开关（纯 UI，业务逻辑在此 slot 中）
        toolbar = self._viz.projection_toolbar
        toolbar.projection_3d.clicked.connect(lambda: self._on_projection_changed("3d"))
        toolbar.projection_xy.clicked.connect(lambda: self._on_projection_changed("xy"))
        toolbar.projection_xz.clicked.connect(lambda: self._on_projection_changed("xz"))
        toolbar.projection_yz.clicked.connect(lambda: self._on_projection_changed("yz"))
        toolbar.frame_synodic.clicked.connect(lambda: self._on_frame_changed("synodic"))
        toolbar.frame_inertial.clicked.connect(lambda: self._on_frame_changed("inertial"))
        toolbar.show_bodies.toggled.connect(self._on_toggle_bodies)
        toolbar.show_libration.toggled.connect(self._on_toggle_libration)
        toolbar.export_animation.clicked.connect(self._on_export_animation)

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

        # G4: 工具选择器
        layout.addWidget(QLabel(_RIGHT_PANEL_TOOL_COMBO_LABEL))
        self._tool_combo = QComboBox()
        for key, spec in TOOL_REGISTRY.items():
            idx = self._tool_combo.count()
            self._tool_combo.addItem(spec.label, key)
            if not spec.enabled:
                model = self._tool_combo.model()
                assert isinstance(model, QStandardItemModel)
                item = model.item(idx)
                if item is not None:
                    item.setEnabled(False)
                    item.setToolTip("即将提供")
        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        layout.addWidget(self._tool_combo)

        # 参数容器
        self._param_container = QWidget()
        self._param_container_layout = QVBoxLayout(self._param_container)
        self._param_container_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._param_container)

        layout.addStretch()

        # G1: 配置运行按钮（已在 __init__ 中创建）
        self._run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(self._run_btn)

        # 默认选中第一个 enabled 工具
        default_key = _get_default_tool_key()
        if default_key is not None:
            for i in range(self._tool_combo.count()):
                if self._tool_combo.itemData(i) == default_key:
                    self._tool_combo.setCurrentIndex(i)
                    break
        self._on_tool_changed(self._tool_combo.currentIndex())

        return panel

    # -- 参数面板（G4+G5 通用化）------------------------------------------

    def _on_tool_changed(self, index: int) -> None:
        """切换工具时动态清空并重建参数面板。"""
        if index < 0:
            return
        tool_key: str | None = self._tool_combo.itemData(index)
        if tool_key is None or tool_key == self._current_tool_key:
            return
        self._current_tool_key = tool_key
        self._build_tool_params(tool_key)

    def _build_tool_params(self, tool_key: str) -> None:
        """为指定工具构建参数面板。"""
        spec: ToolSpec | None = TOOL_REGISTRY.get(tool_key)
        if spec is None or spec.request_model is None:
            return

        # 清空旧控件
        self._param_widgets = {}
        self._param_rows = {}
        layout = self._param_container_layout
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w:
                w.setParent(None)

        # 生成控件
        self._param_widgets = build_params_from_model(spec.request_model)

        # G3: orbit_type -> QComboBox（若字段存在且有 description）
        if "orbit_type" in self._param_widgets:
            self._replace_orbit_type_with_combo(spec.request_model)

        # 显示字段（记录 label + widget + 单位下拉 行，供按轨道类型显示/隐藏）
        for name, widget in self._param_widgets.items():
            options = get_field_units(name)
            label_text = (
                _field_label_with_unit(name, options[0].label)
                if options
                else _DESIGN_ORBIT_LABELS.get(name, name)
            )
            label_widget = QLabel(label_text)
            layout.addWidget(label_widget)
            layout.addWidget(widget)
            unit_combo: QComboBox | None = None
            if options:
                unit_combo = QComboBox()
                for opt in options:
                    unit_combo.addItem(opt.label)
                unit_combo.setCurrentIndex(0)
                unit_combo.currentIndexChanged.connect(
                    lambda _idx, n=name: self._on_unit_combo_changed(n)
                )
                layout.addWidget(unit_combo)
            self._param_rows[name] = (label_widget, widget, unit_combo)

        # control_orbit 的 input_ephemeris 由选中 Artifact 注入，不在 UI 暴露
        if tool_key == "control_orbit" and "input_ephemeris" in self._param_widgets:
            old = self._param_widgets.pop("input_ephemeris")
            self._remove_widget_and_label(old)

        # design_orbit：按 orbit_type 分支填默认值 + 只显示相关字段
        if tool_key == "design_orbit":
            orbit_type_widget = self._param_widgets.get("orbit_type")
            if isinstance(orbit_type_widget, QComboBox):
                orbit_type_widget.currentIndexChanged.connect(self._on_orbit_type_changed)
                self._on_orbit_type_changed(orbit_type_widget.currentIndex())
            # duration GUI 默认下调至 1 个月（issue #355）：模型 default=1.0 年不动，
            # 仅在 GUI 层把单位切到"月"、值设为 1，让短弧设计更顺手。
            self._apply_duration_default_month()

        layout.addStretch()

    def _remove_widget_and_label(self, widget: QWidget) -> None:
        """从参数容器布局移除指定控件的整行（label + widget + 单位下拉）。"""
        # 同步 _param_rows
        for name, (label, w, unit_combo) in list(self._param_rows.items()):
            if w is widget:
                del self._param_rows[name]
                label.setParent(None)
                widget.setParent(None)
                if unit_combo is not None:
                    unit_combo.setParent(None)
                return
        widget.setParent(None)

    def _replace_orbit_type_with_combo(self, model_class: type) -> None:
        """G3: 若 orbit_type 字段 description 含 '/'，替换为 QComboBox。"""
        field = model_class.model_fields.get("orbit_type")
        if field is None or not field.description:
            return
        if "/" not in field.description:
            return

        options = [opt.strip() for opt in field.description.split("/") if opt.strip()]
        if not options:
            return

        combo = QComboBox()
        combo.addItems(options)
        combo.setToolTip(field.description)
        if field.default is not None and str(field.default) in options:
            combo.setCurrentIndex(options.index(str(field.default)))

        # 替换 _param_widgets 中的条目
        old = self._param_widgets.get("orbit_type")
        self._param_widgets["orbit_type"] = combo
        if old is not None:
            old.setParent(None)

    def _on_orbit_type_changed(self, index: int) -> None:
        """切轨道类型：填该分支默认值 + 只显示分支相关字段。"""
        if self._current_tool_key != "design_orbit":
            return
        orbit_type_widget = self._param_widgets.get("orbit_type")
        if not isinstance(orbit_type_widget, QComboBox):
            return
        orbit_type = orbit_type_widget.currentText()
        model = TOOL_REGISTRY["design_orbit"].request_model
        if model is None:
            return
        apply_orbit_type_defaults(self._param_widgets, orbit_type)
        self._sync_visible_fields(orbit_type)

    def _sync_visible_fields(self, orbit_type: str) -> None:
        """按分支字段集显示/隐藏参数行，并把解包后的控件同步进布局。"""
        branch_fields = ORBIT_TYPE_FIELDS.get(orbit_type, set())
        for name in list(self._param_rows):
            label, widget, unit_combo = self._param_rows[name]
            current = self._param_widgets.get(name)
            if current is not None and current is not widget:
                self._replace_row_widget(name, current)
                label, widget, unit_combo = self._param_rows[name]
            visible = name in branch_fields or name not in _ORBIT_TYPE_ALL_BRANCH_FIELDS
            label.setVisible(visible)
            widget.setVisible(visible)
            if unit_combo is not None:
                unit_combo.setVisible(visible)

    def _replace_row_widget(self, name: str, new_widget: QWidget) -> None:
        """把参数面板布局中 name 行的控件替换为 new_widget（apply 解包后同步布局）。"""
        row = self._param_rows.get(name)
        if row is None:
            return
        label, old_widget, unit_combo = row
        layout = self._param_container_layout
        if layout is None:
            old_widget.setParent(None)
            self._param_rows[name] = (label, new_widget, unit_combo)
            return
        layout.replaceWidget(old_widget, new_widget)
        old_widget.setParent(None)
        self._param_rows[name] = (label, new_widget, unit_combo)

    def _on_unit_combo_changed(self, field_name: str) -> None:
        """单位下拉切换：换算控件显示值 + 更新 label 后缀。"""
        row = self._param_rows.get(field_name)
        if row is None:
            return
        label, widget, unit_combo = row
        if unit_combo is None:
            return
        unit = unit_combo.currentText()
        # widget 可能是 Optional 容器（未 apply 前）或解包后的 spinbox
        sb = widget if isinstance(widget, QDoubleSpinBox) else widget.findChild(QDoubleSpinBox)
        if sb is None:
            return
        set_spinbox_unit(sb, field_name, unit)
        label.setText(_field_label_with_unit(field_name, unit))

    def _apply_duration_default_month(self) -> None:
        """把 duration 控件单位切到"月"并设为 1（= 1/12 年标准值）。

        模型 ``DesignOrbitRequest.duration`` 的 default=1.0（年）是上游契约，不改；
        此处仅在 GUI 层覆盖显示，让短弧设计更顺手。duration 不在
        ``ORBIT_TYPE_DEFAULTS``，切轨道类型不会重置该覆盖。
        """
        row = self._param_rows.get("duration")
        if row is None:
            return
        _label, widget, unit_combo = row
        sb = widget if isinstance(widget, QDoubleSpinBox) else widget.findChild(QDoubleSpinBox)
        if unit_combo is None or sb is None:
            return
        idx = unit_combo.findText("月")
        if idx < 0:
            return
        # 切单位触发 _on_unit_combo_changed：换算值（1 年 -> 12 月）+ 更新 label 后缀
        unit_combo.setCurrentIndex(idx)
        sb.setValue(1.0)  # 1 个月（= 1/12 年标准值）

    # -- 信号槽 -------------------------------------------------------------

    def _on_artifact_clicked(self, artifact_id: str) -> None:
        artifact = self._project.get_by_id(artifact_id)
        if artifact is None:
            return
        # Issue #338: 历史 Artifact 的 NPZ 数组懒加载（逻辑移至 persistence.load_artifact_arrays）
        if artifact.state_data is None and artifact.output_path is not None:
            loaded = load_artifact_arrays(artifact)
            if not loaded:
                self._log.append_log(f"NPZ 懒加载失败: {artifact.label}（文件缺失或元数据缺失）")
        if artifact.state_data is not None:
            self._warn_missing_mu(artifact)
            self._selected_artifact_ids = [artifact_id]
            self._render_canvas()
            self._center_tabs.setCurrentIndex(0)

    def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
        # Issue #339: 多选分支补上懒加载（现状缺失，见审查意见）
        for aid in artifact_ids:
            artifact = self._project.get_by_id(aid)
            if artifact is None:
                continue
            if artifact.state_data is None and artifact.output_path is not None:
                load_artifact_arrays(artifact)
            self._warn_missing_mu(artifact)
        self._selected_artifact_ids = list(artifact_ids)
        self._render_canvas()
        self._center_tabs.setCurrentIndex(0)

    def _on_run(self) -> None:
        tool_key = self._current_tool_key
        spec = TOOL_REGISTRY.get(tool_key) if tool_key else None
        if spec is None or not spec.enabled or spec.request_model is None:
            return
        if tool_key == "design_orbit":
            self._run_design_orbit()
        elif tool_key == "control_orbit":
            self._run_control_orbit()

    def _run_design_orbit(self) -> None:
        spec = TOOL_REGISTRY["design_orbit"]
        model = spec.request_model
        if model is None:
            return

        orbit_type = ""
        orbit_type_widget = self._param_widgets.get("orbit_type")
        if isinstance(orbit_type_widget, QComboBox):
            orbit_type = orbit_type_widget.currentText()

        try:
            params = collect_params(self._param_widgets, model)
        except ValueError as exc:
            self._status_bar.showMessage(str(exc), _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"参数错误: {exc}")
            return
        params.pop("orbit_type", None)

        kernel_dir = self._detect_kernel_dir() or None

        self._log.clear()
        self._log.append_log(f"开始 {orbit_type} 轨道设计")
        self._log.append_log(f"参数: {params}")
        self._status_bar.showMessage(f"正在设计 {orbit_type}...")

        # G1: 运行按钮状态管理
        self._run_btn.setEnabled(False)
        self._run_btn.setText("运行中...")

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

    def _run_control_orbit(self) -> None:
        source = self._selected_orbit_artifact()
        if source is None:
            self._status_bar.showMessage("请先选中一条轨道 Artifact", _STATUS_MSG_TIMEOUT_MS)
            return
        ephemeris_data = source.extra.get("ephemeris")
        if not ephemeris_data:
            self._status_bar.showMessage(
                "该 Artifact 无星历数据，需重新设计", _STATUS_MSG_TIMEOUT_MS
            )
            return

        spec = TOOL_REGISTRY["control_orbit"]
        model = spec.request_model
        if model is None:
            return
        params = collect_params(self._param_widgets, model)
        params.pop("input_ephemeris", None)  # 防御：理论上已隐藏

        kernel_dir = self._detect_kernel_dir() or None
        self._log.clear()
        self._log.append_log(f"轨道保持: 源 {source.label}")
        self._status_bar.showMessage("正在仿真轨道保持（蒙特卡洛）...")
        self._run_btn.setEnabled(False)
        self._run_btn.setText("运行中...")

        self._worker = ControlOrbitWorker(
            ephemeris_data=ephemeris_data,
            params=params,
            source_mu=source.extra.get("mu"),
            kernel_dir=kernel_dir,
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_control_finished)
        self._worker.error.connect(self._on_control_error)
        self._worker.start()

    def _selected_orbit_artifact(self) -> Artifact | None:
        """返回当前选中的单个 orbit 类型 Artifact，否则 None。"""
        if len(self._selected_artifact_ids) != 1:
            return None
        a = self._project.get_by_id(self._selected_artifact_ids[0])
        if a is None or a.artifact_type != "orbit":
            return None
        return a

    def _selected_exportable_artifact(self) -> Artifact | None:
        """返回当前选中的可导出动画的 Artifact（orbit 或 ephemeris），否则 None。

        动画导出的对象是星历产物（control_orbit 的 ephemeris 类型为主，
        也兼容 design_orbit 的 orbit 类型）。单选时返回该 Artifact。
        """
        if len(self._selected_artifact_ids) != 1:
            return None
        a = self._project.get_by_id(self._selected_artifact_ids[0])
        if a is None or a.artifact_type not in ("orbit", "ephemeris"):
            return None
        return a

    # -- 右键菜单动作（#340）------------------------------------------------

    def _on_context_action(self, action: str, artifact_ids: list[str]) -> None:
        """分发项目树右键菜单动作。

        generate_family / analyze_stability / optimize / expand_members 在
        ProjectTreeView 中已 setEnabled(False)，不会触发到这里。
        """
        if action == "delete":
            self._delete_artifacts(artifact_ids)
        elif action == "control_orbit":
            self._trigger_control_orbit_from_tree(artifact_ids)

    def _delete_artifacts(self, artifact_ids: list[str]) -> None:
        """从 Project 移除 Artifact 并刷新树与画布。"""
        if not artifact_ids:
            return
        removed = sum(1 for aid in artifact_ids if self._project.remove(aid))
        # 从画布选中集剔除已删项
        self._selected_artifact_ids = [
            aid for aid in self._selected_artifact_ids if aid not in artifact_ids
        ]
        self._refresh_project_tree()
        self._render_canvas()
        self._status_bar.showMessage(f"已删除 {removed} 个 Artifact", _STATUS_MSG_TIMEOUT_MS)

    def _trigger_control_orbit_from_tree(self, artifact_ids: list[str]) -> None:
        """右键 orbit → 轨道保持：选中该 Artifact + 切到 control_orbit 工具。

        不自动运行（给用户在参数面板调参的机会），与 #348 工具选择器范式一致。
        """
        if not artifact_ids:
            return
        orbit_id = artifact_ids[0]
        artifact = self._project.get_by_id(orbit_id)
        if artifact is None or artifact.artifact_type != "orbit":
            return
        if artifact.state_data is None and artifact.output_path is not None:
            load_artifact_arrays(artifact)
        self._selected_artifact_ids = [orbit_id]
        for i in range(self._tool_combo.count()):
            if self._tool_combo.itemData(i) == "control_orbit":
                self._tool_combo.setCurrentIndex(i)
                break
        self._status_bar.showMessage("已选中轨道，调整参数后点运行", _STATUS_MSG_TIMEOUT_MS)

    @staticmethod
    def _detect_kernel_dir() -> str:
        """自动探测 SPICE 内核目录（逻辑见 src.commons.paths.detect_kernel_dir）。"""
        return detect_kernel_dir()

    def _on_worker_log(self, msg: str) -> None:
        self._log.append_log(msg)

    def _on_design_finished(self, result: OrbitDesignResultData) -> None:
        # G1: 恢复按钮状态
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")

        # Issue #338: 计算结果落盘（JSON 元数据 + NPZ 数组）
        json_path: Path | None = None
        npz_name = ""
        try:
            json_path, npz_path = save_artifact(result, OUTPUT_DIR)
            npz_name = npz_path.name
            self._log.append_log(f"结果已保存: {json_path.name}")
        except Exception as exc:  # noqa: BLE001
            # S4: 持久化失败也要保证 in-memory Artifact 可用；明确告知用户
            self._log.append_log(f"持久化失败: {exc}（结果仅保留在内存中）")
            self._status_bar.showMessage("持久化失败", _STATUS_MSG_TIMEOUT_MS)

        artifact = Artifact(
            artifact_type="orbit",
            label=f"{result.orbit_type} (C_J={result.cr3bp_jacobi:.4f})",
            orbit_type=result.orbit_type,
            source_tool="design_orbit",
            state_data=result.states,
            times=result.times,
            output_path=json_path,
            extra={
                # 元数据键与 persistence.save_artifact 写入磁盘 JSON 的键保持一致
                "cr3bp_jacobi": result.cr3bp_jacobi,
                "mu": result.mu,
                "epoch_utc": result.epoch_utc,
                "correction_converged": result.correction_converged,
                "correction_iterations": result.correction_iterations,
                "arrays_file": npz_name,
                "ephemeris": result.ephemeris,  # 内存直通，control_orbit 即可用
            },
        )
        self._project.add(artifact)
        self._refresh_project_tree()

        if artifact.state_data is not None:
            self._selected_artifact_ids = [artifact.artifact_id]
            self._render_canvas()
            self._center_tabs.setCurrentIndex(0)

        self._log.append_log(f"设计完成: {result.orbit_type}, C_J={result.cr3bp_jacobi:.6f}")
        # S4: 若持久化失败，最终状态栏提示优先告知错误（避免被"完成"覆盖）
        if json_path is None:
            self._status_bar.showMessage("设计完成但持久化失败", _STATUS_MSG_TIMEOUT_MS)
        else:
            self._status_bar.showMessage(f"{result.orbit_type} 设计完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_design_error(self, error_msg: str) -> None:
        # G1: 恢复按钮状态
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")

        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("设计失败", _STATUS_MSG_TIMEOUT_MS)

    def _on_control_finished(self, result: ControlResultData) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")

        json_path: Path | None = None
        try:
            json_path, _ = save_control_result(result, OUTPUT_DIR)
            self._log.append_log(f"结果已保存: {json_path.name}")
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"持久化失败: {exc}（结果仅保留在内存中）")
            self._status_bar.showMessage("持久化失败", _STATUS_MSG_TIMEOUT_MS)

        total_dv = float(np.sum(result.maneuvers_delta_v_mps))
        artifact = Artifact(
            artifact_type="ephemeris",
            label=f"受控星历 (Δv={total_dv:.1f} m/s)",
            source_tool="control_orbit",
            state_data=result.controlled_states,
            times=result.controlled_times,
            output_path=json_path,
            extra={
                "mu": result.mu,
                "num_failed": result.num_failed,
                "total_delta_v_mps": total_dv,
                "n_maneuvers": int(len(result.maneuvers_mjd_tdb)),
                # 真物理时间（ET 秒）+ GCRS 惯性 km 位置：P1 坐标系切换、
                # P2 帧动画所需，P0 画布不读。
                "times_et": result.times_et,
                "position_km": result.position_km,
            },
        )
        self._project.add(artifact)
        self._refresh_project_tree()

        if artifact.state_data is not None:
            self._selected_artifact_ids = [artifact.artifact_id]
            self._render_canvas()
            self._center_tabs.setCurrentIndex(0)

        self._log.append_log(
            f"轨道保持完成: 总Δv={total_dv:.2f} m/s, 失败 {result.num_failed} 样本"
        )
        if json_path is not None:
            self._status_bar.showMessage("轨道保持完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_control_error(self, error_msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("轨道保持失败", _STATUS_MSG_TIMEOUT_MS)

    # -- 渲染 ---------------------------------------------------------------

    # Issue #339: CanvasState 流 -- 单一状态源 + render() 单入口

    def _warn_missing_mu(self, artifact: Artifact) -> None:
        """旧 Artifact 无 mu 时提示：地月/L 点标注不可用（计划决策 3）。"""
        if artifact.state_data is not None and artifact.extra.get("mu") is None:
            self._log.append_log(f"旧 Artifact 无 mu，跳过地月标注: {artifact.label}")

    def _artifact_for_id(self, artifact_id: str) -> dict | None:
        """返回画布渲染所需的 Artifact 数据（不含 e2m2e 类型）。

        经 canvas.set_artifacts_provider() 注入；渲染前由 canvas.sync_state()
        调用，返回内存数组，不从磁盘/NPZ 重读。
        """
        a = self._project.get_by_id(artifact_id)
        if a is None or a.state_data is None:
            return None
        return {
            "states": a.state_data,
            "label": a.label,
            "mu": a.extra.get("mu"),
            # P0 仅透传到画布接口；P1 坐标系切换/P2 帧动画消费这两个字段。
            # 缺失（旧 Artifact）返回 None，画布降级处理。
            "position_km": a.extra.get("position_km"),
            "times_et": a.extra.get("times_et"),
        }

    def _render_canvas(self) -> None:
        """同步 CanvasState 并触发 render()。数据在内存，不从 NPZ 重读。"""
        self._viz.canvas.sync_state(self._canvas_state, self._selected_artifact_ids)
        self._viz.canvas.render()

    def _on_projection_changed(self, projection: str) -> None:
        self._canvas_state.projection = projection
        self._render_canvas()

    def _on_toggle_bodies(self, checked: bool) -> None:
        self._canvas_state.show_bodies = checked
        self._render_canvas()

    def _on_toggle_libration(self, checked: bool) -> None:
        self._canvas_state.show_libration = checked
        self._render_canvas()

    def _on_frame_changed(self, frame: str) -> None:
        """坐标系切换：会合系（CR3BP 旋转系）/ 惯性系（GCRS/J2000，km）。

        inertial 需要 position_km + times_et；缺失时画布降级（仅地球原点），
        并在状态栏提示。
        """
        self._canvas_state.frame = frame
        if frame == "inertial" and not self._selected_artifacts_have_inertial():
            self._status_bar.showMessage("该 Artifact 无星历惯性数据", _STATUS_MSG_TIMEOUT_MS)
        self._render_canvas()

    def _selected_artifacts_have_inertial(self) -> bool:
        """任一当前选中 Artifact 同时含 position_km 与 times_et 即为 True。"""
        for aid in self._selected_artifact_ids:
            a = self._project.get_by_id(aid)
            if a is None:
                continue
            if a.extra.get("position_km") is not None and a.extra.get("times_et") is not None:
                return True
        return False

    # -- 导出动画（P2，单条星历 Artifact -> GIF） -------------------------

    def _on_export_animation(self) -> None:
        """工具栏"导出动画"：检查选中 Artifact → 弹参数对话框 → 选保存路径 → 渲染。

        数据不全（synodic 缺 states / inertial 缺 position_km+times_et）时给出
        明确降级提示，不进入对话框。导出期间状态栏提示"正在导出"，同步渲染
        （不强制 QThread，离线导出非频繁操作）。
        """
        artifact = self._selected_exportable_artifact()
        if artifact is None or artifact.state_data is None:
            self._status_bar.showMessage("请先选中一条星历 Artifact", _STATUS_MSG_TIMEOUT_MS)
            return

        artifact_data = self._artifact_for_id(artifact.artifact_id)
        if artifact_data is None:
            self._status_bar.showMessage("该 Artifact 数据不可用", _STATUS_MSG_TIMEOUT_MS)
            return

        has_inertial = (
            artifact_data.get("position_km") is not None
            and artifact_data.get("times_et") is not None
        )
        has_synodic = (
            artifact_data.get("states") is not None and artifact_data.get("times_et") is not None
        )
        if not (has_inertial or has_synodic):
            self._status_bar.showMessage(
                "该 Artifact 无星历时间数据，无法导出动画", _STATUS_MSG_TIMEOUT_MS
            )
            return

        params = self._ask_gif_export_params(has_synodic=has_synodic, has_inertial=has_inertial)
        if params is None:
            return  # 用户取消

        # 选保存路径
        default_name = f"{artifact.label or 'animation'}.gif"
        path, _ = QFileDialog.getSaveFileName(self, "保存 GIF", default_name, "GIF 动画 (*.gif)")
        if not path:
            return

        self._status_bar.showMessage("正在导出动画...")
        try:
            from src.view.gif_exporter import export_animation

            output = export_animation(
                self._viz.canvas,
                artifact_data,
                frame=params["frame"],
                time_range=None,  # 用 times_et 全量，帧数控制采样密度
                n_frames=params["n_frames"],
                window_mode=params["window_mode"],
                output_path=path,
                sliding_window_seconds=params.get("sliding_window_seconds"),
            )
        except Exception as exc:  # noqa: BLE001 -- 导出失败给明确提示，不崩
            self._status_bar.showMessage("动画导出失败", _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"动画导出失败: {exc}")
            return

        self._status_bar.showMessage(f"导出完成: {output}", _STATUS_MSG_TIMEOUT_MS)
        self._log.append_log(f"动画已导出: {output}")

    def _ask_gif_export_params(
        self,
        *,
        has_synodic: bool,
        has_inertial: bool,
    ) -> dict | None:
        """弹出 GIF 参数对话框，返回 {frame, n_frames, window_mode, ...} 或 None。

        默认 frame 取当前画布坐标系（inertial 优先，若数据支持）；帧数 20；
        窗口模式 cumulative。sliding 模式暴露窗口宽度输入。
        """
        from src.view.gif_exporter import DEFAULT_SLIDING_WINDOW_SECONDS

        dlg = QDialog(self)
        dlg.setWindowTitle("导出动画参数")
        form = QFormLayout(dlg)

        frame_combo = QComboBox()
        if has_synodic:
            frame_combo.addItem("会合系（CR3BP 旋转系）", "synodic")
        if has_inertial:
            frame_combo.addItem("惯性系（GCRS/J2000）", "inertial")
        # 默认与当前画布坐标系一致；不可用时选第一个
        current_frame = self._canvas_state.frame
        target_idx = next(
            (i for i in range(frame_combo.count()) if frame_combo.itemData(i) == current_frame),
            0,
        )
        frame_combo.setCurrentIndex(target_idx)
        form.addRow("坐标系", frame_combo)

        n_spin = QSpinBox()
        n_spin.setRange(2, 200)
        n_spin.setValue(20)
        form.addRow("帧数", n_spin)

        window_combo = QComboBox()
        window_combo.addItem("累计（每帧画 [t0, ti]）", "cumulative")
        window_combo.addItem("滑动（每帧画 [ti-w, ti]）", "sliding")
        form.addRow("窗口模式", window_combo)

        window_spin = QDoubleSpinBox()
        window_spin.setRange(1.0, 1e9)
        window_spin.setSuffix(" 秒")
        window_spin.setValue(DEFAULT_SLIDING_WINDOW_SECONDS)
        window_spin.setEnabled(False)
        window_combo.currentIndexChanged.connect(
            lambda idx: window_spin.setEnabled(window_combo.itemData(idx) == "sliding")
        )
        form.addRow("滑动窗宽度", window_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        params: dict = {
            "frame": frame_combo.currentData(),
            "n_frames": n_spin.value(),
            "window_mode": window_combo.currentData(),
        }
        if params["window_mode"] == "sliding":
            params["sliding_window_seconds"] = window_spin.value()
        return params

    # -- 项目树 -------------------------------------------------------------

    def _refresh_project_tree(self) -> None:
        self._tree_view.refresh(self._project)
