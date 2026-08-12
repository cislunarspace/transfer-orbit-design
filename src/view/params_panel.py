"""参数面板自动化 -- 从 Pydantic Request 模型生成 Qt 控件。

Pydantic -> Qt 映射：
- float + ge/le/gt/lt   -> QDoubleSpinBox
- int   + ge/le/gt/lt   -> QSpinBox
- str   + Literal        -> QComboBox
- str   无约束            -> QLineEdit
- Optional[T]            -> QCheckBox + 对应控件（未勾选返回 None）
- list[float]            -> N 个 QDoubleSpinBox（水平排列）
- Any                    -> QLineEdit（JSON 文本）

约束语义差异：
- Pydantic ``gt=0``  ->  QDoubleSpinBox.setMinimum(0 + eps)
- Pydantic ``lt=1``  ->  QDoubleSpinBox.setMaximum(1 - eps)
"""

from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from src.commons.units import DAYS_PER_YEAR, DU_KM, SECONDS_PER_YEAR, TU_SECONDS

# ---------------------------------------------------------------------------
# 每轨道类型的默认值 / 显示字段
# ---------------------------------------------------------------------------

#: 每轨道类型分支的形状参数默认值。多数与 e2m2e
#: ``algorithm/design/design_orbit.py::_validate_params`` 的 None 兜底默认值一致；
#: **DRO 例外**——e2m2e 兜底 10000 km 是 DFH 黄金样本标定值（近月紧凑、星历稳定），
#: 但在地月尺度画布上是贴着月球的点，不像用户认知里的"典型 DRO"。GUI 默认取
#: 60000 km（距月 54000–66000 km，ARTEMIS/Gateway 量级的中等 DRO），让用户打开即见
#: 典型形状。代价：大幅 DRO 在真实星历里不如紧凑 DRO 稳定（默认 1 个月星历会漂移），
#: 与 Halo 默认同理——画布画的是 CR3BP 周期轨道，星历漂移不影响形状观察。
ORBIT_TYPE_DEFAULTS: dict[str, dict[str, float | int]] = {
    "DRO": {"amplitude": 60000.0, "phase": 0.5001},
    "NRHO": {
        "collinear_point": 2,
        "north_south": 2,
        "perilune_height": 5000.0,
        "phase": 0.5,
    },
    "Halo": {"collinear_point": 2, "amplitude": 30000.0, "phase": 0.0},
    "Lissajous": {
        "collinear_point": 2,
        "amplitude_in": 2500.0,
        "amplitude_out": 7500.0,
        "phase_in": 0.01,
        "phase_out": 0.55,
    },
    "L4": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
    "L5": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
    # ELFO（月心冻结轨道）形状参数。semi_major_axis 模型必填，GUI 取近月冻结
    # 代表值 6500 km；其余对齐 DesignOrbitRequest model_validator 的 ELFO 默认
    # （inclination=75、arg_of_pericenter=270、perilune_height=200）。
    "ELFO": {
        "semi_major_axis": 6500.0,
        "inclination": 75.0,
        "arg_of_pericenter": 270.0,
        "perilune_height": 200.0,
    },
}

#: 每轨道类型分支应显示的字段集（== 该分支默认值字段集）。
ORBIT_TYPE_FIELDS: dict[str, set[str]] = {
    "DRO": {"amplitude", "phase"},
    "NRHO": {"collinear_point", "north_south", "perilune_height", "phase"},
    "Halo": {"collinear_point", "amplitude", "phase"},
    "Lissajous": {
        "collinear_point",
        "amplitude_in",
        "amplitude_out",
        "phase_in",
        "phase_out",
    },
    "L4": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
    "L5": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
    "ELFO": {"semi_major_axis", "inclination", "arg_of_pericenter", "perilune_height"},
}

# ---------------------------------------------------------------------------
# 特殊字段：epoch 6-spinbox 与 correction_method 下拉
# ---------------------------------------------------------------------------

#: epoch 字段名。仅当默认值是 6 元序列时渲染为 6 个 spinbox，
#: 避免误伤其它 Any 字段（如 control_orbit 的 input_ephemeris）。
_EPOCH_FIELD = "epoch"

