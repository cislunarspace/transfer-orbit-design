"""主窗口 -- 三栏 Splitter 布局。

组装 project_tree + canvas + params + log，连接 signals/slots。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QByteArray, QDateTime, Qt
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.commons.paths import CATALOG_DIR, OUTPUT_DIR, detect_kernel_dir
from src.engine.catalog_service import CatalogService
from src.engine.exceptions import OrbitError
from src.engine.facade_bridge import (
    TOOL_REGISTRY,
    ControlResultData,
    FacadeBridge,
    FamilyResultData,
    OrbitDesignResultData,
    PropagationResultData,
    StabilityResultData,
    ToolSpec,
)
from src.engine.persistence import save_propagation_result, save_stability_result
from src.engine.workers import (
    ControlOrbitWorker,
    FamilyOrbitWorker,
    OrbitDesignWorker,
    PropagationWorker,
    StabilityWorker,
)
from src.model import Artifact, Project
from src.model.discovery import discover_artifacts
from src.view.canvas import OrbitCanvasWithToolbar
from src.view.chart_settings import (
    APP_NAME,
    ORG_NAME,
    chart_settings_dialog,
    load_settings,
    save_settings,
)
from src.view.log_panel import LogPanel
from src.view.params_panel import (
    FAMILY_TYPE_FIELDS,
    FAMILY_TYPES,
    ORBIT_TYPE_DEFAULTS,
    ORBIT_TYPE_FIELDS,
    _unwrap_optional_widget,
    apply_family_type_defaults,
    apply_orbit_type_defaults,
    build_params_from_model,
    collect_params,
    family_libration_points,
    get_field_units,
    set_spinbox_unit,
    sync_family_point_params,
)

# G4+G5: 工具选择器 + 灰色占位

_RIGHT_PANEL_TOOL_COMBO_LABEL = "选择工具"

#: CR3BP 周期轨道产物（初猜槽位）：design_orbit 设计结果与 catalog_promote
#: 提升的族成员（后者天然只有 CR3BP 段）。
_CR3BP_ORBIT_TOOLS = frozenset({"design_orbit", "catalog_promote"})

# 状态栏消息自动消失时长（毫秒）
_STATUS_MSG_TIMEOUT_MS = 5000

#: 主分栏默认宽度：左栏（项目树）/ 中栏（画布）/ 右栏（参数面板）。
#: 右栏 370：贴合三列参数行（最长标签+数字框+单位下拉）的内容宽度，
#: 数字框不拉长；240+778+370+2×6px 分隔条=1400 铺满默认窗口。
_MAIN_SPLITTER_SIZES = (240, 778, 370)

#: 中栏纵向分栏默认高度（画布/日志）
_CENTER_SPLITTER_SIZES = (560, 160)

#: 分栏默认值版本：默认宽度重设计时递增，升级后首次启动丢弃旧存档改用
#: 新默认（否则 restoreState 会永远恢复用户按旧默认拖出的位置）
_SPLITTER_DEFAULTS_VERSION = 3

#: 参数面板数字框（QSpinBox/QDoubleSpinBox）最大宽度：sizeHint 按兜底范围
#: （±1e12）+ 小数位计算可达 150px+，实际数字就几位，收紧到贴内容。
#: QDateTimeEdit（历元）不设限，日期时间串需要完整宽度。
_PARAM_SPINBOX_MAX_WIDTH = 110

# 上游控制器默认覆盖多年星历；GUI 的轨道设计默认输出短弧，因此首次轨道保持
# 使用已验证可覆盖 30 天标称星历的参数。用户仍可在面板中按任务需求调整。
_CONTROL_ORBIT_GUI_DEFAULTS = {
    "control_interval": 0.25,
    "feedback_arc": 0.125,
}


def _get_default_tool_key() -> str | None:
    """返回第一个 enabled 工具的 key，若无则 None。"""
    for key, spec in TOOL_REGISTRY.items():
        if spec.enabled:
            return key
    return None


# G4+G5: 字段标签（_FIELD_LABELS 已提取为模块级常量）
# 可切换单位字段的标签须以" (标准单位)"结尾（_base_field_label 按后缀剥离，
# 切单位时重新拼后缀），标准单位 = FIELD_UNIT_OPTIONS 首选项。

_DESIGN_ORBIT_LABELS: dict[str, str] = {
    "orbit_type": "轨道类型",
    "amplitude": "振幅 (km)",
    "phase": "初始相位 (周期份额)",
    "collinear_point": "共线平动点",
    "north_south": "北/南族",
    "perilune_height": "近月点高度 (km)",
    "amplitude_in": "面内振幅 (km)",
    "amplitude_out": "面外振幅 (km)",
    "phase_in": "面内相位 (周期份额)",
    "phase_out": "面外相位 (周期份额)",
    "epoch": "历元",
    "duration": "持续时间 (年)",
    "output_step": "输出步长 (秒)",
    "correction_method": "修正方法",
    "correction_revolutions": "修正圈数",
    "inclination": "倾角 (度)",
    "arg_of_pericenter": "近月点幅角 (度)",
    "semi_major_axis": "半长轴 (km)",
    "perturbation": "摄动开关 (JSON)",
    "dyb": "DYB 面质比 (JSON)",
    "earth_degree": "地球引力位阶数",
    "moon_degree": "月球引力位阶数",
    # 轨道保持字段（ControlOrbitRequest）
    "control_mode": "控制模式",
    "is_nrho": "目标为 NRHO",
    "special_mode": "特征点模式",
    "control_interval": "控制间隔 (天)",
    "feedback_arc": "反馈弧段 (天)",
    "special_crossings": "特征点穿越次数",
    "num_controls": "控制次数",
    "num_monte_carlo": "蒙特卡洛样本数",
    "position_accuracy": "测定轨位置误差 (m)",
    "velocity_accuracy": "测定轨速度误差 (m/s)",
    "thrust_angle_err": "推力方向角误差 (度)",
    "thrust_mean": "推力中点值 (m/s)",
    "thrust_rel_err": "推力相对误差",
    "thrust_abs_err": "推力绝对误差 (m/s)",
    "thrust_min": "最小开机推力 (m/s)",
    "thrust_max": "最大开机推力 (m/s)",
    "thrust_total": "累计推力上限 (m/s)",
    "srp_error_level": "光压弧段随机误差",
    "real_perturbation": "真实力模型摄动开关 (JSON)",
    "real_dyb": "真实力模型 DYB 面质比 (JSON)",
    "real_earth_degree": "真实地球引力位阶数",
    "real_moon_degree": "真实月球引力位阶数",
    "engine_layout": "发动机布局 (JSON)",
    "momentum_interval": "角动量卸载间隔 (天)",
    "srp_offset_m": "SRP 压心偏移 (m)",
    "spacecraft_mass": "航天器质量 (kg)",
    "srp_torque": "SRP 力矩 (N·m)",
    "tight_tolerance_km": "严格控制位置容差 (km)",
    "tight_max_iter": "严格控制迭代上限",
    "special_damping_factor": "特征点迭代阻尼因子",
    # 轨道预报字段（PropagationRequest，#389）
    "initial_state": "初值 (GCRS km, km/s)",
    "force_config": "力模型配置 (JSON)",
    # 轨道族生成参数（FamilyGenerationRequest）
    "libration_point": "平动点",
    "max_amplitude_km": "最大振幅 (km)",
    "min_amplitude_km": "最小振幅 (km)",
    "perilune_height_max_km": "近月点高度上限 (km)",
    "amplitude_in_km": "面内振幅上限 (km)",
    "amplitude_out_km": "面外振幅上限 (km)",
    "continuation_direction": "延拓方向",
    "match_tolerance_km": "振幅匹配容差 (km)",
    "n_orbits": "族成员数",
}

#: 参数分组：工具 -> ((组标题, 字段元组), ...)。未分组的字段归入自动追加的
#: "其他" 组（e2m2e 新增字段不会被遗漏）。轨道类型切换时整组隐藏。
_PARAM_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "design_orbit": (
        (
            "形状参数",
            (
                "orbit_type",
                "amplitude",
                "phase",
                "collinear_point",
                "north_south",
                "perilune_height",
                "amplitude_in",
                "amplitude_out",
                "phase_in",
                "phase_out",
                "semi_major_axis",
                "inclination",
                "arg_of_pericenter",
            ),
        ),
        (
            "传播参数",
            (
                "epoch",
                "duration",
                "output_step",
                "perturbation",
                "dyb",
                "earth_degree",
                "moon_degree",
            ),
        ),
        ("修正参数", ("correction_method", "correction_revolutions")),
    ),
    "control_orbit": (
        (
            "控制参数",
            (
                "control_mode",
                "is_nrho",
                "special_mode",
                "control_interval",
                "feedback_arc",
                "special_crossings",
                "num_controls",
                "tight_tolerance_km",
                "tight_max_iter",
                "special_damping_factor",
            ),
        ),
        (
            "仿真与误差",
            (
                "num_monte_carlo",
                "output_step",
                "position_accuracy",
                "velocity_accuracy",
                "thrust_angle_err",
                "thrust_mean",
                "thrust_rel_err",
                "thrust_abs_err",
                "thrust_min",
                "thrust_max",
                "thrust_total",
                "srp_error_level",
                "spacecraft_mass",
                "srp_offset_m",
                "srp_torque",
            ),
        ),
        (
            "力模型",
            (
                "perturbation",
                "dyb",
                "earth_degree",
                "moon_degree",
                "real_perturbation",
                "real_dyb",
                "real_earth_degree",
                "real_moon_degree",
            ),
        ),
        ("角动量管理", ("engine_layout", "momentum_interval")),
    ),
    "orbit_propagation": (
        (
            "初值",
            (
                "initial_state",
                "epoch",
            ),
        ),
        (
            "预报参数",
            (
                "duration",
                "output_step",
                "force_config",
            ),
        ),
    ),
    "orbit_family_generation": (
        (
            "族参数",
            (
                "orbit_type",
                "libration_point",
                "n_orbits",
                "max_amplitude_km",
                "min_amplitude_km",
                "north_south",
                "perilune_height_max_km",
                "amplitude_in_km",
                "amplitude_out_km",
                "phase_in",
                "phase_out",
                "continuation_direction",
                "match_tolerance_km",
            ),
        ),
    ),
}

#: design_orbit 所有分支字段的并集（不在其中的字段视为通用字段，始终显示）
_ORBIT_TYPE_ALL_BRANCH_FIELDS: set[str] = set().union(*ORBIT_TYPE_FIELDS.values())


#: 族生成公共参数字段（任何族都可传给 FamilyGenerationRequest）。
_FAMILY_COMMON_PARAMS = frozenset({"orbit_type", "n_orbits"})


def _family_request_params(params: dict, family_type: str) -> dict:
    """过滤面板收集的族生成参数，只留当前族适用字段。

    e2m2e 5.7.1 起 FamilyGenerationRequest 按 model_fields_set 拒绝跨族字段
    （None 也算已设置）：隐藏分支的残留值与未勾选 Optional 的 None 都不能
    进入 request，由模型填族默认。

    5.8.2 起 DRO 为月心族、不绑定平动点：平动点下拉被清空/隐藏后，收集到的
    空字符串必须被过滤掉，否则会触发 ``libration_point`` 的 int 解析错误。
    """
    allowed = FAMILY_TYPE_FIELDS.get(family_type, set()) | _FAMILY_COMMON_PARAMS
    if family_libration_points(family_type):
        allowed = allowed | {"libration_point"}
    return {k: v for k, v in params.items() if k in allowed and v is not None}


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

    def __init__(self, parent=None, *, catalog: CatalogService | None = None) -> None:
        super().__init__(parent)
        self._project = Project(name="Transfer Orbit Design")
        self._worker: (
            OrbitDesignWorker
            | ControlOrbitWorker
            | FamilyOrbitWorker
            | StabilityWorker
            | PropagationWorker
            | None
        ) = None
        self._stop_requested = False
        self._current_tool_key: str | None = None
        self._param_widgets: dict[str, QWidget] = {}
        self._param_rows: dict[str, tuple[QLabel, QWidget, QComboBox | None]] = {}
        # 参数分组：组标题 -> (QLabel 表头, QFrame 分隔线)；组标题 -> 组内字段
        self._group_headers: dict[str, tuple[QLabel, QFrame]] = {}
        self._group_fields: dict[str, list[str]] = {}
        self._param_container: QWidget | None = None
        self._param_container_layout: QGridLayout | None = None
        self._param_scroll: QScrollArea | None = None
        self._run_btn = QPushButton("运行")  # G1: 非 Optional，_build_right_panel 中配置
        self._run_btn.setObjectName("runButton")  # 挂钩全局样式表
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setEnabled(False)
        self._reset_btn = QPushButton("重置参数")

        # Issue #339: 画布渲染状态（CanvasState）与当前选中 Artifact 集合
        from src.view.canvas import CanvasState

        self._canvas_state = CanvasState()
        self._selected_artifact_ids: list[str] = []

        # 图表设置：QSettings 持久化，启动加载后注入画布
        from PyQt6.QtCore import QSettings

        self._qsettings = QSettings(ORG_NAME, APP_NAME)
        self._chart_settings = load_settings(self._qsettings)

        # Issue #375: 轨道库 catalog -- 产物清单 / 过滤 / 谱系 / 标注 / 导出。
        # 库目录 QSettings 可改，默认仓库根 catalog/（与 output/ 平级）。
        self._catalog_dir = self._load_catalog_dir()
        self._catalog: CatalogService = (
            catalog
            if catalog is not None
            else CatalogService(
                FacadeBridge(
                    kernel_dir=detect_kernel_dir() or None, catalog_dir=str(self._catalog_dir)
                )
            )
        )
        self._catalog_filters: dict = {}
        # catalog 分类体系之外的遗留分区（transfer）：目录扫描过渡，不参与过滤
        self._legacy_artifacts: list[Artifact] = []

        self.setWindowTitle("Transfer Orbit Design v2")
        self.resize(1400, 900)

        self._build_ui()
        self._build_menu()
        # 设置注入画布（_build_ui 之后，canvas 已创建）
        self._viz.canvas.set_chart_settings(self._chart_settings)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

        # 启动恢复：产物清单经 catalog_query 重建（含 transfer 遗留分区）
        self._reload_from_catalog()

    def _load_catalog_dir(self) -> Path:
        """读库目录设置（QSettings）；未设置或目录已不存在时用仓库根默认。"""
        value = self._qsettings.value("catalog/dir", "")
        if value and Path(value).is_dir():
            return Path(value)
        return CATALOG_DIR

    def _reload_from_catalog(self) -> None:
        """按当前过滤条件重查轨道库并重建 Project（清单单一来源）。"""
        try:
            artifacts = self._catalog.query_artifacts(self._catalog_filters)
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"读取轨道库失败: {exc}")
            self._status_bar.showMessage("读取轨道库失败", _STATUS_MSG_TIMEOUT_MS)
            return
        if not self._legacy_artifacts:
            try:
                self._legacy_artifacts = discover_artifacts(OUTPUT_DIR)
            except Exception as exc:  # noqa: BLE001
                self._log.append_log(f"扫描遗留 transfer 分区失败: {exc}")
        self._project = Project(name="Transfer Orbit Design")
        for artifact in artifacts:
            self._project.add(artifact)
        for artifact in self._legacy_artifacts:
            self._project.add(artifact)
        # 断链判定依据全库（未过滤视图），过滤把上游筛出清单不算断链
        if self._catalog_filters:
            try:
                self._project.known_record_ids = {
                    a.record_id for a in self._catalog.query_artifacts(None) if a.record_id
                }
            except Exception as exc:  # noqa: BLE001
                self._log.append_log(f"读取轨道库全量清单失败: {exc}")
        else:
            self._project.known_record_ids = {a.record_id for a in artifacts if a.record_id}
        self._refresh_project_tree()

    # -- UI 构建 -----------------------------------------------------------

    def _build_ui(self) -> None:
        # 分隔条着色等全局样式集中在 ui_settings.build_app_stylesheet（启动时应用）
        # 一次性迁移：分栏默认值升版后丢弃按旧默认拖出的存档，首次启动套用新默认
        if (
            self._qsettings.value("ui/splitter/defaults_version", 0, type=int)
            < _SPLITTER_DEFAULTS_VERSION
        ):
            self._qsettings.remove("ui/splitter/main")
            self._qsettings.remove("ui/splitter/center")
            self._qsettings.setValue("ui/splitter/defaults_version", _SPLITTER_DEFAULTS_VERSION)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        self._main_splitter = splitter

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())

        # D: 左右栏固定宽度（不随窗口拉伸），中间画布占满剩余空间
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        # 禁止拖没：任一栏都可拖宽拖窄，但不允许完全收起导致功能消失
        for i in range(3):
            splitter.setCollapsible(i, False)
        # 分隔条位置持久化：有存档用存档，否则用默认；「重置布局」可恢复默认
        saved = self._qsettings.value("ui/splitter/main")
        if not isinstance(saved, QByteArray) or not splitter.restoreState(saved):
            splitter.setSizes(_MAIN_SPLITTER_SIZES)

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        from src.view.catalog_filter_bar import CatalogFilterBar
        from src.view.project_tree import ProjectTreeView
        from src.view.record_detail_panel import RecordDetailPanel

        panel = QWidget()
        panel.setMinimumWidth(200)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("项目"))
        # Issue #375: 过滤栏（多维组合，直接驱动 catalog_query）+ 记录详情
        self._filter_bar = CatalogFilterBar()
        self._filter_bar.filters_changed.connect(self._on_filters_changed)
        self._filter_bar.export_requested.connect(self._on_export_requested)
        layout.addWidget(self._filter_bar)
        self._tree_view = ProjectTreeView()
        self._tree_view.artifact_selected.connect(self._on_artifact_clicked)
        self._tree_view.artifacts_selected.connect(self._on_artifacts_multi_selected)
        self._tree_view.context_action.connect(self._on_context_action)
        layout.addWidget(self._tree_view, 3)
        self._detail_panel = RecordDetailPanel()
        self._detail_panel.tag_requested.connect(self._on_tag_requested)
        self._detail_panel.promote_requested.connect(self._on_promote_requested)
        layout.addWidget(self._detail_panel, 2)

        return panel

    def _build_menu(self) -> None:
        """菜单栏：设置 → 图表设置 / 界面设置 / 轨道库目录 / 重置布局。"""
        menu_bar = self.menuBar()
        if menu_bar is None:
            return
        menu = menu_bar.addMenu("设置")
        if menu is None:
            return
        action = menu.addAction("图表设置…")
        if action is not None:
            action.triggered.connect(self._open_chart_settings)
        ui_action = menu.addAction("界面设置…")
        if ui_action is not None:
            ui_action.triggered.connect(self._open_ui_settings)
        catalog_action = menu.addAction("轨道库目录…")
        if catalog_action is not None:
            catalog_action.triggered.connect(self._open_catalog_dir_settings)
        layout_action = menu.addAction("重置布局")
        if layout_action is not None:
            layout_action.triggered.connect(self._reset_layout)

    def _open_ui_settings(self) -> None:
        """弹出界面设置对话框（字号/主题）；确认后持久化，重启后生效。"""
        from src.view.ui_settings import (
            load_ui_settings,
            save_ui_settings,
            ui_settings_dialog,
        )

        new_settings = ui_settings_dialog(self, load_ui_settings(self._qsettings))
        if new_settings is None:
            return
        save_ui_settings(self._qsettings, new_settings)
        self._status_bar.showMessage("界面设置已保存，将在下次启动时生效", _STATUS_MSG_TIMEOUT_MS)

    def _reset_layout(self) -> None:
        """恢复默认分栏布局，并清除持久化的分隔条位置。"""
        self._qsettings.remove("ui/splitter/main")
        self._qsettings.remove("ui/splitter/center")
        self._main_splitter.setSizes(_MAIN_SPLITTER_SIZES)
        self._center_splitter.setSizes(_CENTER_SPLITTER_SIZES)
        self._status_bar.showMessage("布局已恢复默认", _STATUS_MSG_TIMEOUT_MS)

    def closeEvent(self, a0) -> None:  # noqa: N802, ANN001 - Qt 覆盖方法签名
        """关闭时记住分隔条位置，下次启动恢复原布局。"""
        self._qsettings.setValue("ui/splitter/main", self._main_splitter.saveState())
        self._qsettings.setValue("ui/splitter/center", self._center_splitter.saveState())
        super().closeEvent(a0)

    def _open_catalog_dir_settings(self) -> None:
        """切换轨道库目录（QSettings 持久化；清单从新库重读，新计算写入新库）。"""
        directory = QFileDialog.getExistingDirectory(self, "选择轨道库目录", str(self._catalog_dir))
        if not directory:
            return
        self._qsettings.setValue("catalog/dir", directory)
        self._catalog_dir = Path(directory)
        self._catalog = CatalogService(
            FacadeBridge(kernel_dir=detect_kernel_dir() or None, catalog_dir=str(directory))
        )
        self._reload_from_catalog()
        self._status_bar.showMessage(
            f"轨道库已切换到 {directory}（后续计算写入新库）", _STATUS_MSG_TIMEOUT_MS
        )

    def _open_chart_settings(self) -> None:
        """弹出图表设置对话框；确认后持久化并重绘画布。"""
        new_settings = chart_settings_dialog(self, self._chart_settings)
        if new_settings is None:
            return
        self._chart_settings = new_settings
        save_settings(self._qsettings, new_settings)
        self._viz.canvas.set_chart_settings(new_settings)
        self._render_canvas()
        self._status_bar.showMessage("图表设置已保存", _STATUS_MSG_TIMEOUT_MS)

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
        toolbar.center_barycenter.clicked.connect(lambda: self._on_center_changed("barycenter"))
        toolbar.center_moon.clicked.connect(lambda: self._on_center_changed("moon"))
        toolbar.center_l1.clicked.connect(lambda: self._on_center_changed("L1"))
        toolbar.center_l2.clicked.connect(lambda: self._on_center_changed("L2"))
        toolbar.plot_overlay.clicked.connect(lambda: self._on_plot_content_changed("overlay"))
        toolbar.plot_guess.clicked.connect(lambda: self._on_plot_content_changed("guess"))
        toolbar.plot_ephemeris.clicked.connect(lambda: self._on_plot_content_changed("ephemeris"))
        toolbar.show_bodies.toggled.connect(self._on_toggle_bodies)
        toolbar.show_libration.toggled.connect(self._on_toggle_libration)
        toolbar.equal_aspect.toggled.connect(self._on_toggle_equal_aspect)
        toolbar.export_animation.clicked.connect(self._on_export_animation)
        toolbar.fit_view.clicked.connect(self._viz.canvas.fit_to_data)

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
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        saved = self._qsettings.value("ui/splitter/center")
        if not isinstance(saved, QByteArray) or not splitter.restoreState(saved):
            splitter.setSizes(_CENTER_SPLITTER_SIZES)
        self._center_splitter = splitter

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
                    item.setToolTip(spec.description)
        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        layout.addWidget(self._tool_combo)

        # 工具说明：切换工具时同步（帮助用户理解工具用途与输入要求）；
        # 字号颜色与正文一致，不再用灰色小字
        self._tool_desc_label = QLabel("")
        self._tool_desc_label.setWordWrap(True)
        layout.addWidget(self._tool_desc_label)

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

        # G1: 配置运行按钮（已在 __init__ 中创建）；样式经 objectName 挂钩全局
        # 样式表（ui_settings.build_app_stylesheet），不在此内联
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn.clicked.connect(self._on_stop_run)
        # 重置按钮：重建当前工具参数面板（恢复模型默认值 + 轨道类型默认值）
        self._reset_btn.clicked.connect(self._on_reset_params)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addWidget(self._reset_btn, 1)
        btn_row.addWidget(self._run_btn, 2)
        btn_row.addWidget(self._stop_btn, 1)
        layout.addLayout(btn_row)

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
        spec = TOOL_REGISTRY.get(tool_key)
        if self._tool_desc_label is not None and spec is not None:
            self._tool_desc_label.setText(spec.description)
        self._build_tool_params(tool_key)

    def _on_reset_params(self) -> None:
        """重置参数：重建当前工具面板（恢复模型默认值 + 轨道类型分支默认值）。"""
        if self._current_tool_key is not None:
            self._build_tool_params(self._current_tool_key)

    def _set_run_controls(self, *, running: bool, stopping: bool = False) -> None:
        """同步运行、停止、重置和工具选择控件的可用状态。"""
        if running and not stopping:
            self._stop_requested = False
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("停止中..." if stopping else "运行中..." if running else "运行")
        self._stop_btn.setEnabled(running and not stopping)
        self._reset_btn.setEnabled(not running)
        self._tool_combo.setEnabled(not running)

    def _apply_control_special_mode(self) -> None:
        """按当前选中轨道设置特征点模式，Halo/NRHO 使用 xdot=zdot=0。"""
        source = self._selected_orbit_artifact()
        widget = self._param_widgets.get("special_mode")
        if source is None or not isinstance(widget, QComboBox):
            return
        orbit_type = str(source.orbit_type or source.extra.get("orbit_type", "")).upper()
        mode = 2 if orbit_type in {"HALO", "NRHO"} else 1
        widget.setEnabled(False)
        index = widget.findData(mode)
        if index >= 0:
            widget.setCurrentIndex(index)

    def _apply_propagation_defaults(self) -> None:
        """轨道预报初值预填：选中含 GCRS 星历的工件末端状态（#389）。

        initial_state 预填为末端 [位置; 速度]（km, km/s），epoch 预填为末端
        时刻；无选中或所选工件无星历时保持面板当前值（可纯手填）。
        """
        end = self._selected_ephemeris_end_state()
        if end is None:
            return
        state, epoch_dt = end
        widget = self._param_widgets.get("initial_state")
        if widget is not None and widget.property("__params_panel_kind") == "list_float":
            for sb, v in zip(widget.findChildren(QDoubleSpinBox), state, strict=False):
                sb.setValue(float(v))
        epoch_widget = self._param_widgets.get("epoch")
        if isinstance(epoch_widget, QDateTimeEdit):
            if epoch_dt is None:
                self._log.append_log("历元预填失败（SPICE 时间换算不可用），请手填起始历元")
            else:
                epoch_widget.setDateTime(epoch_dt)

    def _selected_ephemeris_end_state(self) -> tuple[list[float], Any] | None:
        """返回选中工件的星历末端 (6 维状态, QDateTime) | None。

        支持三类源：design_orbit（extra["ephemeris"]，速度存 m/s）、
        control_orbit（extra 顶层，速度 km/s）、orbit_propagation（自身可继续
        向后预报）。坐标序不一致或数据不全时返回 None。
        """
        if len(self._selected_artifact_ids) != 1:
            return None
        artifact = self._project.get_by_id(self._selected_artifact_ids[0])
        if artifact is None:
            return None
        pos = vel = times = None
        if artifact.source_tool in _CR3BP_ORBIT_TOOLS:
            eph = artifact.extra.get("ephemeris") or {}
            pos = eph.get("position_km")
            velocity_mps = eph.get("velocity_mps")
            vel = (
                np.asarray(velocity_mps, dtype=float) / 1000.0
                if velocity_mps is not None
                else None
            )
            times = eph.get("times_et")
        elif artifact.source_tool in ("control_orbit", "orbit_propagation"):
            pos = artifact.extra.get("position_km")
            vel = artifact.extra.get("velocity_km_s")
            times = artifact.extra.get("times_et")
        if pos is None or vel is None or times is None or len(times) == 0:
            return None
        pos = np.asarray(pos, dtype=float)
        vel = np.asarray(vel, dtype=float)
        if pos.ndim != 2 or vel.shape != pos.shape:
            return None
        epoch_dt = self._et_to_qdatetime(float(np.asarray(times)[-1]))
        return list(pos[-1]) + list(vel[-1]), epoch_dt

    @staticmethod
    def _et_to_qdatetime(et: float):
        """ET 秒 → QDateTime；SPICE 不可用（内核缺失等）时返回 None。"""
        try:
            from e2m2e.data.kernels._spice_loader import get_spiceypy
            from e2m2e.data.kernels.manager import SPICEManager

            SPICEManager()._ensure_leapseconds()
            iso = get_spiceypy().et2utc(et, "ISOC", 0)
            return QDateTime.fromString(iso, "yyyy-MM-ddTHH:mm:ss")
        except Exception:  # noqa: BLE001 -- 历元预填失败不阻断预报（可手填）
            return None

    def _on_stop_run(self) -> None:
        """请求停止当前任务；同步算法调用返回前不会强制终止线程。"""
        worker = self._worker
        if worker is None or not self._stop_btn.isEnabled():
            return
        worker.requestInterruption()
        self._stop_requested = True
        self._set_run_controls(running=True, stopping=True)
        self._log.append_log("已请求停止，等待当前数值调用返回...")
        self._status_bar.showMessage("正在停止运行...", _STATUS_MSG_TIMEOUT_MS)

    def _consume_stop_request(self) -> bool:
        """在完成或报错信号处理前消费停止请求，阻止结果副作用。"""
        if not self._stop_requested:
            return False
        self._on_worker_cancelled()
        return True

    def _on_worker_cancelled(self) -> None:
        """当前数值调用返回后丢弃已取消任务的结果。"""
        self._stop_requested = False
        self._set_run_controls(running=False)
        self._worker = None
        self._log.append_log("运行已停止，结果未保存")
        self._status_bar.showMessage("运行已停止", _STATUS_MSG_TIMEOUT_MS)

    def _has_active_task(self) -> bool:
        """任务尚在运行、停止等待或完成信号排队时均视为活跃。"""
        worker = self._worker
        return worker is not None and (
            worker.isRunning() or self._stop_requested or self._stop_btn.isEnabled()
        )

    def _reject_if_task_active(self) -> bool:
        if not self._has_active_task():
            return False
        self._status_bar.showMessage(
            "已有任务运行，请等待完成或停止当前任务", _STATUS_MSG_TIMEOUT_MS
        )
        return True

    def _add_group_header(self, layout: QGridLayout, title: str, row: int) -> int:
        """在参数面板插入组表头（加粗标题 + 分隔线），返回下一行号。"""
        header = QLabel(title)
        header.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(header, row, 0, 1, 3)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep, row + 1, 0, 1, 3)
        self._group_headers[title] = (header, sep)
        return row + 2

    def _build_tool_params(self, tool_key: str) -> None:
        """为指定工具构建参数面板（分组展示：组标题 + 字段行）。"""
        spec: ToolSpec | None = TOOL_REGISTRY.get(tool_key)
        if spec is None or spec.request_model is None:
            return

        # 清空旧控件：替换 scroll area 的 widget。QScrollArea.setWidget 会销毁旧
        # container（连同其 layout 与子控件），QGridLayout 的 rowCount/rowStretch
        # 残留也一并重置——避免跨工具切换残留空行造成底部大段空白。
        self._param_widgets = {}
        self._param_rows = {}
        self._group_headers = {}
        self._group_fields = {}
        new_container = QWidget()
        new_layout = QGridLayout(new_container)
        new_layout.setContentsMargins(0, 0, 0, 0)
        # 多余宽度归标签列：数字框/下拉保持内容宽度（数字就几位，拉长了空）
        new_layout.setColumnStretch(0, 1)
        self._param_container = new_container
        self._param_container_layout = new_layout
        if self._param_scroll is not None:
            self._param_scroll.setWidget(new_container)
        layout = new_layout

        # 生成控件
        self._param_widgets = build_params_from_model(spec.request_model)

        if tool_key == "control_orbit":
            # input_ephemeris / input_record_id 由选中 Artifact 注入（后者
            # issue #375 谱系直连），不在 UI 暴露；mu 同样由源 Artifact 注入
            # （source_mu），面板编辑无效（ControlOrbitRequest 的 mu 仅为响应
            # 透传字段，算法层不消费）。上游默认控制时长面向多年星历，覆盖
            # 不了 GUI 默认设计的短弧，故在 GUI 层覆盖为短弧默认值。
            for hidden in ("input_ephemeris", "input_record_id", "mu"):
                self._param_widgets.pop(hidden, None)
            for name, default in _CONTROL_ORBIT_GUI_DEFAULTS.items():
                widget = self._param_widgets.get(name)
                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(default)
            self._apply_control_special_mode()
        elif tool_key == "orbit_family_generation":
            # sampling_mode 各族首版只有唯一规则，不暴露（模型自动填默认）。
            sampling_mode = self._param_widgets.pop("sampling_mode", None)
            if sampling_mode is not None:
                sampling_mode.setParent(None)
        elif tool_key == "orbit_propagation":
            # force_config：预设（留空=默认三体）+ 可选 JSON 文本框，不做勾选式
            # Optional 包装与结构化表单（#389 决策）；非法 JSON 在运行前拦截。
            fc_widget = self._param_widgets.get("force_config")
            if isinstance(fc_widget, QWidget):
                unwrapped = _unwrap_optional_widget(fc_widget)
                assert isinstance(unwrapped, QLineEdit)
                unwrapped.setPlaceholderText(
                    'JSON 力模型配置（留空 = 默认三体：地球点质量 + 月球/太阳第三体）'
                )
                self._param_widgets["force_config"] = unwrapped

        # G3: design_orbit 的 orbit_type -> QComboBox
        if tool_key == "design_orbit" and "orbit_type" in self._param_widgets:
            self._replace_orbit_type_with_combo(spec.request_model)
        elif tool_key == "orbit_family_generation" and "orbit_type" in self._param_widgets:
            self._replace_family_orbit_type_with_combo(spec.request_model)

        # 分组顺序：_PARAM_GROUPS 声明顺序 + 未分组字段归入"其他"
        group_specs = _PARAM_GROUPS.get(tool_key, ())
        grouped = [f for _, fields in group_specs for f in fields]
        ungrouped = [n for n in self._param_widgets if n not in grouped]
        all_groups: list[tuple[str, tuple[str, ...]]] = list(group_specs)
        if ungrouped:
            all_groups.append(("其他", tuple(ungrouped)))

        # 显示字段：QGridLayout 3 列（label / 控件 / 单位下拉），label 与控件
        # 同行、单位下拉并入控件行。_param_rows 契约（label, widget, unit_combo）不变。
        row = 0
        for title, fields in all_groups:
            present = [n for n in fields if n in self._param_widgets]
            if not present:
                continue
            row = self._add_group_header(layout, title, row)
            self._group_fields[title] = present
            for name in present:
                widget = self._param_widgets[name]
                options = get_field_units(name)
                label_text = (
                    _field_label_with_unit(name, options[0].label)
                    if options
                    else _DESIGN_ORBIT_LABELS.get(name, name)
                )
                label_widget = QLabel(label_text)
                layout.addWidget(label_widget, row, 0)
                # 宽控件（历元/JSON 文本/轨道类型下拉/Optional 包装行）跨列
                # 1-2：标签列与单位下拉列占去大半宽度后，列 1 剩余预算放不下
                # 它们的完整文本；这些行都没有单位下拉（options 为空），跨列
                # 无冲突。竖排数字框（list_float）不跨——跨了会被拉宽。
                spans_two_cols = options is None and (
                    isinstance(widget, (QDateTimeEdit, QLineEdit))
                    or widget.property("__params_panel_kind") == "optional"
                    or name == "orbit_type"
                )
                layout.addWidget(widget, row, 1, 1, 2 if spans_two_cols else 1)
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
        elif tool_key == "orbit_propagation":
            # duration 默认 30 天（对齐设计短弧）；初值预填选中星历工件的末端状态
            self._set_duration_display("日", 30.0)
            self._apply_propagation_defaults()
        elif tool_key == "orbit_family_generation":
            family_widget = self._param_widgets.get("orbit_type")
            if isinstance(family_widget, QComboBox):
                family_combo: QComboBox = family_widget
                family_combo.currentIndexChanged.connect(self._on_family_type_changed)
                self._on_family_type_changed(family_combo.currentIndex())
            # 切平动点时同步族参数范围约束与默认值（如 Halo L2 默认 30000 超出 L1 范围）
            point_widget = self._param_widgets.get("libration_point")
            if isinstance(point_widget, QComboBox):
                point_combo: QComboBox = point_widget
                point_combo.currentIndexChanged.connect(self._on_family_point_changed)

        # 数字框收紧宽度（见 _PARAM_SPINBOX_MAX_WIDTH）；历元 QDateTimeEdit
        # 不是"数字没那么长"的场景，保持完整日期时间宽度
        for sb in new_container.findChildren(QAbstractSpinBox):
            if not isinstance(sb, QDateTimeEdit):
                sb.setMaximumWidth(_PARAM_SPINBOX_MAX_WIDTH)

        layout.setRowStretch(row, 1)

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

    def _replace_family_orbit_type_with_combo(self, model_class: type) -> None:
        """族生成工具的 orbit_type 替换为七族下拉（机制同 design_orbit 的 G3）。"""
        field = model_class.model_fields.get("orbit_type")
        if field is None:
            return
        combo = QComboBox()
        combo.addItems(list(FAMILY_TYPES))
        if field.description:
            combo.setToolTip(field.description)
        old = self._param_widgets.get("orbit_type")
        self._param_widgets["orbit_type"] = combo
        if old is not None:
            old.setParent(None)

    def _on_family_type_changed(self, index: int) -> None:
        """切族类型：重建平动点下拉 + 填该族默认值 + 只显示该族参数字段。"""
        if self._current_tool_key != "orbit_family_generation":
            return
        orbit_type_widget = self._param_widgets.get("orbit_type")
        if not isinstance(orbit_type_widget, QComboBox):
            return
        family_combo: QComboBox = orbit_type_widget
        family_type = family_combo.currentText()
        self._rebuild_family_libration_points(family_type)
        apply_family_type_defaults(self._param_widgets, family_type)
        # 切族但平动点未变时下拉不发信号，这里补一次约束/默认同步（幂等）
        point_widget = self._param_widgets.get("libration_point")
        if isinstance(point_widget, QComboBox):
            point = point_widget.currentData()
            if isinstance(point, int):
                sync_family_point_params(self._param_widgets, family_type, point)
        self._sync_family_visible_fields(family_type)

    def _on_family_point_changed(self, index: int) -> None:
        """族面板切平动点：刷新范围约束，超范围的当前值替换为该点默认值。"""
        if self._current_tool_key != "orbit_family_generation":
            return
        family_widget = self._param_widgets.get("orbit_type")
        point_widget = self._param_widgets.get("libration_point")
        if not isinstance(family_widget, QComboBox) or not isinstance(point_widget, QComboBox):
            return
        point = point_widget.itemData(index)
        if not isinstance(point, int):
            return
        sync_family_point_params(self._param_widgets, family_widget.currentText(), point)

    def _rebuild_family_libration_points(self, family_type: str) -> None:
        """按族重建 libration_point 下拉项（共线族 L1/L2，Lissajous 加 L3，三角族 L4/L5）。"""
        widget = self._param_widgets.get("libration_point")
        if not isinstance(widget, QComboBox):
            return
        point_combo: QComboBox = widget
        point_combo.blockSignals(True)
        point_combo.clear()
        for point in family_libration_points(family_type):
            point_combo.addItem(f"L{point}", point)
        point_combo.blockSignals(False)

    def _sync_family_visible_fields(self, family_type: str) -> None:
        """按族显示/隐藏族参数字段，并把解包后的控件同步进布局。

        公共字段（orbit_type/n_orbits）始终显示；平动点字段仅共线/三角族
        （DRO 为月心族、无平动点，行隐藏）。不同族共用同名字段（如 Halo/Axial
        与三角族共用 max_amplitude_km）时保持可见。
        """
        branch_fields = FAMILY_TYPE_FIELDS.get(family_type, set())
        always_visible = {"orbit_type", "n_orbits"}
        if family_libration_points(family_type):
            always_visible.add("libration_point")
        for name in list(self._param_rows):
            label, widget, unit_combo = self._param_rows[name]
            current = self._param_widgets.get(name)
            if current is not None and current is not widget:
                self._replace_row_widget(name, current)
                label, widget, unit_combo = self._param_rows[name]
            visible = name in always_visible or name in branch_fields
            label.setVisible(visible)
            widget.setVisible(visible)
            if unit_combo is not None:
                unit_combo.setVisible(visible)

    def _sync_visible_fields(self, orbit_type: str) -> None:
        """按分支字段集显示/隐藏参数行，并把解包后的控件同步进布局。

        整组字段全隐藏时同步隐藏组表头（如 ELFO 分支下"修正参数"仍可见，
        "形状参数"组内只留该分支字段）。
        """
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
        # 组表头：组内字段全部隐藏时同步隐藏表头与分隔线。
        for title, fields in self._group_fields.items():
            header_pair = self._group_headers.get(title)
            if header_pair is None:
                continue
            any_visible = any(
                name in self._param_rows and not self._param_rows[name][0].isHidden()
                for name in fields
            )
            header_pair[0].setVisible(any_visible)
            header_pair[1].setVisible(any_visible)

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
        """单位下拉切换：换算控件显示值 + 更新 label 后缀。

        widget 可能是 Optional 容器（未 apply 前）、list[float] 容器或解包后的
        spinbox；set_spinbox_unit 对三种形态统一处理。
        """
        row = self._param_rows.get(field_name)
        if row is None:
            return
        label, widget, unit_combo = row
        if unit_combo is None:
            return
        unit = unit_combo.currentText()
        set_spinbox_unit(widget, field_name, unit)
        label.setText(_field_label_with_unit(field_name, unit))

    def _apply_duration_default_month(self) -> None:
        """把 duration 控件单位切到"月"并设为 1（= 1/12 年标准值）。

        模型 ``DesignOrbitRequest.duration`` 的 default=1.0（年）是上游契约，不改；
        此处仅在 GUI 层覆盖显示，让短弧设计更顺手。duration 不在
        ``ORBIT_TYPE_DEFAULTS``，切轨道类型不会重置该覆盖。
        """
        self._set_duration_display("月", 1.0)

    def _set_duration_display(self, unit_label: str, value: float) -> None:
        """把 duration 控件切到指定显示单位并设值（值按该单位解释）。"""
        row = self._param_rows.get("duration")
        if row is None:
            return
        _label, widget, unit_combo = row
        sb = widget if isinstance(widget, QDoubleSpinBox) else widget.findChild(QDoubleSpinBox)
        if unit_combo is None or sb is None:
            return
        idx = unit_combo.findText(unit_label)
        if idx < 0:
            return
        unit_combo.setCurrentIndex(idx)
        sb.setValue(value)

    # -- 信号槽 -------------------------------------------------------------

    def _ensure_arrays_loaded(self, artifact: Artifact) -> None:
        """catalog 记录懒加载（完整内容经 catalog_get 取回，失败仅记日志）。"""
        if (
            artifact.state_data is None
            and artifact.record_id
            and not self._catalog.load_arrays(artifact)
        ):
            self._log.append_log(f"记录数据加载失败: {artifact.label}（记录缺失或损坏）")

    def _on_artifact_clicked(self, artifact_id: str) -> None:
        artifact = self._project.get_by_id(artifact_id)
        if artifact is None:
            return
        self._select_artifact(artifact_id, render=True)

    def _select_artifact(self, artifact_id: str, *, render: bool = True) -> None:
        """选中单个 Artifact：记录懒加载 → 详情面板 → 画布。"""
        artifact = self._project.get_by_id(artifact_id)
        if artifact is None:
            return
        # Issue #375: catalog 记录懒加载（完整内容经 catalog_get 取回）
        self._ensure_arrays_loaded(artifact)
        if artifact.state_data is not None:
            self._warn_missing_mu(artifact)
            self._warn_missing_ephemeris(artifact)
        self._selected_artifact_ids = [artifact_id]
        if self._current_tool_key == "control_orbit":
            self._apply_control_special_mode()
        elif self._current_tool_key == "orbit_propagation":
            self._apply_propagation_defaults()
        self._update_plot_content_controls()
        self._update_detail_panel(artifact)
        if render and artifact.state_data is not None:
            self._render_canvas()

    def _update_detail_panel(self, artifact: Artifact | None) -> None:
        """刷新记录详情面板（谱系解析：上游标签 + 断链标记）。"""
        if artifact is None or not artifact.record_id:
            self._detail_panel.clear()
            return
        upstream = self._project.find_upstream(artifact)
        self._detail_panel.show_record(
            artifact,
            upstream_label=upstream.label if upstream is not None else None,
            broken_lineage=self._project.has_broken_lineage(artifact),
        )

    def _on_artifacts_multi_selected(self, artifact_ids: list[str]) -> None:
        # Issue #339: 多选分支补上懒加载（现状缺失，见审查意见）
        for aid in artifact_ids:
            artifact = self._project.get_by_id(aid)
            if artifact is None:
                continue
            self._ensure_arrays_loaded(artifact)
            self._warn_missing_mu(artifact)
            self._warn_missing_ephemeris(artifact)
        self._selected_artifact_ids = list(artifact_ids)
        self._update_plot_content_controls()
        if artifact_ids:
            first = self._project.get_by_id(artifact_ids[0])
            self._update_detail_panel(first)
        self._render_canvas()

    def _on_run(self) -> None:
        if self._reject_if_task_active():
            return
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
        elif tool_key == "orbit_propagation":
            self._run_propagation()

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
        self._set_run_controls(running=True)

        self._worker = OrbitDesignWorker(
            orbit_type=orbit_type,
            params=params,
            kernel_dir=kernel_dir,
            catalog_dir=str(self._catalog_dir),
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_design_finished)
        self._worker.error.connect(self._on_design_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _run_control_orbit(self) -> None:
        source = self._selected_orbit_artifact()
        if source is None:
            self._status_bar.showMessage("请先在左侧项目树中选择一条轨道", _STATUS_MSG_TIMEOUT_MS)
            return
        # 记录懒加载（谱系输入与时长校验都需要星历段时间轴）
        self._ensure_arrays_loaded(source)
        ephemeris_data = source.extra.get("ephemeris")

        spec = TOOL_REGISTRY["control_orbit"]
        model = spec.request_model
        if model is None:
            return
        self._apply_control_special_mode()
        params = collect_params(self._param_widgets, model)
        params.pop("input_ephemeris", None)  # 防御：理论上已隐藏
        params.pop("input_record_id", None)
        # Issue #375: 库中记录直连站保输入（Facade 取星历段并写谱系
        # source_record_id，design→control 链式不经文件倒手）；无记录的产物
        # 回退 input_ephemeris（内存星历重建 EphemerisTable）。
        if source.record_id and source.extra.get("has_ephemeris"):
            params["input_record_id"] = source.record_id
        elif not ephemeris_data:
            self._status_bar.showMessage("所选轨道没有星历数据，需重新设计", _STATUS_MSG_TIMEOUT_MS)
            return

        # 校验仿真时长不超出源星历覆盖：控制律的目标点/反馈弧都取自标称星历，
        # 超出覆盖时控制律无解（默认 30 天/次 × 119 次 + 28 天反馈 ≈ 3598 天，
        # 而 GUI 设计默认星历仅 30 天 → 蒙特卡洛样本必然全部失败、Δv=0）。
        times_et = (ephemeris_data or {}).get("times_et")
        if times_et is not None and len(times_et) > 1:
            span_days = float(times_et[-1] - times_et[0]) / 86400.0
            interval = float(params.get("control_interval", 30.0))
            feedback = float(params.get("feedback_arc", 28.0))
            n_ctrl = int(params.get("num_controls", 120))
            sim_days = (n_ctrl - 2) * interval + feedback
            if sim_days > span_days:
                msg = (
                    f"仿真时长 {sim_days:.1f} 天（{n_ctrl - 2} 次机动 × "
                    f"{interval} 天/次 + 反馈弧 {feedback} 天）超出源星历覆盖 "
                    f"{span_days:.1f} 天，轨道保持必然全部失败。"
                    f"请减小控制间隔/次数，或设计更长时长的标称轨道。"
                )
                self._status_bar.showMessage(msg, _STATUS_MSG_TIMEOUT_MS)
                self._log.append_log(f"参数错误: {msg}")
                return

        kernel_dir = self._detect_kernel_dir() or None
        self._log.clear()
        self._log.append_log(f"轨道保持: 源 {source.label}")
        self._status_bar.showMessage("正在仿真轨道保持（蒙特卡洛）...")
        self._set_run_controls(running=True)

        self._worker = ControlOrbitWorker(
            ephemeris_data=ephemeris_data,
            params=params,
            source_mu=source.extra.get("mu"),
            kernel_dir=kernel_dir,
            catalog_dir=str(self._catalog_dir),
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_control_finished)
        self._worker.error.connect(self._on_control_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _run_propagation(self) -> None:
        """运行轨道预报（#389）：面板收集参数，JSON 力模型配置运行前拦截。"""
        spec = TOOL_REGISTRY["orbit_propagation"]
        model = spec.request_model
        if model is None:
            return
        try:
            params = collect_params(self._param_widgets, model)
        except ValueError as exc:
            self._status_bar.showMessage(str(exc), _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"参数错误: {exc}")
            return
        force_config = params.get("force_config")
        if isinstance(force_config, str):
            text = force_config.strip()
            if not text:
                params.pop("force_config", None)  # 留空 = 默认三体
            else:
                try:
                    params["force_config"] = json.loads(text)
                except json.JSONDecodeError as exc:
                    msg = f"力模型配置 JSON 无效: {exc}"
                    self._status_bar.showMessage(msg, _STATUS_MSG_TIMEOUT_MS)
                    self._log.append_log(f"参数错误: {msg}")
                    return
        elif force_config is None:
            params.pop("force_config", None)

        kernel_dir = self._detect_kernel_dir() or None
        self._log.clear()
        self._status_bar.showMessage("正在轨道预报...")
        self._set_run_controls(running=True)

        self._worker = PropagationWorker(
            params=params, kernel_dir=kernel_dir, parent=self
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_propagation_finished)
        self._worker.error.connect(self._on_propagation_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_propagation_finished(self, result: PropagationResultData) -> None:
        """预报完成：星历落盘 output/propagation/ 后重扫非 catalog 分区并选中。"""
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        try:
            json_path = save_propagation_result(result, OUTPUT_DIR)
        except Exception as exc:  # noqa: BLE001 -- 落盘失败给明确提示，不崩
            self._log.append_log(f"预报结果落盘失败: {exc}")
            self._status_bar.showMessage("轨道预报失败", _STATUS_MSG_TIMEOUT_MS)
            return
        self._log.append_log(
            f"轨道预报完成: {result.n_points} 点，"
            f"时长 {result.duration_sec / 86400.0:.2f} 天（{json_path.name}）"
        )
        self._reload_from_catalog()
        # discovery 用文件名茎作 artifact_id，落盘后即可按 id 选中
        if self._project.get_by_id(json_path.stem) is not None:
            self._select_artifact(json_path.stem)
        self._status_bar.showMessage("轨道预报完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_propagation_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("轨道预报失败", _STATUS_MSG_TIMEOUT_MS)

    def _run_family_generation(self) -> None:
        """运行轨道族生成（工具选择器入口，参数来自面板）。"""
        spec = TOOL_REGISTRY["orbit_family_generation"]
        model = spec.request_model
        if model is None:
            return
        family_widget = self._param_widgets.get("orbit_type")
        family_type = (
            family_widget.currentText() if isinstance(family_widget, QComboBox) else "Halo"
        )
        try:
            params = collect_params(self._param_widgets, model)
        except ValueError as exc:
            self._status_bar.showMessage(str(exc), _STATUS_MSG_TIMEOUT_MS)
            self._log.append_log(f"参数错误: {exc}")
            return
        # 5.7.1 起 FamilyGenerationRequest 拒绝跨族字段（含 None），过滤到当前族
        params = _family_request_params(params, family_type)
        params["orbit_type"] = family_type

        self._log.clear()
        self._status_bar.showMessage(f"正在生成 {family_type} 轨道族...")
        self._set_run_controls(running=True)

        self._worker = FamilyOrbitWorker(
            params=params, catalog_dir=str(self._catalog_dir), parent=self
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_family_finished)
        self._worker.error.connect(self._on_family_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_family_finished(self, result: FamilyResultData) -> None:
        """族生成完成：产物已自动入库，重查清单并选中新记录。"""
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)

        completion = f"轨道族生成完成: {result.n_orbits} 条 {result.orbit_type} 轨道" + (
            f"（L{result.libration_point}）" if result.libration_point else ""
        )
        if result.status_message:
            # 软失败（部分族）：展示上游状态消息说明未满额原因
            completion += f"；{result.status_message}"
        self._log.append_log(completion)
        self._reload_from_catalog()
        self._select_record_after_run(result.record_id, fallback_log="族记录未入库")
        self._status_bar.showMessage("轨道族生成完成", _STATUS_MSG_TIMEOUT_MS)

    def _select_record_after_run(self, record_id: str | None, *, fallback_log: str) -> None:
        """计算完成后选中新入库的记录（清单已重查，record_id 即主键）。"""
        if record_id and self._project.get_by_id(record_id) is not None:
            self._select_artifact(record_id)
            return
        if record_id is None:
            self._log.append_log(fallback_log)
        elif self._catalog_filters:
            self._log.append_log(f"新记录 {record_id} 不满足当前过滤条件，未在项目树中显示")

    def _on_family_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
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
        """删除 Artifact：库记录走 catalog_delete（不可撤销，先确认），遗留分区仅移出内存。"""
        if not artifact_ids:
            return
        record_backed = [
            aid
            for aid in artifact_ids
            if (a := self._project.get_by_id(aid)) is not None and a.record_id
        ]
        if record_backed:
            from PyQt6.QtWidgets import QMessageBox

            answer = QMessageBox.question(
                self,
                "删除记录",
                f"将永久删除 {len(record_backed)} 条轨道库记录（含数据文件，不可撤销）。继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        removed = 0
        for aid in artifact_ids:
            artifact = self._project.get_by_id(aid)
            if artifact is None:
                continue
            if artifact.record_id:
                try:
                    self._catalog.delete(artifact.record_id)
                    removed += 1
                except OrbitError as exc:
                    self._log.append_log(f"删除记录失败 {artifact.label}: {exc.message}")
            else:
                self._legacy_artifacts = [a for a in self._legacy_artifacts if a.artifact_id != aid]
                removed += 1
        self._reload_from_catalog()
        # 从画布选中集剔除已删项
        self._selected_artifact_ids = [
            aid for aid in self._selected_artifact_ids if aid not in artifact_ids
        ]
        self._update_detail_panel(None)
        self._render_canvas()
        self._status_bar.showMessage(f"已删除 {removed} 条记录", _STATUS_MSG_TIMEOUT_MS)

    # -- 轨道库交互（过滤 / 标注 / 提升 / 导出，issue #375）-----------------

    def _on_filters_changed(self, filters: dict) -> None:
        """过滤栏变化：重查库并重建树（选中集随之失效，画布清空）。"""
        self._catalog_filters = dict(filters)
        self._selected_artifact_ids = []
        self._reload_from_catalog()
        self._update_detail_panel(None)
        self._render_canvas()

    def _on_tag_requested(self, record_id: str, tags: list, note: str) -> None:
        """详情面板保存标注：catalog_tag 落库后重查清单并保持选中。"""
        try:
            self._catalog.tag(record_id, tags, note)
        except OrbitError as exc:
            self._log.append_log(f"标注保存失败: {exc.message}")
            self._status_bar.showMessage("标注保存失败", _STATUS_MSG_TIMEOUT_MS)
            return
        self._reload_from_catalog()
        self._select_artifact(record_id, render=False)
        self._status_bar.showMessage("标注已保存", _STATUS_MSG_TIMEOUT_MS)

    def _on_promote_requested(self, record_id: str, member_index: int) -> None:
        """详情面板提升族成员：catalog_promote 生成独立记录并选中。"""
        try:
            new_record_id = self._catalog.promote_member(record_id, member_index)
        except OrbitError as exc:
            self._log.append_log(f"成员提升失败: {exc.message}")
            self._status_bar.showMessage("成员提升失败", _STATUS_MSG_TIMEOUT_MS)
            return
        self._reload_from_catalog()
        self._select_artifact(new_record_id)
        self._status_bar.showMessage(
            f"成员 {member_index} 已提升为独立记录", _STATUS_MSG_TIMEOUT_MS
        )

    def _on_export_requested(self) -> None:
        """导出教学案例包：当前过滤子集经 catalog_export 打包（zip 或目录）。"""
        dest, selected = QFileDialog.getSaveFileName(
            self,
            "导出教学案例包",
            "orbit_cases.zip",
            "案例包 zip (*.zip);;案例包目录 (*)",
        )
        if not dest:
            return
        try:
            count = self._catalog.export(self._catalog_filters, dest)
        except OrbitError as exc:
            self._log.append_log(f"导出失败: {exc.message}")
            self._status_bar.showMessage("导出失败", _STATUS_MSG_TIMEOUT_MS)
            return
        kind = "zip 包" if selected.startswith("案例包 zip") else "目录"
        self._log.append_log(f"教学案例包已导出（{kind}）: {dest}，共 {count} 条记录")
        self._status_bar.showMessage(f"已导出 {count} 条记录 → {dest}", _STATUS_MSG_TIMEOUT_MS)

    def _trigger_control_orbit_from_tree(self, artifact_ids: list[str]) -> None:
        """右键 orbit → 轨道保持：选中该 Artifact + 切到 control_orbit 工具。

        不自动运行（给用户在参数面板调参的机会），与 #348 工具选择器范式一致。
        """
        if self._reject_if_task_active() or not artifact_ids:
            return
        orbit_id = artifact_ids[0]
        artifact = self._project.get_by_id(orbit_id)
        if artifact is None or artifact.artifact_type != "orbit":
            return
        self._ensure_arrays_loaded(artifact)
        self._selected_artifact_ids = [orbit_id]
        for i in range(self._tool_combo.count()):
            if self._tool_combo.itemData(i) == "control_orbit":
                self._tool_combo.setCurrentIndex(i)
                break
        if self._current_tool_key == "control_orbit":
            self._apply_control_special_mode()
        self._status_bar.showMessage("已选中轨道，调整参数后点运行", _STATUS_MSG_TIMEOUT_MS)

    def _trigger_stability_from_tree(self, artifact_ids: list[str]) -> None:
        """右键 orbit → 查看稳定性：后台分析选中轨道，结果弹对话框 + 落盘。

        稳定性分析用 CR3BP 周期轨道（Artifact.state_data），无需 SPICE。
        mu 缺失（旧 Artifact）时由 FacadeBridge 用默认地月系统兜底。
        """
        if self._reject_if_task_active() or not artifact_ids:
            return
        orbit_id = artifact_ids[0]
        artifact = self._project.get_by_id(orbit_id)
        if artifact is None or artifact.artifact_type != "orbit":
            self._status_bar.showMessage("请先在左侧项目树中选择一条轨道", _STATUS_MSG_TIMEOUT_MS)
            return
        self._ensure_arrays_loaded(artifact)
        if artifact.state_data is None:
            self._status_bar.showMessage("所选记录没有轨道数据", _STATUS_MSG_TIMEOUT_MS)
            return

        self._stability_source_label = artifact.label
        self._log.append_log(f"稳定性分析: {artifact.label}")
        self._status_bar.showMessage("正在分析稳定性...")
        self._set_run_controls(running=True)
        self._worker = StabilityWorker(
            states=artifact.state_data,
            times=artifact.times,
            mu=artifact.extra.get("mu"),
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_stability_finished)
        self._worker.error.connect(self._on_stability_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_stability_finished(self, result: StabilityResultData) -> None:
        """稳定性分析完成：落盘 JSON + 弹结果对话框。"""
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        label = getattr(self, "_stability_source_label", "orbit")
        try:
            json_path = save_stability_result(result, OUTPUT_DIR, orbit_label=label)
            self._log.append_log(f"稳定性结果已保存: {json_path.name}")
        except Exception as exc:  # noqa: BLE001
            self._log.append_log(f"稳定性结果落盘失败: {exc}")
        self._show_stability_dialog(result, label)
        self._status_bar.showMessage("稳定性分析完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_stability_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
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
        """设计完成：产物已自动入库，重查清单并选中新记录。"""
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)

        self._log.append_log(f"设计完成: {result.orbit_type}, C_J={result.cr3bp_jacobi:.6f}")
        if result.record_id:
            self._log.append_log(f"已入轨道库: {result.record_id}")
        self._reload_from_catalog()
        self._select_record_after_run(result.record_id, fallback_log="产物未入轨道库")
        self._status_bar.showMessage(f"{result.orbit_type} 设计完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_design_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        # G1: 恢复按钮状态
        self._set_run_controls(running=False)

        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("设计失败", _STATUS_MSG_TIMEOUT_MS)

    def _on_control_finished(self, result: ControlResultData) -> None:
        """站保完成：产物已自动入库（谱系指向被控记录），重查清单并选中新记录。"""
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)

        total_dv = float(np.sum(result.maneuvers_delta_v_mps))
        self._log.append_log(
            f"轨道保持完成: 总Δv={total_dv:.2f} m/s, 失败 {result.num_failed} 样本"
        )
        self._reload_from_catalog()
        self._select_record_after_run(result.record_id, fallback_log="站保全样本失败，未产生库记录")
        self._status_bar.showMessage("轨道保持完成", _STATUS_MSG_TIMEOUT_MS)

    def _on_control_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        self._log.append_log(f"错误:\n{error_msg}")
        self._status_bar.showMessage("轨道保持失败", _STATUS_MSG_TIMEOUT_MS)

    # -- 渲染 ---------------------------------------------------------------

    # Issue #339: CanvasState 流 -- 单一状态源 + render() 单入口

    def _warn_missing_mu(self, artifact: Artifact) -> None:
        """旧 Artifact 无 mu 时提示：地月/L 点标注不可用（计划决策 3）。"""
        if artifact.state_data is not None and artifact.extra.get("mu") is None:
            self._log.append_log(f"{artifact.label} 缺少 mu 参数，跳过地月标注")

    def _warn_missing_ephemeris(self, artifact: Artifact) -> None:
        """轨道设计产物（design_orbit）无标称星历时提示：画布只能画初猜。

        #359 US 10：星历缺失要明确告知，而非画布静默只画初猜。design_orbit
        正常总会产出星历，此分支仅防御异常/旧产物；catalog_promote 提升的
        族成员天然只有 CR3BP 段（无星历），同样适用。
        """
        if artifact.source_tool in _CR3BP_ORBIT_TOOLS and not artifact.extra.get("ephemeris"):
            self._log.append_log(f"该轨道无标称星历，画布只能画初猜: {artifact.label}")

    def _artifact_for_id(self, artifact_id: str) -> dict | None:
        """返回画布渲染所需的 Artifact 数据（不含 e2m2e 类型）。

        经 canvas.set_artifacts_provider() 注入；渲染前由 canvas.sync_state()
        调用，返回内存数组，不从磁盘/NPZ 重读。

        契约（#359）：四份轨迹数据显式平级暴露给画布，不嵌套、不靠隐式 fallback。
        画布按 ``CanvasState.plot_content`` 选择消费哪一槽。

        - ``initial_guess_states``: CR3BP 周期轨道（无量纲会合系，质心归一）。
          仅 design_orbit 产物有；control_orbit 与历史 Artifact 为 None。
        - ``initial_guess_times``: 初猜无量纲会合系时间（旋转角 θ=t），
          惯性系近似视图用。
        - ``ephemeris_synodic``: 星历会合系位置（质心归一，已减 μ；ADR 0013）。
          design_orbit 的标称星历（从 extra["ephemeris"]）与 control_orbit 的
          受控星历（state_data 已在 facade_bridge 减过 μ）共用此槽。
        - ``ephemeris_position_km``: 星历惯性系 GCRS km 位置。
        - ``ephemeris_times_et``: 物理时间（ET 秒，与星历槽同源）。
        - ``family_states`` / ``family_times``: 轨道族（无量纲会合系）及其
          无量纲时间，惯性系近似视图用。
        """
        a = self._project.get_by_id(artifact_id)
        if a is None or a.state_data is None:
            return None
        mu = a.extra.get("mu")
        data: dict = {
            "label": a.label,
            "mu": mu,
            "initial_guess_states": None,
            "initial_guess_times": None,
            "ephemeris_synodic": None,
            "ephemeris_position_km": None,
            "ephemeris_times_et": None,
            "family_states": None,
            "family_times": None,
        }
        if a.source_tool in _CR3BP_ORBIT_TOOLS:
            # CR3BP 周期轨道作为初猜；标称星历四件套来自 extra["ephemeris"]
            # （catalog_promote 提升的成员无星历段，仅初猜）
            eph = a.extra.get("ephemeris") or {}
            data["initial_guess_states"] = a.state_data
            data["initial_guess_times"] = a.times
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
            data["family_times"] = a.times
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
        """等比例开关：勾选后 3D/2D 按数据真实比例（Z 区间会多取一些），否则各轴独立填满。"""
        self._canvas_state.equal_aspect = checked
        self._render_canvas()

    def _on_center_changed(self, center: str) -> None:
        """中心视图切换：质心/月球/L1/L2（惯性系下 L1/L2 已灰显，不会到达）。"""
        self._canvas_state.center = center
        self._render_canvas()

    def _on_frame_changed(self, frame: str) -> None:
        """坐标系切换：会合系（CR3BP 旋转系）/ 惯性系（GCRS/J2000，km）。

        inertial 需要 position_km + times_et；纯 CR3BP 产物（轨道族/旧初猜）
        降级为旋转近似视图。inertial 下 L1/L2 中心无意义（灰显并回退质心）；
        CR3BP 初猜无几何意义，"初猜"绘制内容自动切到"星历"并灰显控件。
        """
        self._canvas_state.frame = frame
        if frame == "inertial" and self._canvas_state.center in ("L1", "L2"):
            # L1/L2 是会合系概念，惯性系下回退质心（即地球原点）
            self._canvas_state.center = "barycenter"
        self._update_plot_content_controls()
        self._update_center_controls()
        if frame == "inertial" and not self._selected_artifacts_have_inertial():
            self._status_bar.showMessage(
                "所选记录没有惯性系星历数据，显示会合系旋转近似视图", _STATUS_MSG_TIMEOUT_MS
            )
        self._render_canvas()

    def _update_center_controls(self) -> None:
        """惯性系下 L1/L2 中心无几何意义，灰显；回会合系恢复。"""
        tb = self._viz.projection_toolbar
        enabled = self._canvas_state.frame == "synodic"
        tb.center_l1.setEnabled(enabled)
        tb.center_l2.setEnabled(enabled)
        self._sync_toolbar_buttons()

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
        tb.center_barycenter.setChecked(state.center == "barycenter")
        tb.center_moon.setChecked(state.center == "moon")
        tb.center_l1.setChecked(state.center == "L1")
        tb.center_l2.setChecked(state.center == "L2")
        tb.plot_overlay.setChecked(state.plot_content == "overlay")
        tb.plot_guess.setChecked(state.plot_content == "guess")
        tb.plot_ephemeris.setChecked(state.plot_content == "ephemeris")
        tb.equal_aspect.setChecked(state.equal_aspect)

    def _selected_artifacts_have_initial_guess(self) -> bool:
        """任一当前选中 Artifact 含 CR3BP 初猜（design_orbit / 提升成员）即为 True。"""
        for aid in self._selected_artifact_ids:
            a = self._project.get_by_id(aid)
            if a is None:
                continue
            if a.source_tool in _CR3BP_ORBIT_TOOLS and a.state_data is not None:
                return True
        return False

    def _selected_artifacts_have_inertial(self) -> bool:
        """任一当前选中 Artifact 同时含 position_km 与 times_et 即为 True。"""
        for aid in self._selected_artifact_ids:
            a = self._project.get_by_id(aid)
            if a is None:
                continue
            # design_orbit 的星历在 extra["ephemeris"]，control_orbit 在 extra 顶层
            if a.source_tool in _CR3BP_ORBIT_TOOLS:
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
            self._status_bar.showMessage(
                "请先在左侧项目树中选择一条星历记录", _STATUS_MSG_TIMEOUT_MS
            )
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
            self._status_bar.showMessage("所选记录的数据不可用", _STATUS_MSG_TIMEOUT_MS)
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
                "所选记录没有星历时间数据，无法导出动画", _STATUS_MSG_TIMEOUT_MS
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
