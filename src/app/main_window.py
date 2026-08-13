"""主窗口 -- 三栏 Splitter 布局。

组装 project_tree + canvas + params + log，连接 signals/slots。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.commons.paths import OUTPUT_DIR, detect_kernel_dir
from src.engine.facade_bridge import (
    TOOL_REGISTRY,
    ControlResultData,
    FamilyResultData,
    OrbitDesignResultData,
    StabilityResultData,
    ToolSpec,
)
from src.engine.persistence import (
    load_artifact_arrays,
    save_artifact,
    save_control_result,
    save_family_result,
    save_stability_result,
)
from src.engine.workers import (
    ControlOrbitWorker,
    FamilyOrbitWorker,
    OrbitDesignWorker,
    StabilityWorker,
)
from src.model import Artifact, Project
from src.model.discovery import discover_artifacts
from src.view.canvas import OrbitCanvasWithToolbar
from src.view.log_panel import LogPanel
from src.view.params_panel import (
    ORBIT_TYPE_DEFAULTS,
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
    "inclination": "倾角 (度)",
    "arg_of_pericenter": "近月点幅角 (度)",
    "semi_major_axis": "半长轴 (km)",
    # 轨道族生成参数（FamilyGenerationRequest）
    "max_amplitude_km": "最大面外振幅 (km)",
    "n_orbits": "族成员数",
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
        self._worker: (
            OrbitDesignWorker | ControlOrbitWorker | FamilyOrbitWorker | StabilityWorker | None
        ) = None
        self._current_tool_key: str | None = None
        self._param_widgets: dict[str, QWidget] = {}
        self._param_rows: dict[str, tuple[QLabel, QWidget, QComboBox | None]] = {}
        self._param_container: QWidget | None = None
        self._param_container_layout: QGridLayout | None = None
        self._param_scroll: QScrollArea | None = None
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
        # 分隔条可见性：默认 QSplitter handle 过细难以发现/抓住，着色 + hover
        # 加深；宽度用 setHandleWidth 设置（QSS 的 width 对 handle 不生效）。
        self.setStyleSheet(
            "QSplitter::handle { background-color: #c8c8c8; }"
            "QSplitter::handle:hover { background-color: #8f8f8f; }"
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())

        # D: 左右栏固定宽度（不随窗口拉伸），中间画布占满剩余空间
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([260, 820, 320])

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        from src.view.project_tree import ProjectTreeView

        panel = QWidget()
        panel.setMinimumWidth(200)
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
        # C: 画布与日志同屏（垂直 splitter），运行时可同时看轨道与日志，
        # 不再切 tab。日志默认高度较小，可拖动分隔条调整。
        self._viz = OrbitCanvasWithToolbar()
        # Issue #339: 注入数据回调 -- main_window 提供 state_data / label / mu 查询，
        # canvas 不自持 Project（view 只经接口与数据层交互）。
        self._viz.canvas.set_artifacts_provider(self._artifact_for_id)

        # Issue #339: 投影切换 + 地月/L 点开关（纯 UI，业务逻辑在此 slot 中）
        toolbar = self._viz.projection_toolbar
        toolbar.projection_3d.clicked.connect(lambda: self._on_projection_changed("3d"))
        toolbar.projection_xy.clicked.connect(lambda: self._on_projection_changed("xy"))
        toolbar.projection_xz.clicked.connect(lambda: self._on_projection_changed("xz"))
        toolbar.projection_yz.clicked.connect(lambda: self._on_projection_changed("yz"))
        toolbar.projection_quad.clicked.connect(lambda: self._on_projection_changed("quad"))
        toolbar.frame_synodic.clicked.connect(lambda: self._on_frame_changed("synodic"))
        toolbar.frame_inertial.clicked.connect(lambda: self._on_frame_changed("inertial"))
        toolbar.plot_overlay.clicked.connect(lambda: self._on_plot_content_changed("overlay"))
        toolbar.plot_guess.clicked.connect(lambda: self._on_plot_content_changed("guess"))
        toolbar.plot_ephemeris.clicked.connect(lambda: self._on_plot_content_changed("ephemeris"))
        toolbar.show_bodies.toggled.connect(self._on_toggle_bodies)
        toolbar.show_libration.toggled.connect(self._on_toggle_libration)
        toolbar.equal_aspect.toggled.connect(self._on_toggle_equal_aspect)
        toolbar.export_animation.clicked.connect(self._on_export_animation)

        self._log = LogPanel()
        self._log.setMinimumHeight(80)

        # 去掉 tab 后日志区不再自带标题，补一个与左侧「项目」一致的标签
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("日志"))
        log_layout.addWidget(self._log)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)
        splitter.addWidget(self._viz.widget)
        splitter.addWidget(log_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 160])

        return splitter

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

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

        # 参数容器：QScrollArea + QGridLayout（label 与控件同行、单位下拉并入
        # 控件行），字段多时可滚动，不再被窗口高度截断。
        self._param_scroll = QScrollArea()
        self._param_scroll.setWidgetResizable(True)
        self._param_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._param_container = QWidget()
        container_layout = QGridLayout(self._param_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        self._param_container_layout = container_layout
        self._param_scroll.setWidget(self._param_container)
        layout.addWidget(self._param_scroll)

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

        # 清空旧控件：替换 scroll area 的 widget。QScrollArea.setWidget 会销毁旧
        # container（连同其 layout 与子控件），QGridLayout 的 rowCount/rowStretch
        # 残留也一并重置——避免跨工具切换残留空行造成底部大段空白。
        self._param_widgets = {}
        self._param_rows = {}
        new_container = QWidget()
        new_layout = QGridLayout(new_container)
        new_layout.setContentsMargins(0, 0, 0, 0)
        self._param_container = new_container
        self._param_container_layout = new_layout
        if self._param_scroll is not None:
            self._param_scroll.setWidget(new_container)
        layout = new_layout

        # 生成控件
        self._param_widgets = build_params_from_model(spec.request_model)

        # G3: orbit_type -> QComboBox（若字段存在且有 description）
        if "orbit_type" in self._param_widgets:
            self._replace_orbit_type_with_combo(spec.request_model)

        # 显示字段：QGridLayout 3 列（label / 控件 / 单位下拉），label 与控件
        # 同行、单位下拉并入控件行。_param_rows 契约（label, widget, unit_combo）不变。
        row = 0
        for name, widget in self._param_widgets.items():
            options = get_field_units(name)
            label_text = (
                _field_label_with_unit(name, options[0].label)
                if options
                else _DESIGN_ORBIT_LABELS.get(name, name)
            )
            label_widget = QLabel(label_text)
            layout.addWidget(label_widget, row, 0)
            layout.addWidget(widget, row, 1)
            unit_combo: QComboBox | None = None
            if options:
                # 无注解局部变量承接：pyright 对 PyQt6 类型不做 isinstance/赋值收窄
                # （已知限制），带 `| None` 注解的变量赋值也不收窄，故换名新建。
                combo = QComboBox()
                for opt in options:
                    combo.addItem(opt.label)
                combo.setCurrentIndex(0)
                combo.currentIndexChanged.connect(
                    lambda _idx, n=name: self._on_unit_combo_changed(n)
                )
                layout.addWidget(combo, row, 2)
                unit_combo = combo
            self._param_rows[name] = (label_widget, widget, unit_combo)
            row += 1

        # control_orbit 的 input_ephemeris 由选中 Artifact 注入，不在 UI 暴露
        if tool_key == "control_orbit" and "input_ephemeris" in self._param_widgets:
            old = self._param_widgets.pop("input_ephemeris")
            self._remove_widget_and_label(old)

        # design_orbit：按 orbit_type 分支填默认值 + 只显示相关字段
        if tool_key == "design_orbit":
            orbit_type_widget = self._param_widgets.get("orbit_type")
            if isinstance(orbit_type_widget, QComboBox):
                # pyright 不窄化 PyQt6 类型的 isinstance（已知限制），带注解赋值强制类型
                orbit_combo: QComboBox = orbit_type_widget
                orbit_combo.currentIndexChanged.connect(self._on_orbit_type_changed)
                self._on_orbit_type_changed(orbit_combo.currentIndex())
            # duration GUI 默认下调至 1 个月（issue #355）：模型 default=1.0 年不动，
            # 仅在 GUI 层把单位切到"月"、值设为 1，让短弧设计更顺手。
            self._apply_duration_default_month()

        layout.setRowStretch(row, 1)

    def _remove_widget_and_label(self, widget: QWidget) -> None:
        """从参数容器布局移除指定控件的整行（label + widget + 单位下拉）。"""
        layout = self._param_container_layout
        for name, (label, w, unit_combo) in list(self._param_rows.items()):
            if w is widget:
                del self._param_rows[name]
                # QGridLayout 下 setParent(None) 不会自动移除布局项，须显式 removeWidget
                if layout is not None:
                    layout.removeWidget(label)
                    layout.removeWidget(widget)
                    if unit_combo is not None:
                        layout.removeWidget(unit_combo)
                label.setParent(None)
                widget.setParent(None)
                if unit_combo is not None:
                    unit_combo.setParent(None)
                return
        widget.setParent(None)

    def _replace_orbit_type_with_combo(self, model_class: type) -> None:
        """G3: orbit_type 字段替换为 QComboBox。

        选项来源是 ``ORBIT_TYPE_DEFAULTS`` 的 key（用户友好的分支名，如
        Halo/Lissajous/ELFO），而非 ``field.description`` 的全大写枚举——后者
        含 "..." 占位符、且 5.6.5 起改全大写（HALO/LISSAJOUS），不适合直接
        展示，也不与 ``apply_orbit_type_defaults`` 的分支 key 对齐。description
        仍作 tooltip。
        """
        field = model_class.model_fields.get("orbit_type")
        if field is None:
            return
        options = list(ORBIT_TYPE_DEFAULTS.keys())
        if not options:
            return

        combo = QComboBox()
        combo.addItems(options)
        if field.description:
            combo.setToolTip(field.description)

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
        # pyright 不窄化 PyQt6 类型的 isinstance（已知限制），带注解赋值强制类型
        orbit_combo: QComboBox = orbit_type_widget
        orbit_type = orbit_combo.currentText()
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
            self._warn_missing_ephemeris(artifact)
            self._selected_artifact_ids = [artifact_id]
            self._update_plot_content_controls()
            self._render_canvas()

    def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
        # Issue #339: 多选分支补上懒加载（现状缺失，见审查意见）
        for aid in artifact_ids:
            artifact = self._project.get_by_id(aid)
            if artifact is None:
                continue
            if artifact.state_data is None and artifact.output_path is not None:
                load_artifact_arrays(artifact)
            self._warn_missing_mu(artifact)
            self._warn_missing_ephemeris(artifact)
        self._selected_artifact_ids = list(artifact_ids)
        self._update_plot_content_controls()
        self._render_canvas()

    def _on_run(self) -> None:
        tool_key = self._current_tool_key
        spec = TOOL_REGISTRY.get(tool_key) if tool_key else None
        if spec is None or not spec.enabled or spec.request_model is None:
            return
        if tool_key == "design_orbit":
            self._run_design_orbit()
        elif tool_key == "control_orbit":
            self._run_control_orbit()
        elif tool_key == "orbit_family_generation":
            self._run_family_generation()

    def _run_design_orbit(self) -> None:
        spec = TOOL_REGISTRY["design_orbit"]
        model = spec.request_model
        if model is None:
            return

        orbit_type = ""
        orbit_type_widget = self._param_widgets.get("orbit_type")
        if isinstance(orbit_type_widget, QComboBox):
            # pyright 不窄化 PyQt6 类型的 isinstance（已知限制），带注解赋值强制类型
            orbit_combo: QComboBox = orbit_type_widget
            orbit_type = orbit_combo.currentText()

        try:
            params = collect_params(self._param_widgets, model)
        except ValueError as exc:
            self._status_bar.showMessage(str(exc), _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"参数错误: {exc}")
            return
        params.pop("orbit_type", None)

        kernel_dir = self._detect_kernel_dir() or None

        self._log.clear()
        # 开场日志（开始/参数）由 worker 统一 emit，避免主窗口与 worker 各打一次
        # 造成重复；这里只清空日志 + 状态栏即时反馈。
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

    def _run_family_generation(self) -> None:
        """运行 Halo 轨道族生成（工具选择器入口，参数来自面板）。"""
        spec = TOOL_REGISTRY["orbit_family_generation"]
        model = spec.request_model
        if model is None:
            return
        try:
            params = collect_params(self._param_widgets, model)
        except ValueError as exc:
            self._status_bar.showMessage(str(exc), _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"参数错误: {exc}")
            return

        self._log.clear()
        self._status_bar.showMessage("正在生成 Halo 轨道族...")
        self._run_btn.setEnabled(False)
        self._run_btn.setText("运行中...")

        self._worker = FamilyOrbitWorker(params=params, parent=self)
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_family_finished)
        self._worker.error.connect(self._on_family_error)
        self._worker.start()

    def _on_family_finished(self, result: FamilyResultData) -> None:
        """族生成完成：落盘 + 建 family Artifact + 画布叠加显示。"""
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")

        json_path: Path | None = None
        try:
            json_path, _ = save_family_result(result, OUTPUT_DIR)
            self._log.append_log(f"结果已保存: {json_path.name}")
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"持久化失败: {exc}（结果仅保留在内存中）")
            self._status_bar.showMessage("持久化失败", _STATUS_MSG_TIMEOUT_MS)

        artifact = Artifact(
            artifact_type="family",
            label=f"Halo 族 (L{result.libration_point}, {result.n_orbits} 条)",
            orbit_type=result.orbit_type,
            source_tool="orbit_family_generation",
            state_data=result.states,  # (m, n, 6)
            times=result.times,  # (m, n)
            output_path=json_path,
            extra={
                "mu": result.mu,
                "libration_point": result.libration_point,
                "z0s": result.z0s,
                "arrays_file": json_path.name if json_path else None,
            },
        )
        self._project.add(artifact)
        self._refresh_project_tree()

        if artifact.state_data is not None:
            self._selected_artifact_ids = [artifact.artifact_id]
            self._render_canvas()

        self._log.append_log(
            f"轨道族生成完成: {result.n_orbits} 条 Halo 轨道（L{result.libration_point}）"
        )
        if json_path is not None:
            self._status_bar.showMessage("轨道族生成完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_family_error(self, error_msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("轨道族生成失败", _STATUS_MSG_TIMEOUT_MS)

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

        generate_family / optimize / expand_members 在 ProjectTreeView 中
        setEnabled(False)，不会触发到这里。analyze_stability 由本方法
        直接启动后台分析（结果对话框 + 落盘）。
        """
        if action == "delete":
            self._delete_artifacts(artifact_ids)
        elif action == "control_orbit":
            self._trigger_control_orbit_from_tree(artifact_ids)
        elif action == "analyze_stability":
            self._trigger_stability_from_tree(artifact_ids)

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

    def _trigger_stability_from_tree(self, artifact_ids: list[str]) -> None:
        """右键 orbit → 查看稳定性：后台分析选中轨道，结果弹对话框 + 落盘。

        稳定性分析用 CR3BP 周期轨道（Artifact.state_data），无需 SPICE。
        mu 缺失（旧 Artifact）时由 FacadeBridge 用默认地月系统兜底。
        """
        if not artifact_ids:
            return
        orbit_id = artifact_ids[0]
        artifact = self._project.get_by_id(orbit_id)
        if artifact is None or artifact.artifact_type != "orbit":
            self._status_bar.showMessage("请选中一条轨道 Artifact", _STATUS_MSG_TIMEOUT_MS)
            return
        if artifact.state_data is None and artifact.output_path is not None:
            load_artifact_arrays(artifact)
        if artifact.state_data is None:
            self._status_bar.showMessage("该 Artifact 无轨道数据", _STATUS_MSG_TIMEOUT_MS)
            return

        self._stability_source_label = artifact.label
        self._log.append_log(f"稳定性分析: {artifact.label}")
        self._status_bar.showMessage("正在分析稳定性...")
        self._worker = StabilityWorker(
            states=artifact.state_data,
            times=artifact.times,
            mu=artifact.extra.get("mu"),
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_stability_finished)
        self._worker.error.connect(self._on_stability_error)
        self._worker.start()

    def _on_stability_finished(self, result: StabilityResultData) -> None:
        """稳定性分析完成：落盘 JSON + 弹结果对话框。"""
        label = getattr(self, "_stability_source_label", "orbit")
        try:
            json_path = save_stability_result(result, OUTPUT_DIR, orbit_label=label)
            self._log.append_log(f"稳定性结果已保存: {json_path.name}")
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"稳定性结果落盘失败: {exc}")
        self._show_stability_dialog(result, label)
        self._status_bar.showMessage("稳定性分析完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_stability_error(self, error_msg: str) -> None:
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("稳定性分析失败", _STATUS_MSG_TIMEOUT_MS)

    @staticmethod
    def _format_stability_text(result: StabilityResultData, orbit_label: str) -> str:
        """把稳定性 DTO 格式化为只读文本（对话框展示）。"""
        from enum import Enum

        lines: list[str] = [f"轨道: {orbit_label}", ""]

        cls = result.classification or {}
        stability_type = cls.get("stability_type")
        st_name = stability_type.value if isinstance(stability_type, Enum) else stability_type
        lines.append(f"稳定性分类: {st_name}")
        lines.append(f"  稳定: {cls.get('is_stable')}    不稳定: {cls.get('is_unstable')}")

        def _fmt(v: Any) -> str:
            return f"{v:.6f}" if isinstance(v, (int, float)) else str(v)

        lines.append(f"  稳定裕度: {_fmt(cls.get('stability_margin'))}")
        lines.append(
            f"  Floquet 模最大/最小: {_fmt(cls.get('max_eigenvalue_magnitude'))} / "
            f"{_fmt(cls.get('min_eigenvalue_magnitude'))}"
        )
        if cls.get("max_lyapunov_exponent") is not None:
            lines.append(f"  最大 Lyapunov 指数: {_fmt(cls.get('max_lyapunov_exponent'))}")

        idx = result.stability_indices or {}
        lines.append(
            "\n稳定性指数:  ν1={}  ν2={}  ν3={}  Broucke={}".format(
                *(_fmt(idx.get(k)) for k in ("nu1", "nu2", "nu3", "broucke"))
            )
        )

        bif = result.bifurcation or {}
        bif_type = bif.get("bifurcation_type")
        bif_name = bif_type.value if isinstance(bif_type, Enum) else bif_type
        lines.append(f"分岔: {bif_name}（检测到: {bif.get('bifurcation_detected')}）")

        ev = result.eigenvalues
        if ev is not None:
            lines.append("\nFloquet 乘子（单值矩阵特征值）:")
            for i, lam in enumerate(np.asarray(ev)):
                lines.append(
                    f"  λ{i + 1} = {lam.real:+.6f} {lam.imag:+.6f}j    |λ| = {abs(lam):.6f}"
                )

        mm = result.monodromy_matrix
        if mm is not None:
            lines.append("\n单值矩阵 (6×6):")
            for row in np.asarray(mm):
                lines.append("  " + "  ".join(f"{v:+.4f}" for v in row))

        return "\n".join(lines)

    def _show_stability_dialog(self, result: StabilityResultData, orbit_label: str) -> None:
        """弹出稳定性分析结果对话框（只读文本）。"""
        from PyQt6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QTextEdit,
            QVBoxLayout,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(f"稳定性分析 - {orbit_label}")
        dlg.resize(680, 560)
        layout = QVBoxLayout(dlg)

        text = QTextEdit(dlg)
        text.setReadOnly(True)
        text.setFontFamily("monospace")
        text.setPlainText(self._format_stability_text(result, orbit_label))
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

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

    def _warn_missing_ephemeris(self, artifact: Artifact) -> None:
        """轨道设计产物（design_orbit）无标称星历时提示：画布只能画初猜。

        #359 US 10：星历缺失要明确告知，而非画布静默只画初猜。design_orbit
        正常总会产出星历，此分支仅防御异常/旧产物。
        """
        if artifact.source_tool == "design_orbit" and not artifact.extra.get("ephemeris"):
            self._log.append_log(f"该轨道无标称星历，画布只能画初猜: {artifact.label}")

    def _artifact_for_id(self, artifact_id: str) -> dict | None:
        """返回画布渲染所需的 Artifact 数据（不含 e2m2e 类型）。

        经 canvas.set_artifacts_provider() 注入；渲染前由 canvas.sync_state()
        调用，返回内存数组，不从磁盘/NPZ 重读。

        契约（#359）：四份轨迹数据显式平级暴露给画布，不嵌套、不靠隐式 fallback。
        画布按 ``CanvasState.plot_content`` 选择消费哪一槽。

        - ``initial_guess_states``: CR3BP 周期轨道（无量纲会合系，质心归一）。
          仅 design_orbit 产物有；control_orbit 与历史 Artifact 为 None。
        - ``ephemeris_synodic``: 星历会合系位置（质心归一，已减 μ；ADR 0013）。
          design_orbit 的标称星历（从 extra["ephemeris"]）与 control_orbit 的
          受控星历（state_data 已在 facade_bridge 减过 μ）共用此槽。
        - ``ephemeris_position_km``: 星历惯性系 GCRS km 位置。
        - ``ephemeris_times_et``: 物理时间（ET 秒，与星历槽同源）。
        """
        a = self._project.get_by_id(artifact_id)
        if a is None or a.state_data is None:
            return None
        mu = a.extra.get("mu")
        data: dict = {
            "label": a.label,
            "mu": mu,
            "initial_guess_states": None,
            "ephemeris_synodic": None,
            "ephemeris_position_km": None,
            "ephemeris_times_et": None,
            "family_states": None,
        }
        if a.source_tool == "design_orbit":
            # CR3BP 周期轨道作为初猜；标称星历四件套来自 extra["ephemeris"]
            eph = a.extra.get("ephemeris") or {}
            data["initial_guess_states"] = a.state_data
            syn = eph.get("synodic_position")
            if syn is not None:
                # ADR 0013：星历会合系位置送画布前减 μ（地心归一 → 质心归一）
                data["ephemeris_synodic"] = np.asarray(syn) - (mu or 0.0)
            data["ephemeris_position_km"] = eph.get("position_km")
            data["ephemeris_times_et"] = eph.get("times_et")
        elif a.source_tool == "orbit_family_generation":
            # 轨道族：state_data 为 (m, n, 6) 三维数组，画布逐条渲染；
            # 族是纯 CR3BP 周期轨道（无量纲会合系，质心归一），无星历。
            data["family_states"] = a.state_data
        else:
            # control_orbit / 历史 ephemeris Artifact：state_data 已是质心归一
            # 的受控星历会合系位置（facade_bridge 减过 μ），作为星历会合系槽。
            data["ephemeris_synodic"] = a.state_data
            data["ephemeris_position_km"] = a.extra.get("position_km")
            data["ephemeris_times_et"] = a.extra.get("times_et")
        return data

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

    def _on_toggle_equal_aspect(self, checked: bool) -> None:
        """等比例开关：勾选后 3D/2D 按数据真实比例，否则各轴独立填满。"""
        self._canvas_state.equal_aspect = checked
        self._render_canvas()

    def _on_frame_changed(self, frame: str) -> None:
        """坐标系切换：会合系（CR3BP 旋转系）/ 惯性系（GCRS/J2000，km）。

        inertial 需要 position_km + times_et；缺失时画布降级（仅地球原点），
        并在状态栏提示。inertial 下 CR3BP 初猜无几何意义，"初猜"绘制内容
        自动切到"星历"并灰显控件。
        """
        self._canvas_state.frame = frame
        self._update_plot_content_controls()
        if frame == "inertial" and not self._selected_artifacts_have_inertial():
            self._status_bar.showMessage("该 Artifact 无星历惯性数据", _STATUS_MSG_TIMEOUT_MS)
        self._render_canvas()

    def _on_plot_content_changed(self, content: str) -> None:
        """绘制内容切换：初猜 / 星历 / 叠加（与会合系/惯性系正交）。

        仅会合系 + 含初猜数据的 Artifact 允许"初猜"；其他场景由
        ``_update_plot_content_controls`` 灰显。本 slot 不二次校验，依赖控件状态。
        """
        self._canvas_state.plot_content = content
        self._render_canvas()

    def _update_plot_content_controls(self) -> None:
        """按当前坐标系与选中 Artifact 启用/禁用"初猜"绘制按钮。

        规则：
        - 惯性系：CR3BP 无量纲初猜无惯性系表示，"初猜"灰显；若当前选了"初猜"，
          自动切到"星历"。
        - 选中 Artifact 任一含初猜（design_orbit 产物）：会合系下"初猜"可用。
        - 否则（control_orbit 产物）：会合系下"初猜"也灰显。
        """
        toolbar = self._viz.projection_toolbar
        guess_available = (
            self._canvas_state.frame == "synodic" and self._selected_artifacts_have_initial_guess()
        )
        toolbar.plot_guess.setEnabled(guess_available)
        if not guess_available and self._canvas_state.plot_content == "guess":
            # 初猜不可用时退到"星历"（有星历）或"叠加"（默认）
            self._canvas_state.plot_content = "ephemeris"
        self._sync_toolbar_buttons()

    def _sync_toolbar_buttons(self) -> None:
        """把工具栏按钮 checked 状态同步到 CanvasState。

        QButtonGroup 互斥保证用户点击时 checked 自动正确；此方法只在程序化
        改变 CanvasState 时（如惯性系强制 guess->ephemeris）同步高亮，避免
        状态与按钮脱节。setChecked 只发 toggled 不触发 connected 的 clicked
        信号，不会造成递归。
        """
        tb = self._viz.projection_toolbar
        state = self._canvas_state
        tb.projection_3d.setChecked(state.projection == "3d")
        tb.projection_xy.setChecked(state.projection == "xy")
        tb.projection_xz.setChecked(state.projection == "xz")
        tb.projection_yz.setChecked(state.projection == "yz")
        tb.projection_quad.setChecked(state.projection == "quad")
        tb.frame_synodic.setChecked(state.frame == "synodic")
        tb.frame_inertial.setChecked(state.frame == "inertial")
        tb.plot_overlay.setChecked(state.plot_content == "overlay")
        tb.plot_guess.setChecked(state.plot_content == "guess")
        tb.plot_ephemeris.setChecked(state.plot_content == "ephemeris")
        tb.equal_aspect.setChecked(state.equal_aspect)

    def _selected_artifacts_have_initial_guess(self) -> bool:
        """任一当前选中 Artifact 含 CR3BP 初猜（design_orbit 产物）即为 True。"""
        for aid in self._selected_artifact_ids:
            a = self._project.get_by_id(aid)
            if a is None:
                continue
            if a.source_tool == "design_orbit" and a.state_data is not None:
                return True
        return False

    def _selected_artifacts_have_inertial(self) -> bool:
        """任一当前选中 Artifact 同时含 position_km 与 times_et 即为 True。"""
        for aid in self._selected_artifact_ids:
            a = self._project.get_by_id(aid)
            if a is None:
                continue
            # design_orbit 的星历在 extra["ephemeris"]，control_orbit 在 extra 顶层
            if a.source_tool == "design_orbit":
                eph = a.extra.get("ephemeris") or {}
                if eph.get("position_km") is not None and eph.get("times_et") is not None:
                    return True
            elif a.extra.get("position_km") is not None and a.extra.get("times_et") is not None:
                return True
        return False

    # -- 导出动画（P2，单条星历 Artifact -> GIF） -------------------------

    def _on_export_animation(self) -> None:
        """工具栏"导出动画"：检查选中 Artifact → 弹参数对话框 → 选保存路径 → 渲染。

        绘制内容为"初猜"时不可导出（CR3BP 单周期无物理时间轴），状态栏明确提示。
        数据不全（synodic 缺 ephemeris_synodic / inertial 缺 ephemeris_position_km
        + ephemeris_times_et）时给出明确降级提示，不进入对话框。导出期间状态栏
        提示"正在导出"，同步渲染（不强制 QThread，离线导出非频繁操作）。
        """
        artifact = self._selected_exportable_artifact()
        if artifact is None or artifact.state_data is None:
            self._status_bar.showMessage("请先选中一条星历 Artifact", _STATUS_MSG_TIMEOUT_MS)
            return

        # 初猜模式无物理时间轴，明确拒绝（不进入对话框）
        if self._canvas_state.plot_content == "guess":
            self._status_bar.showMessage(
                "初猜模式无物理时间轴，无法导出动画（切到星历或叠加再导出）",
                _STATUS_MSG_TIMEOUT_MS,
            )
            return

        artifact_data = self._artifact_for_id(artifact.artifact_id)
        if artifact_data is None:
            self._status_bar.showMessage("该 Artifact 数据不可用", _STATUS_MSG_TIMEOUT_MS)
            return

        has_inertial = (
            artifact_data.get("ephemeris_position_km") is not None
            and artifact_data.get("ephemeris_times_et") is not None
        )
        has_synodic = (
            artifact_data.get("ephemeris_synodic") is not None
            and artifact_data.get("ephemeris_times_et") is not None
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