#: correction_method 下拉取值，须对齐 e2m2e
#: ``algorithm/ephemeris_correction/__init__.py::_REGISTRY`` 的键。
#: 注：segmented 由 e2m2e 对 Halo/NRHO 自动选用（design_orbit 内部路径），
#: 不在此暴露——用户选 two_level/standard 时不稳定轨道会被自动重定向。
CORRECTION_METHOD_OPTIONS: tuple[str, ...] = ("standard", "two_level", "homotopy")

#: str 枚举类字段 -> 下拉选项（现仅 correction_method）。
_STR_ENUM_FIELDS: dict[str, tuple[str, ...]] = {
    "correction_method": CORRECTION_METHOD_OPTIONS,
}

#: epoch 6 个 spinbox 的取值范围；is_int=True -> QSpinBox，False -> QDoubleSpinBox。
_EPOCH_SPINBOX_SPECS: tuple[tuple[str, float, float, bool], ...] = (
    ("年", 1900, 2100, True),
    ("月", 1, 12, True),
    ("日", 1, 31, True),
    ("时", 0, 23, True),
    ("分", 0, 59, True),
    ("秒", 0.0, 59.0, False),
)

# ---------------------------------------------------------------------------
# 可切换显示单位（对齐 e2m2e 参数的标准单位，见 src/commons/units.py）
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class UnitOption:
    """单个显示单位。``display * to_standard = standard``。

    decimals/step 为该显示单位下 spinbox 的小数位与步长。
    """

    label: str
    to_standard: float
    decimals: int = 4
    step: float = 1.0


#: 可切换单位字段 -> 单位选项（首个 = 标准单位，to_standard == 1.0）。
#: 独立于 ORBIT_TYPE_DEFAULTS/FIELDS，避免破坏现有默认值测试。
FIELD_UNIT_OPTIONS: dict[str, tuple[UnitOption, ...]] = {
    "amplitude": (
        UnitOption("km", 1.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "perilune_height": (
        UnitOption("km", 1.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_in": (
        UnitOption("km", 1.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_out": (
        UnitOption("km", 1.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "duration": (
        UnitOption("年", 1.0),
        UnitOption("月", 1.0 / 12, decimals=4, step=1.0),
        UnitOption("日", 1.0 / DAYS_PER_YEAR, decimals=4, step=1.0),
        UnitOption("TU", TU_SECONDS / SECONDS_PER_YEAR, decimals=4, step=0.1),
    ),
    "output_step": (
        UnitOption("秒", 1.0),
        UnitOption("TU", TU_SECONDS, decimals=4, step=0.001),
    ),
}

#: Optional 字段的 GUI 展示默认值：这些字段不包 Optional 容器（勾选框），直接
#: 展示为 spinbox 并填入默认值。它们是"通用字段"（不进 ORBIT_TYPE_DEFAULTS
#: 分支，不会被 apply_orbit_type_defaults 解包），需要 GUI 层自行给初值。
#:
#: duration：e2m2e 5.6.5 起 model default=None（让 model_validator 按 orbit_type
#: 填秒级默认）；GUI 仍展示 1 年短弧默认（issue #355），main_window 再覆盖到 1 月。
#: 此处默认值单位为年（FIELD_UNIT_OPTIONS["duration"] 的标准单位），facade
#: 构造 request 时换算成秒。
_OPTIONAL_FIELD_GUI_DEFAULTS: dict[str, float] = {
    "duration": 1.0,
}

# Qt 动态属性名：控件用 setProperty 存单位状态。拼错会静默破坏换算，故提为常量。
# 用单下划线前缀，避免双下划线带来的 name-mangling 语义误导（动态属性本身不参与
# mangling，但双下划线会让读者误以为有改写）。
_UNIT_ATTR = "_params_panel_unit"
_STD_MIN_ATTR = "_params_panel_std_min"
_STD_MAX_ATTR = "_params_panel_std_max"

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_field_meta(field: Any) -> dict[str, Any]:
    """从 Pydantic v2 FieldInfo 提取约束元数据。

    annotated_types 约束（Ge/Le/Gt/Lt/...）是带 ``slots=True`` 的 frozen
    dataclass，没有 ``__dict__``，须用 ``dataclasses.fields`` 提取。
    """
    meta: dict[str, Any] = {}
    if not hasattr(field, "metadata"):
        return meta
    for constraint in field.metadata:
        if dataclasses.is_dataclass(constraint):
            for f in dataclasses.fields(constraint):
                value = getattr(constraint, f.name)
                if value is not None:
                    meta[f.name] = value
            continue
        if not hasattr(constraint, "__dict__"):
            continue
        for key, value in constraint.__dict__.items():
            if value is not None:
                meta[key] = value
    return meta


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """解包 Optional[T] -> (T, True)，非 Optional 返回 (tp, False)。"""
    origin = typing.get_origin(tp)
    if origin is typing.Union or isinstance(tp, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _is_literal(tp: Any) -> bool:
    """判断类型是否为 Literal。"""
    return typing.get_origin(tp) is typing.Literal


# ---------------------------------------------------------------------------
# 显示单位辅助
# ---------------------------------------------------------------------------


def get_field_units(field_name: str) -> tuple[UnitOption, ...] | None:
    """返回字段的可切换单位选项；字段不支持单位切换时返回 None。"""
    return FIELD_UNIT_OPTIONS.get(field_name)


def _find_unit_option(field_name: str, unit: str) -> UnitOption | None:
    """按单位名查找 UnitOption；未知单位返回 None（不静默回退到首个）。

    调用方传入的 unit 通常来自控件属性或单位下拉（必是 options 中的 label），
    返回 None 仅在收到非法 unit 时发生，由调用方自行决定是否中止。
    """
    options = get_field_units(field_name)
    if not options:
        return None
    for opt in options:
        if opt.label == unit:
            return opt
    return None


def _current_unit_option(field_name: str, widget: QWidget) -> UnitOption | None:
    """读取控件当前显示单位（属性缺失时视为标准单位）。"""
    options = get_field_units(field_name)
    if not options:
        return None
    unit = widget.property(_UNIT_ATTR) or options[0].label
    return _find_unit_option(field_name, unit)


def set_spinbox_unit(sb: QDoubleSpinBox, field_name: str, unit: str) -> None:
    """切换 QDoubleSpinBox 的显示单位：换算当前值并缩放范围/步长/小数位。

    单位状态存于控件属性：``_params_panel_unit``（当前显示单位）、
    ``_params_panel_std_min/_params_panel_std_max``（标准单位下的范围，
    控件生成时从约束写入）。
    """
    options = get_field_units(field_name)
    if not options:
        return
    new_opt = _find_unit_option(field_name, unit)
    if new_opt is None:
        return
    old_opt = _current_unit_option(field_name, sb)
    if old_opt is None or old_opt is new_opt:
        return
    standard = float(sb.value()) * old_opt.to_standard
    sb.setProperty(_UNIT_ATTR, new_opt.label)
    sb.setDecimals(new_opt.decimals)
    sb.setSingleStep(new_opt.step)
    std_min = sb.property(_STD_MIN_ATTR)
    std_max = sb.property(_STD_MAX_ATTR)
    if std_min is not None:
        sb.setMinimum(float(std_min) / new_opt.to_standard)
    if std_max is not None:
        sb.setMaximum(float(std_max) / new_opt.to_standard)
    sb.setValue(standard / new_opt.to_standard)


# ---------------------------------------------------------------------------
# 单类型控件工厂
# ---------------------------------------------------------------------------


def _make_float_field(field_name: str, field: Any, meta: dict[str, Any]) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(4)
    if "ge" in meta:
        widget.setMinimum(float(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(float(meta["gt"]) + 1e-8)
    has_upper = "le" in meta or "lt" in meta
    if "le" in meta:
        widget.setMaximum(float(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(float(meta["lt"]) - 1e-8)
    widget.setSingleStep(1.0)
    if field.default is not None and field.default is not ...:
        default = float(field.default)
        # 无上界约束时 Qt 默认 max=99.99 过小：用大值（与 _make_list_float_field
        # 的 ±1e12 一致），仅在默认值更大时再扩（实际不会触发）。
        # 有上界约束时仍保留"扩 max 容纳默认值"的兜底。
        if not has_upper:
            widget.setMaximum(max(1e12, default))
        elif default > widget.maximum():
            widget.setMaximum(default)
        widget.setValue(default)
    elif widget.minimum() <= 0.0 <= widget.maximum():
        widget.setValue(0.0)

    # 可切换单位字段：写入标准单位下的范围属性 + 默认显示单位（标准单位）
    options = get_field_units(field_name)
    if options is not None:
        std = options[0]
        widget.setProperty(_STD_MIN_ATTR, float(widget.minimum()))
        widget.setProperty(_STD_MAX_ATTR, float(widget.maximum()))
        widget.setProperty(_UNIT_ATTR, std.label)
        widget.setDecimals(std.decimals)
        widget.setSingleStep(std.step)
    return widget


def _make_int_field(field: Any, meta: dict[str, Any]) -> QSpinBox:
    widget = QSpinBox()
    if "ge" in meta:
        widget.setMinimum(int(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(int(meta["gt"]) + 1)
    if "le" in meta:
        widget.setMaximum(int(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(int(meta["lt"]) - 1)
    if field.default is not None and field.default is not ...:
        default = int(field.default)
        # 无上界约束时 Qt 默认 max=99，扩到能容纳默认值
        if default > widget.maximum():
            widget.setMaximum(default)
        widget.setValue(default)
    elif widget.minimum() <= 0 <= widget.maximum():
        widget.setValue(0)
    return widget


def _make_str_field(field: Any) -> QLineEdit:
    widget = QLineEdit()
    if field.default is not None and field.default is not ...:
        widget.setText(str(field.default))
    return widget


def _make_combo_from_literal(tp: Any, field: Any) -> QComboBox:
    widget = QComboBox()
    values = [str(v) for v in typing.get_args(tp)]
    widget.addItems(values)
    if field.default is not None and field.default is not ...:
        idx = values.index(str(field.default)) if str(field.default) in values else 0
        widget.setCurrentIndex(idx)
    return widget


# ---------------------------------------------------------------------------
# 复合控件工厂 (G6, G7)
# ---------------------------------------------------------------------------


def _make_optional_wrapper(
    inner_widget: QWidget,
    field: Any,
) -> QWidget:
    """Optional[T] -> QCheckBox + 内部控件容器。

    未勾选时内部控件 disabled，collect_params 返回 None。
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    cb = QCheckBox()
    cb.setChecked(field.default is not None)
    layout.addWidget(cb)
    layout.addWidget(inner_widget)

    inner_widget.setEnabled(field.default is not None)
    cb.toggled.connect(inner_widget.setEnabled)

    container.setProperty("__params_panel_kind", "optional")
    return container


def _make_list_float_field(field: Any, meta: dict[str, Any]) -> QWidget:
    """list[float] -> 水平排列的 N 个 QDoubleSpinBox。"""
    args = typing.get_args(field.annotation)
    n = args[1] if len(args) > 1 and isinstance(args[1], int) else 3

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    defaults: list[float] = list(field.default) if field.default is not None else [0.0] * n

    for i in range(n):
        sb = QDoubleSpinBox()
        sb.setDecimals(4)
        sb.setSingleStep(1.0)
        sb.setMinimum(-1e12)
        sb.setMaximum(1e12)
        if i < len(defaults):
            sb.setValue(float(defaults[i]))
        layout.addWidget(sb)

    container.setProperty("__params_panel_kind", "list_float")
    return container


def _is_epoch_default(value: Any) -> bool:
    """判断默认值是否为 [年,月,日,时,分,秒] 六元序列。"""
    return isinstance(value, (tuple, list)) and len(value) == 6


def _make_epoch_field(field: Any) -> QWidget:
    """epoch -> 水平排列的 6 个 spinbox（年/月/日/时/分 整数，秒浮点）。

    调用方（``_make_field_widget``）仅在 ``_is_epoch_default(field.default)``
    为真时路由进来，故此处 default 必为 6 元序列，无需兜底。
    """
    defaults = [float(v) for v in field.default]
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    for (_, lo, hi, is_int), default in zip(_EPOCH_SPINBOX_SPECS, defaults, strict=True):
        if is_int:
            sb = QSpinBox()
            sb.setRange(int(lo), int(hi))
            sb.setValue(int(default))
        else:
            sb = QDoubleSpinBox()
            sb.setDecimals(3)
            sb.setRange(float(lo), float(hi))
            sb.setValue(float(default))
        layout.addWidget(sb)

    container.setProperty("__params_panel_kind", "epoch")
    return container


def _make_str_enum_combo(field: Any, options: tuple[str, ...]) -> QComboBox:
    """str 枚举字段 -> QComboBox，选中项对齐字段默认值。"""
    combo = QComboBox()
    combo.addItems(list(options))
    if field.default is not None and field.default is not ...:
        default = str(field.default)
        if default in options:
            combo.setCurrentIndex(options.index(default))
    return combo


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def _make_field_widget(field_name: str, field: Any) -> QWidget | None:
    """根据 Pydantic 字段类型和约束创建对应 Qt 控件。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    # 特判 1：epoch（[年,月,日,时,分,秒]）-> 6-spinbox 容器。
    # 仅当默认值是 6 元序列才命中，避免误伤其它 Any 字段（如 input_ephemeris）。
    if field_name == _EPOCH_FIELD and inner_tp is Any and _is_epoch_default(field.default):
        return _make_epoch_field(field)

    # 特判 2：str 枚举类字段（correction_method）-> QComboBox。
    options = _STR_ENUM_FIELDS.get(field_name)
    if inner_tp is str and options:
        return _make_str_enum_combo(field, options)

    origin = typing.get_origin(inner_tp)
    meta = _get_field_meta(field)

    # 基础控件选择
    base_widget: QWidget | None = None

    if _is_literal(inner_tp):
        base_widget = _make_combo_from_literal(inner_tp, field)
    elif origin is list:
        args = typing.get_args(inner_tp)
        if args and args[0] is float:
            base_widget = _make_list_float_field(field, meta)
    elif inner_tp is float or origin is float:
        base_widget = _make_float_field(field_name, field, meta)
    elif inner_tp is int or origin is int:
        base_widget = _make_int_field(field, meta)
    elif inner_tp is str:
        base_widget = _make_str_field(field)
    else:
        # Any / 其它 -> QLineEdit（JSON）
        # 无注解局部变量承接：pyright 对 PyQt6 类型不做赋值收窄（已知限制），
        # 带 `| None` 注解的 base_widget 赋值后仍视为可为 None，故换名新建。
        line_edit = QLineEdit()
        if field.default is not None and field.default is not ...:
            line_edit.setText(str(field.default))
        base_widget = line_edit

    if base_widget is None:
        return None

    # G7: Optional 包装
    if is_optional and field.default is None:
        # 通用 Optional 字段（如 duration）：模型 default=None（让 e2m2e
        # model_validator 兜底），但 GUI 始终展示 spinbox + 合理默认值，不走
        # 勾选框式 Optional 容器。这些字段不在 ORBIT_TYPE_DEFAULTS 分支，不会被
        # apply_orbit_type_defaults 解包，故在此直接给 spinbox。
        gui_default = _OPTIONAL_FIELD_GUI_DEFAULTS.get(field_name)
        if gui_default is not None:
            if isinstance(base_widget, QDoubleSpinBox):
                base_widget.setValue(float(gui_default))
            return base_widget
        return _make_optional_wrapper(base_widget, field)

    return base_widget


def build_params_from_model(
    model_class: type,
    parent: QWidget | None = None,
) -> dict[str, QWidget]:
    """从 Pydantic 模型自动生成参数面板控件。

    Returns:
        字段名 -> Qt 控件字典。调用方负责将控件加入布局。
    """
    widgets: dict[str, QWidget] = {}
    for name, field in model_class.model_fields.items():
        widget = _make_field_widget(name, field)
        if widget is not None:
            if parent is not None:
                widget.setParent(parent)
            # G2: Field.description -> tooltip
            if field.description:
                widget.setToolTip(field.description)
            widgets[name] = widget
    return widgets


# ---------------------------------------------------------------------------
# 默认值填充（per-orbit_type）
# ---------------------------------------------------------------------------


def _find_inner_widget(container: QWidget) -> QWidget | None:
    """从 Optional 容器中找出唯一的非 QCheckBox 子控件。"""
    inner_widgets = container.findChildren(QWidget)
    return next(
        (w for w in inner_widgets if not isinstance(w, QCheckBox)),
        None,
    )


def _unwrap_optional_widget(widget: QWidget) -> QWidget:
    """若控件是 Optional 容器（QCheckBox + 内部控件），解包返回内部控件。

    解包时把内部控件脱离容器父级，避免容器被 Python 回收时连带删除内部控件。
    非 Optional 容器原样返回。
    """
    if widget.property("__params_panel_kind") != "optional":
        return widget
    inner = _find_inner_widget(widget)
    if inner is not None:
        inner.setParent(None)
        return inner
    return widget


def apply_orbit_type_defaults(
    widgets: dict[str, QWidget],
    orbit_type: str,
) -> None:
    """把 orbit_type 分支的默认值填入 widgets 对应控件。

    分支字段若是 Optional 容器（QCheckBox + 内部控件），解包为内部控件并
    用分支默认值 setValue（去掉勾选框，直接可调）。未知 orbit_type 或字段
    缺失时静默跳过（无分支则不做任何事）。按控件类型而非模型字段类型设值
    （int 默认值 -> QSpinBox，float 默认值 -> QDoubleSpinBox）。
    """
    defaults = ORBIT_TYPE_DEFAULTS.get(orbit_type)
    if not defaults:
        return
    for field_name, value in defaults.items():
        widget = widgets.get(field_name)
        if widget is None:
            continue
        widget = _unwrap_optional_widget(widget)
        widget.setEnabled(True)
        widgets[field_name] = widget
        if isinstance(widget, QDoubleSpinBox):
            value_f = float(value)
            # 标准单位默认值 -> 当前显示单位
            opt = _current_unit_option(field_name, widget)
            if opt is not None:
                value_f /= opt.to_standard
            widget.setValue(value_f)
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))


# ---------------------------------------------------------------------------
# 值读取
# ---------------------------------------------------------------------------


def _read_list_float(widget: QWidget) -> list[float]:
    """从 list_float 容器读取所有 QDoubleSpinBox 值。"""
    result: list[float] = []
    for child in widget.findChildren(QDoubleSpinBox):
        result.append(float(child.value()))
    return result


def _read_epoch(widget: QWidget) -> list[float]:
    """从 epoch 容器按布局顺序读取 6 个 spinbox 值，返回 [年,月,日,时,分,秒]。

    对日历合法性做校验（挡 Feb 30 等 spinbox 范围挡不住的非法日期），
    让收集阶段立即报友好错误，而非等到 SPICE str2et 解析失败。
    """
    import datetime

    values: list[float] = []
    layout = widget.layout()
    if layout is not None:
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                values.append(float(w.value()))

    if len(values) == 6:
        y, mo, d, h, mi, s = (int(v) for v in values)
        try:
            datetime.datetime(y, mo, d, h, mi, s)
        except ValueError as exc:
            raise ValueError(f"非法历元: {exc}") from exc
    return values


def _read_widget_value(name: str, field: Any, widget: QWidget) -> Any:
    """从单个控件读取当前值，按字段类型转换。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    # G7: Optional 容器
    if widget.property("__params_panel_kind") == "optional":
        cb = widget.findChild(QCheckBox)
        if cb and not cb.isChecked():
            return None
        # 找到非 QCheckBox 的内部控件
        inner = _find_inner_widget(widget)
        if inner is not None:
            return _read_widget_value(name, field, inner)

    # epoch 容器（6 个 spinbox）
    if widget.property("__params_panel_kind") == "epoch":
        return _read_epoch(widget)

    # G6: list[float] 容器
    if widget.property("__params_panel_kind") == "list_float":
        return _read_list_float(widget)

    if isinstance(widget, QComboBox):
        val = widget.currentText()
    elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        val = widget.value()
    elif isinstance(widget, QLineEdit):
        val = widget.text()
    else:
        val = widget  # 不可达（防御）

    if inner_tp is float and isinstance(val, (int, float)):
        result = float(val)
        # 显示单位 -> 标准单位（可切换单位字段）
        opt = _current_unit_option(name, widget)
        if opt is not None:
            result *= opt.to_standard
        return result
    if inner_tp is int and isinstance(val, (int, float)):
        return int(val)
    return val


def collect_params(widgets: dict[str, QWidget], model_class: type) -> dict[str, Any]:
    """从控件字典收集参数值，返回可传给 FacadeBridge 的 dict。

    ``model_class`` 用于查找字段类型以做正确转换。
    """
    params: dict[str, Any] = {}
    for name, widget in widgets.items():
        field = model_class.model_fields[name]
        params[name] = _read_widget_value(name, field, widget)
    return params
